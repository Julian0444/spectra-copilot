"""Persist a bounded SDK simulation. MockTransport cannot contact the network."""
import argparse
import json
import os
from pathlib import Path

import anthropic
import httpx
from copilot.budget import Budget, Limits, BudgetStop, PINNED_MODEL
from copilot.budget import guard_sdk


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    requests=[]
    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'simulated','type':'message','role':'assistant','model':PINNED_MODEL,
            'content':[],'stop_reason':'end_turn','stop_sequence':None,'usage':{'input_tokens':5000,'output_tokens':10}})
    budget=Budget(limits=Limits(usd=.018))
    client=anthropic.Anthropic(api_key='synthetic-unused',max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    stopped=None
    with guard_sdk(client,budget):
        for _ in range(3):
            try:client.beta.messages.create(model=PINNED_MODEL,max_tokens=512,messages=[{'role':'user','content':'x'*2000}])
            except BudgetStop as exc:stopped=exc.code;break
    result={'mode':'offline SDK MockTransport simulation','remote_calls':0,'paid_usd':0,
            'simulated_http_calls':len(requests),'stopped_before_call':len(requests)+1,
            'stop_reason':stopped,'ledger':budget.snapshot()}
    assert len(requests)==2 and stopped=='usd_budget_exhausted' and budget.spent+budget.reserved_usd<=budget.cap
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='ledger'}))


if __name__=='__main__':main()
