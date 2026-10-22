"""One future 5C case, one attempt; parent process enforces wall timeout.

Receives only a scientific input path and monetary ceiling. No labels, case
family, expected answers or custody IDs are arguments. Budget defaults to zero.
"""
import argparse
from pathlib import Path

from copilot import agent
from copilot.budget import Budget,Limits,PINNED_MODEL,CASE_CEILING_USD
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
    args=p.parse_args()
    if not 0<=args.budget_usd<=CASE_CEILING_USD or not 0<args.seconds<=Limits().seconds:
        p.error('Outside frozen per-case limits')
    if args.budget_usd and (args.candidate is None or args.protocol_dir is None):
        p.error('Paid execution requires the registered installed identity and protocol')
    if args.candidate:
        from copilot.candidate_identity import verify
        verify(args.candidate,args.protocol_dir)
    budget=Budget(PINNED_MODEL,Limits(usd=args.budget_usd,seconds=args.seconds))
    def progress(report,ledger):
        write_json(args.progress,sanitize({'report':report,'execution_budget':ledger}))
    result=agent.run_structured(args.input,model=PINNED_MODEL,budget=budget,progress=progress)
    write_json(args.result,sanitize(result))
    return 0


if __name__=='__main__':raise SystemExit(main())
