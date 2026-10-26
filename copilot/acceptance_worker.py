"""One future 5C case, one attempt; parent process enforces wall timeout.

Receives only a scientific input path and monetary ceiling. No labels, case
family, expected answers or custody IDs are arguments. Budget defaults to zero.
"""
import argparse
import hashlib
import math
import json
import os
from pathlib import Path
import time

from copilot import agent
from copilot.budget import Budget,Limits,PINNED_MODEL,CASE_CEILING_USD,AUTHORIZED_EFFORTS,BudgetStop
from copilot.acceptance_io import write_json,sanitize


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True)
    p.add_argument('--candidate',type=Path)
    p.add_argument('--protocol-dir',type=Path)
    p.add_argument('--progress',type=Path,required=True)
    p.add_argument('--result',type=Path,required=True)
    p.add_argument('--budget-usd',type=float,default=0.)
    p.add_argument('--seconds',type=float,default=Limits().seconds)
    p.add_argument('--effort',choices=AUTHORIZED_EFFORTS,default='low')
    p.add_argument('--expected-sha256')
    p.add_argument('--deadline-monotonic',type=float)
    p.add_argument('--audit-path',type=Path);p.add_argument('--alias');p.add_argument('--phase')
    p.add_argument('--campaign-dir',type=Path)
    args=p.parse_args()
    if not 0<=args.budget_usd<=CASE_CEILING_USD or not 0<args.seconds<=Limits().seconds:
        p.error('Outside frozen per-case limits')
    if args.budget_usd and (args.candidate is None or args.protocol_dir is None):
        p.error('Paid execution requires the registered installed identity and protocol')
    if args.budget_usd:
        from copilot.campaign import authorize_worker
        try:authorize_worker(args)
        except (ValueError,OSError,KeyError,TypeError):p.error('Paid worker requires an open campaign claim and a unique registered row')
    budget=Budget(PINNED_MODEL,Limits(usd=args.budget_usd,seconds=args.seconds),effort=args.effort)
    if args.deadline_monotonic is not None:
        if not math.isfinite(args.deadline_monotonic):p.error('Invalid deadline')
        budget.started=min(budget.started,args.deadline_monotonic-args.seconds)
    recorded={}
    def progress(report,ledger):
        write_json(args.progress,sanitize({'report':report,'execution_budget':ledger}))
        if args.audit_path:
            for index,event in enumerate(ledger['events']):
                if recorded.get(index)==event['status']:continue
                # fsync is inside the guard callback: failure prevents the POST.
                fd=os.open(args.audit_path,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
                with os.fdopen(fd,'a') as stream:
                    stream.write(json.dumps({'phase':args.phase,'alias':args.alias,'call':index+1,
                        'event':event,'cost_certified':ledger['cost_certified']},allow_nan=False)+'\n')
                    stream.flush();os.fsync(stream.fileno())
                recorded[index]=event['status']
    result=agent.explanation.result(status='technical_error')
    progress(result,budget.snapshot())
    try:
        if args.candidate:
            from copilot.candidate_identity import verify
            verify(args.candidate,args.protocol_dir,effort=args.effort,require_installed=bool(args.budget_usd))
        payload=Path(args.input).read_bytes()
        if args.expected_sha256 and hashlib.sha256(payload).hexdigest()!=args.expected_sha256:
            result['completion_code']='input_identity_mismatch'
        elif budget.remaining_seconds()<=0:
            result['completion_code']='case_timeout'
        else:
            result=agent.run_structured(payload,model=PINNED_MODEL,budget=budget,progress=progress,effort=args.effort)
    except Exception:
        result['completion_code']='worker_preflight_failed'
    result['execution_budget']=budget.snapshot()
    write_json(args.result,sanitize(result))
    return 0


if __name__=='__main__':raise SystemExit(main())
