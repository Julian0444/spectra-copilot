"""Pre-request reservations for a bounded text-only Anthropic run.

No paid request is enabled by default. USD accounting uses integer microdollars.
The conservative UTF-8 bound is a declared transport assumption, not a provider
billing guarantee. Unknown/over-bound usage locks the ledger as uncertified.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
import json
import math
import time

PINNED_MODEL = 'claude-haiku-4-5-20251001'
RATES = {PINNED_MODEL:(1,5), 'claude-haiku-4-5':(1,5), 'claude-opus-4-8':(5,25)}


class BudgetStop(RuntimeError):
    def __init__(self, code):self.code=code;super().__init__(code)


@dataclass(frozen=True)
class Limits:
    input_tokens:int=64000
    output_tokens:int=4096
    calls:int=8
    max_output_per_call:int=512
    usd:float=0.
    retries:int=0
    seconds:float=120.


class Budget:
    def __init__(self, model=PINNED_MODEL, limits=None, parent=None):
        self.model,self.limits,self.parent=model,limits or Limits(),parent
        if model not in RATES:raise BudgetStop('unpriced_model')
        if parent and parent.model!=model:raise ValueError('Aggregate model identity must match')
        if (any(type(getattr(self.limits,k)) is not int or getattr(self.limits,k)<0 for k in
                ('input_tokens','output_tokens','calls','max_output_per_call','retries')) or self.limits.retries!=0
                or not math.isfinite(self.limits.usd) or self.limits.usd<0 or not math.isfinite(self.limits.seconds) or self.limits.seconds<=0):
            raise ValueError('Invalid limits; automatic retries must be zero')
        self.cap=int(Decimal(str(self.limits.usd))*1000000)
        self.used_in=self.used_out=self.calls=self.spent=0
        self.reserved_in=self.reserved_out=self.reserved_usd=0
        self.certified=True;self.events=[];self.on_change=None;self.started=time.monotonic();self.used=False

    def begin(self):
        if self.used:raise BudgetStop('retry_forbidden')
        self.used=True
        self.check_open()

    def check_open(self):
        if not self.certified:raise BudgetStop('usage_uncertified')
        if self.cap==0:raise BudgetStop('paid_budget_zero')
        if time.monotonic()-self.started>=self.limits.seconds:raise BudgetStop('case_timeout')
        if self.parent:self.parent.check_open()

    def remaining_seconds(self):
        value=self.limits.seconds-(time.monotonic()-self.started)
        return min(value,self.parent.remaining_seconds()) if self.parent else value

    def _check(self,n_in,n_out,cost):
        self.check_open()
        if self.calls>=self.limits.calls:raise BudgetStop('call_budget_exhausted')
        if self.used_in+self.reserved_in+n_in>self.limits.input_tokens:raise BudgetStop('input_budget_exhausted')
        if self.used_out+self.reserved_out+n_out>self.limits.output_tokens:raise BudgetStop('output_budget_exhausted')
        if self.spent+self.reserved_usd+cost>self.cap:raise BudgetStop('usd_budget_exhausted')
        if self.parent:self.parent._check(n_in,n_out,cost)

    def reserve(self,n_in,n_out):
        if type(n_in) is not int or type(n_out) is not int or min(n_in,n_out)<0:raise ValueError('Invalid reservation')
        if n_out>self.limits.max_output_per_call:raise BudgetStop('per_call_output_exceeded')
        cost=n_in*RATES[self.model][0]+n_out*RATES[self.model][1]
        self._check(n_in,n_out,cost)
        ticket={'input_bound':n_in,'output_bound':n_out,'microdollars':cost,'status':'reserved'}
        self._reserve(ticket);self.events.append(ticket)
        try:
            if self.on_change:self.on_change(self.snapshot())
        except BaseException:
            self._settle(ticket,0,0,0)
            ticket.update(status='not_sent',input_tokens=0,output_tokens=0,actual_microdollars=0)
            raise
        return ticket

    def _reserve(self,ticket):
        self.calls+=1;self.reserved_in+=ticket['input_bound'];self.reserved_out+=ticket['output_bound'];self.reserved_usd+=ticket['microdollars']
        if self.parent:self.parent._reserve(ticket)

    def settle(self,ticket,usage):
        if ticket['status']!='reserved':raise ValueError('Reservation already settled')
        try:
            values={k:getattr(usage,k,None) if not isinstance(usage,dict) else usage.get(k) for k in
                    ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')}
            n_in,n_out=values['input_tokens'],values['output_tokens']
            if type(n_in) is not int or type(n_out) is not int or min(n_in,n_out)<0:
                raise ValueError('Unknown usage')
            # This proposal sends no cache controls, server tools or thinking.
            if any(values[k] not in (None,0) for k in ('cache_creation_input_tokens','cache_read_input_tokens')):
                raise ValueError('Unexpected billing category')
            if n_in>ticket['input_bound'] or n_out>ticket['output_bound']:
                raise ValueError('Usage outside pre-request bound')
        except Exception:
            self.uncertain(ticket);raise BudgetStop('usage_uncertified') from None
        cost=n_in*RATES[self.model][0]+n_out*RATES[self.model][1]
        self._settle(ticket,n_in,n_out,cost)
        ticket.update(status='settled',input_tokens=n_in,output_tokens=n_out,actual_microdollars=cost)
        if self.on_change:self.on_change(self.snapshot())

    def _settle(self,ticket,n_in,n_out,cost):
        self.reserved_in-=ticket['input_bound'];self.reserved_out-=ticket['output_bound'];self.reserved_usd-=ticket['microdollars']
        self.used_in+=n_in;self.used_out+=n_out;self.spent+=cost
        if self.parent:self.parent._settle(ticket,n_in,n_out,cost)

    def uncertain(self,ticket):
        # Keep the full reservation charged against available budget, never retry.
        ticket['status']='unknown_usage';self.certified=False
        if self.parent:self.parent.uncertain(ticket)
        if self.on_change:self.on_change(self.snapshot())

    def snapshot(self):
        return {'model':self.model,'calls':self.calls,'retries':0,'input_tokens':self.used_in,'output_tokens':self.used_out,
                'usd':self.spent/1e6 if self.certified else None,'known_usd':self.spent/1e6,
                'reserved_usd':self.reserved_usd/1e6,'cost_certified':self.certified,
                'cap_usd':self.cap/1e6,'events':self.events.copy(),
                'input_bound_policy':'UTF-8 request JSON bytes + 4096 framing/tool allowance; text-only; over-bound usage invalidates certification'}


def new_budget(model):
    return Budget(model)  # Zero paid USD without explicit caller-supplied limits.


def _clean(value):
    from anthropic import omit, NOT_GIVEN
    if isinstance(value,dict):return {k:_clean(v) for k,v in value.items() if v is not omit and v is not NOT_GIVEN}
    if isinstance(value,(list,tuple)):return [_clean(v) for v in value]
    if value is None or type(value) in (str,int,float,bool):return value
    raise BudgetStop('unsupported_request_value')


def request_bound(body,model):
    body=_clean(body)
    if body.get('model')!=model:raise BudgetStop('model_budget_mismatch')
    if body.get('stream') or any(k in body for k in ('thinking','cache_control','mcp_servers','context_management','output_config')):
        raise BudgetStop('unbudgeted_request_feature')
    def validate(node):
        if isinstance(node,dict):
            if 'cache_control' in node or ('type' in node and node['type'] in
                    {'image','document','server_tool_use','web_search_20250305','code_execution_20250522'}):
                raise BudgetStop('unbudgeted_request_feature')
            for v in node.values():validate(v)
        elif isinstance(node,list):
            for v in node:validate(v)
    validate(body)
    if any('type' in t and t['type']!='custom' for t in body.get('tools',[])):
        raise BudgetStop('server_tool_forbidden')
    # 4096 includes the published 496-token Haiku tool prompt plus framing margin.
    n_in=len(json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())+4096
    n_out=body.get('max_tokens')
    if type(n_out) is not int or n_out<1:raise BudgetStop('missing_output_limit')
    return n_in,n_out


@contextmanager
def guard_sdk(client,budget):
    """Guard the SDK's actual POST boundary, including tool_runner.parse requests."""
    if client.max_retries!=0:raise BudgetStop('sdk_retries_forbidden')
    resource=client.beta.messages;original=resource._post
    def guarded(path,*args,**kwargs):
        if path.split('?')[0]!='/v1/messages':raise BudgetStop('unbudgeted_endpoint')
        n_in,n_out=request_bound(kwargs['body'],budget.model)
        ticket=budget.reserve(n_in,n_out)
        options=dict(kwargs.get('options') or {})
        options['timeout']=max(.001,budget.remaining_seconds())
        kwargs['options']=options
        try:
            message=original(path,*args,**kwargs)
        except BaseException:
            budget.uncertain(ticket)
            raise
        budget.settle(ticket,getattr(message,'usage',None))
        return message
    resource._post=guarded
    try:yield
    finally:resource._post=original
