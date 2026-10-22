"""5B-2.2: reuse frozen development replay, then ONLY free token counting.

prepare is offline. count loads the macOS Keychain credential inside its process;
its transport allows only POST https://api.anthropic.com/v1/messages/count_tokens.
No generation, retries other than bounded 429 handling, or acceptance data.
Private bodies/rows stay outside Git. Only aggregate summary and hash are public.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import time

import anthropic
import httpx

from copilot import agent
from copilot.acceptance_io import sha256, write_json
from copilot.budget import (Budget, BudgetStop, Limits, PINNED_MODEL,
    FRAMING_ALLOWANCE, CASE_MAX_NANODOLLARS, NANODOLLARS_PER_USD, request_bound)

DEVELOPMENT_SHA256='60b2b4584e5a57030a4ff82a1b13d23065505a4d8bb878a20f5d4caecbe3f7c4'
COUNT_PATH='/v1/messages/count_tokens'


def wire(body):
    return json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()


def count_parameters(body):
    request_bound(body,PINNED_MODEL)
    # max_tokens bounds generated output and is not part of this endpoint's schema.
    return {k:deepcopy(v) for k,v in body.items() if k!='max_tokens'}


def prepare(source, development, output):
    if sha256(development)!=DEVELOPMENT_SHA256:raise ValueError('Development identity changed')
    manifest=json.loads(development.read_text())['cases']
    previous=json.loads((source/'rows.json').read_text())
    source_summary=json.loads((source/'summary.json').read_text())
    if source_summary['identity']['development_sha256']!=DEVELOPMENT_SHA256:raise ValueError('Replay identity changed')
    if len(manifest)!=96 or [r['case_id'] for r in previous]!=[r['case_id'] for r in manifest]:
        raise ValueError('Only the frozen development cohort is allowed')
    if sum(r['kind']=='real' for r in manifest)!=48 or sum(r['kind']=='synthetic' for r in manifest)!=48:
        raise ValueError('Development denominators changed')
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    (output/'requests').mkdir(mode=0o700)
    schemas=[t.to_dict() for t in agent.RunTools('spectrum.npz').tools]
    records=[];conversations=0;invalid=0
    for position,row in enumerate(previous):
        if row['status']=='invalid_input':
            if row['conversations']:raise ValueError('Invalid input had requests')
            invalid+=1;continue
        if row['status']!='measured' or [r['turns'] for r in row['conversations']]!=list(range(3,9)):
            raise ValueError('Incomplete original replay')
        for run in row['conversations']:
            conversations+=1
            for old in run['requests']:
                path=source/'requests'/f"case-{position:03d}-turns-{run['turns']}"/f"request-{old['turn']:02d}.json"
                raw=path.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=old['wire_sha256'] or len(raw)!=old['wire_bytes']:
                    raise ValueError('Original request identity changed')
                body=json.loads(raw)
                if body['tools']!=schemas:raise ValueError('Tool schemas differ from stored replay')
                messages=deepcopy(body['messages']);system=deepcopy(body['system'])
                body.update(model=PINNED_MODEL,max_tokens=Limits().max_output_per_call,**agent.request_kwargs(PINNED_MODEL))
                assert body['messages']==messages and body['system']==system
                bound,out=request_bound(body,PINNED_MODEL)
                payload=wire(body);filename=f'{len(records):04d}.json'
                (output/'requests'/filename).write_bytes(payload)
                records.append({'case_index':position,'kind':row['kind'],'turns':run['turns'],'turn':old['turn'],
                    'file':filename,'source_sha256':old['wire_sha256'],'body_sha256':hashlib.sha256(payload).hexdigest(),
                    'count_body_sha256':hashlib.sha256(wire(count_parameters(body))).hexdigest(),
                    'wire_bytes':len(payload),'input_bound':bound,'output_bound':out})
    if (len(records),conversations,invalid)!=(2970,540,6):raise ValueError('Replay coverage changed')
    write_json(output/'requests.json',records)
    write_json(output/'prepared.json',{'schema':'batch5b22-count-preparation-v1','model':PINNED_MODEL,
        'development_sha256':DEVELOPMENT_SHA256,'source_rows_sha256':sha256(source/'rows.json'),
        'source_summary_sha256':sha256(source/'summary.json'),'requests_sha256':sha256(output/'requests.json'),
        'requested_cases':96,'valid_cases':90,'invalid_cases':6,'conversations':540,'requests':2970,
        'configuration':agent.request_kwargs(PINNED_MODEL),'limits':vars(Limits()),
        'changed_body_fields':['model','max_tokens','thinking','output_config'],
        'histories_and_tool_results':'Unchanged scripted responses from 5B-2.1 development replay',
        'real_generation_calls':0,'spent_usd':0})
    print(json.dumps({'prepared_requests':len(records),'conversations':conversations,'spent_usd':0}))


class CountOnlyTransport(httpx.BaseTransport):
    def __init__(self, transport):
        self.transport=transport;self.requests_made=0

    def handle_request(self,request):
        if (request.method!='POST' or request.url.scheme!='https' or request.url.host!='api.anthropic.com'
                or request.url.port not in (None,443) or request.url.path!=COUNT_PATH or request.url.query):
            raise RuntimeError('Only the authorized free endpoint is allowed')
        self.requests_made+=1
        return self.transport.handle_request(request)

    def close(self):self.transport.close()


def retry_delay(value):
    if value is None:raise ValueError('429 lacks retry-after')
    try:delay=float(value)
    except ValueError:delay=(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds()
    import math
    if not math.isfinite(delay) or delay<0:raise ValueError('Invalid retry-after')
    return delay


def aggregate(directory, records, counted, attempts):
    groups=defaultdict(list)
    for row,measurement in zip(records,counted):
        groups[(row['case_index'],row['turns'])].append((row,measurement))
    by_turns={};worst_reserved=0
    for turns in range(3,9):
        runs=[rows for (_,n),rows in groups.items() if n==turns]
        fits={'full_reservation':0,'counted_input_full_output':0}
        for rows in runs:
            for profile in fits:
                budget=Budget(limits=Limits(usd=.1));admitted=0
                for row,measurement in rows:
                    try:ticket=budget.reserve(row['input_bound'],row['output_bound'])
                    except BudgetStop:break
                    n_in=row['input_bound'] if profile=='full_reservation' else measurement['input_tokens']
                    budget.settle(ticket,{'input_tokens':n_in,'output_tokens':row['output_bound']});admitted+=1
                fits[profile]+=admitted==turns
                if profile=='full_reservation':worst_reserved=max(worst_reserved,budget.spent)
        by_turns[str(turns)]={'valid_cases':len(runs),'complete':fits}
    tokens=[r['input_tokens'] for r in counted]
    ratios=[m['input_tokens']/r['input_bound'] for r,m in zip(records,counted)]
    byte_ratios=[m['input_tokens']/r['wire_bytes'] for r,m in zip(records,counted)]
    margins=[r['input_bound']-m['input_tokens']-FRAMING_ALLOWANCE for r,m in zip(records,counted)]
    return {'schema':'batch5b22-count-summary-v1','date':'2026-10-22','model':PINNED_MODEL,
        'development_sha256':DEVELOPMENT_SHA256,'requests_index_sha256':sha256(directory/'requests.json'),
        'count_rows_sha256':sha256(directory/'count-rows.jsonl'),'prepared_sha256':sha256(directory/'prepared.json'),
        'script_sha256':sha256(__file__),'sdk_version':anthropic.__version__,
        'requested_cases':96,'real_cases':48,'synthetic_cases':48,'valid_cases':90,'invalid_cases':6,
        'conversations':540,'requests_counted':len(counted),'http_requests_made':attempts,
        'rate_policy':{'maximum_rpm':3000,'max_attempts_per_body':3,'retry_only_status':429,'respects_retry_after':True},
        'input_tokens':{'minimum':min(tokens),'maximum':max(tokens),'total_across_replays':sum(tokens)},
        'count_to_bound_ratio':{'maximum':max(ratios),'mean':sum(ratios)/len(ratios)},
        'count_to_wire_bytes_ratio_maximum':max(byte_ratios),
        'bound_coverage':{'framing_allowance':FRAMING_ALLOWANCE,'covered_including_margin':sum(m>=0 for m in margins),
                          'total':len(margins),'minimum_remaining_margin':min(margins)},
        'largest_prompt':{'counted_tokens':max(tokens),'byte_bound':max(r['input_bound'] for r in records),'tier_limit':100000},
        'by_turns':by_turns,'limits':vars(Limits()),'configuration':agent.request_kwargs(PINNED_MODEL),
        'worst_scripted_reserved_cost_usd':worst_reserved/NANODOLLARS_PER_USD,
        'theoretical_cost_usd':{'per_case':CASE_MAX_NANODOLLARS/NANODOLLARS_PER_USD,
                              'all_128':CASE_MAX_NANODOLLARS*128/NANODOLLARS_PER_USD},
        'generation_calls':0,'spent_usd':0,
        'limitations':['count_tokens estimates input; it is not generated-response usage.',
            'Histories use simulated responses without real Haiku thinking blocks; actual histories may grow differently.',
            'Fitting 90/90 eight-turn replays proves neither completion, time compliance nor correct tool use by Haiku.',
            'No paid development pilot or 5C execution; independent verification remains pending.']}


def count(directory):
    logging.disable(logging.CRITICAL)
    os.umask(0o077)
    prepared=json.loads((directory/'prepared.json').read_text())
    if prepared['model']!=PINNED_MODEL or prepared['development_sha256']!=DEVELOPMENT_SHA256:
        raise ValueError('Unrecognized development preparation')
    if sha256(directory/'requests.json')!=prepared['requests_sha256']:raise ValueError('Request index changed')
    records=json.loads((directory/'requests.json').read_text())
    if len(records)!=2970:raise ValueError('Incomplete preparation')
    parameters=[]
    # Validate all inputs before retrieving any credential or constructing a client.
    for row in records:
        path=directory/'requests'/row['file']
        if path.parent!=directory/'requests' or sha256(path)!=row['body_sha256']:raise ValueError('Request changed')
        body=json.loads(path.read_text());params=count_parameters(body)
        if hashlib.sha256(wire(params)).hexdigest()!=row['count_body_sha256']:raise ValueError('Count payload changed')
        if request_bound(body,PINNED_MODEL)!=(row['input_bound'],row['output_bound']):raise ValueError('Bound changed')
        parameters.append(params)
    target=directory/'count-rows.jsonl'
    # Exclusive output prevents automatic resumption after uncertain transport errors.
    with target.open('x') as log:
        state={'status':'starting','http_requests_made':0,'counted':0,'generation_calls':0,'spent_usd':0}
        transport=None
        try:
            result=subprocess.run(['security','find-generic-password','-s','anthropic-api-key','-w'],
                capture_output=True,check=False)
            if result.returncode:raise RuntimeError('Keychain credential unavailable')
            credential=result.stdout.decode().strip();del result
            if not credential:raise RuntimeError('Empty Keychain credential')
            transport=CountOnlyTransport(httpx.HTTPTransport(retries=0))
            client=anthropic.Anthropic(api_key=credential,base_url='https://api.anthropic.com',max_retries=0,
                http_client=httpx.Client(transport=transport,follow_redirects=False,trust_env=False),timeout=30.)
            del credential
            counted=[];last_started=0.
            with client:
                for i,(row,params) in enumerate(zip(records,parameters)):
                    for attempt in range(3):
                        time.sleep(max(0.,.02-(time.monotonic()-last_started)))
                        last_started=time.monotonic()
                        try:
                            response=client.messages.count_tokens(**params)
                            break
                        except anthropic.APIStatusError as error:
                            state['last_http_status']=error.status_code
                            if error.status_code!=429 or attempt==2:raise
                            delay=retry_delay(error.response.headers.get('retry-after'))
                            state['rate_limit_retries']=state.get('rate_limit_retries',0)+1
                            time.sleep(delay)
                    n=response.input_tokens
                    if type(n) is not int or n<0:raise ValueError('Invalid count')
                    measurement={'request_index':i,'input_tokens':n,'body_sha256':row['body_sha256']}
                    log.write(json.dumps(measurement)+'\n');log.flush();counted.append(measurement)
                    state.update(status='counting',http_requests_made=transport.requests_made,counted=len(counted))
                    if n+FRAMING_ALLOWANCE>row['input_bound']:raise ValueError('Byte bound does not cover count plus framing')
                    if len(counted)%100==0:
                        write_json(directory/'count-state.json',state);print(json.dumps(state),flush=True)
            state['status']='complete';write_json(directory/'count-state.json',state)
            summary=aggregate(directory,records,counted,transport.requests_made)
            write_json(directory/'summary.json',summary)
            print(json.dumps({'status':'complete','http_requests_made':transport.requests_made,
                              'summary_sha256':sha256(directory/'summary.json'),'spent_usd':0}),flush=True)
        except Exception as error:
            # Never serialize exceptions, HTTP responses, clients or headers.
            state.update(status='stopped',error_type=type(error).__name__,
                         http_requests_made=transport.requests_made if transport else 0)
            write_json(directory/'count-state.json',state);print(json.dumps(state),flush=True)
            return 2
    return 0


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    prep=sub.add_parser('prepare')
    for field in ('source','development','output'):prep.add_argument('--'+field,type=Path,required=True)
    live=sub.add_parser('count');live.add_argument('--directory',type=Path,required=True)
    args=p.parse_args()
    if args.mode=='prepare':prepare(args.source,args.development,args.output);return 0
    return count(args.directory)


if __name__=='__main__':raise SystemExit(main())
