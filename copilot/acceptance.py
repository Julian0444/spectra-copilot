"""Sealed, label-free execution for 5C. This module never opens scoring labels.

A custodian must prepare opaque scientific inputs separately. 5B-2 exercises
only invented simulations; it never prepares or runs the private acceptance.
"""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np

from copilot import explanation
from copilot.budget import (PINNED_MODEL, Limits, CASE_MAX_USD, CASE_MAX_NANODOLLARS,
                            TOTAL_CEILING_USD, CASE_COUNT, NANODOLLARS_PER_USD, nanodollars,
                            AUTHORIZED_EFFORTS, request_configuration)
from copilot.acceptance_io import sha256,write_json,sanitize,seal_record_path,register_seal

SCHEMA='batch5c-inputs-v1'
TERMINAL=explanation.STATES | {'timeout'}


def read_input_plan(path):
    plan=json.loads(Path(path).read_text())
    if set(plan)!={'schema','mode','inputs'} or plan['schema']!=SCHEMA or plan['mode'] not in {'proposal','simulation'}:
        raise ValueError('Only the label-free input schema is allowed')
    items=plan['inputs']
    if not items or (plan['mode']=='proposal' and len(items)!=CASE_COUNT):raise ValueError('Frozen requested population is 128')
    aliases=[]
    for item in items:
        if set(item)!={'alias','input_path','input_sha256'}:raise ValueError('Input plan cannot carry labels or expected answers')
        alias=item['alias'];aliases.append(alias)
        if not re.fullmatch('[0-9a-f]{24}',alias) or alias.isdecimal():raise ValueError('Use ephemeral random hex aliases')
        if not re.fullmatch('[0-9a-f]{64}',item['input_sha256']):raise ValueError('Input hash required')
        if not Path(item['input_path']).is_absolute():raise ValueError('Absolute private input path required')
    if len(set(aliases))!=len(aliases):raise ValueError('Duplicate request alias')
    return plan


def _failed(code,progress=None,paid_ceiling=0):
    report=(progress or {}).get('report') or explanation.result(status='technical_error')
    report['status']='explanation_incomplete' if report.get('model_z') is not None else 'technical_error'
    report['completion_code']=code
    budget=(progress or {}).get('execution_budget')
    if budget is None:
        budget={'calls':0,'known_usd':0.,'reserved_usd':0.,'usd':0. if paid_ceiling==0 else None,'cost_certified':paid_ceiling==0}
    elif budget.get('reserved_usd',0)>0 or not budget.get('cost_certified',False):
        budget['cost_certified']=False;budget['usd']=None
    report['execution_budget']=budget
    return report


def run_worker(item,directory,usd,seconds=Limits().seconds,command=None,candidate=None,protocol_dir=None,effort='low'):
    directory=Path(directory);progress=directory/(item['alias']+'.progress.json');result=directory/(item['alias']+'.result.json')
    args=command or [sys.executable,'-m','copilot.acceptance_worker','--input',item['input_path'],
        '--progress',str(progress),'--result',str(result),'--budget-usd',str(usd),'--seconds',str(seconds),'--effort',effort,
        '--expected-sha256',item['input_sha256'],'--deadline-monotonic',str(time.monotonic()+seconds)]
    if candidate and command is None:args+=['--candidate',str(candidate),'--protocol-dir',str(protocol_dir)]
    if command is None:
        from copilot.budget import Budget
        # No POST can precede a durable reservation. A killed import/preflight
        # therefore has known zero cost until the worker updates this record.
        write_json(progress,{'report':explanation.result(status='technical_error'),
                             'execution_budget':Budget(limits=Limits(usd=usd),effort=effort).snapshot()})
    try:
        process=subprocess.run(args,capture_output=True,text=True,timeout=seconds)
        if process.returncode==0 and result.exists():return json.loads(result.read_text()),False
        code='worker_failed'
    except subprocess.TimeoutExpired:
        code='case_timeout'
    prior=json.loads(progress.read_text()) if progress.exists() else None
    return _failed(code,prior,usd),code=='case_timeout'


def summarize(rows):
    times=[r['latency_seconds'] for r in rows if r['status']!='pending']
    ledgers=[r['result'].get('execution_budget') for r in rows if r.get('result') is not None]
    certified=True;known_nano=0
    for ledger in ledgers:
        if ledger is None:
            certified=False;continue
        try:
            value=nanodollars(ledger.get('known_usd',0))
            reserved=nanodollars(ledger.get('reserved_usd',0))
            known_nano+=value
            certified &= (ledger.get('cost_certified') is True and ledger.get('usd') is not None
                          and nanodollars(ledger['usd'])==value and reserved==0
                          and ledger.get('known_nanodollars',value)==value
                          and ledger.get('reserved_nanodollars',reserved)==reserved)
        except (ValueError,TypeError,ArithmeticError):
            certified=False
    known=known_nano/NANODOLLARS_PER_USD
    return {'requested':len(rows),'status_counts':{s:sum(r['status']==s for r in rows) for s in sorted(TERMINAL|{'pending'})},
        'attempted':sum(r['attempts'] for r in rows),'attempts_per_case_max':max(r['attempts'] for r in rows),
        'llm_calls':sum((l or {}).get('calls',0) for l in ledgers),'automatic_retries':0,
        'cost':{'certified':certified,'total_usd':known if certified else None,'known_usd':known,'known_nanodollars':known_nano,
                'mean_per_requested':known/len(rows) if certified else None},
        'latency':{'n':len(times),'p50':float(np.quantile(times,.5)) if times else None,
                   'p95':float(np.quantile(times,.95)) if times else None,'maximum':max(times) if times else None},
        'scientific_accuracy':'pending_independent_review','labels_loaded':False}


def execute_plan(plan_path,output,*,usd=0.,runner=None,candidate=None,seconds=Limits().seconds,protocol_dir=None,effort='low'):
    """Persist every requested row first, then execute once and seal all outputs.

    `runner` is only accepted for explicit simulations. Production uses a fresh
    subprocess per case and kills it at the wall deadline, preserving progress.
    """
    request_configuration(effort)
    plan=read_input_plan(plan_path);output=Path(output)
    if not math.isfinite(usd) or not 0<=usd<=TOTAL_CEILING_USD or not 0<seconds<=Limits().seconds:raise ValueError('Outside frozen execution limits')
    authorized_nanodollars=nanodollars(usd)
    if plan['mode']=='simulation' and usd:raise ValueError('Simulation cannot authorize paid calls')
    if plan['mode']=='proposal' and (runner is not None or candidate is None):raise ValueError('Proposal requires fixed identity and real isolated worker')
    protocol_dir=Path(protocol_dir or Path(__file__).resolve().parent.parent/'docs')
    if plan['mode']=='proposal':
        from copilot.candidate_identity import verify
        verify(candidate,protocol_dir,effort=effort)
    if seal_record_path(output).exists() or seal_record_path(output).is_symlink():
        raise FileExistsError('Preserve the external seal registration')
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    traces=output/'traces';traces.mkdir(mode=0o700)
    identity={'schema':'batch5c-execution-v1','mode':plan['mode'],'model':PINNED_MODEL,'effort':effort,
              'input_plan_sha256':sha256(plan_path),'requested':len(plan['inputs']),
              'input_identities':[{k:v for k,v in item.items() if k!='input_path'} for item in plan['inputs']],
              'candidate_sha256':sha256(candidate) if candidate else None,'authorized_ceiling_usd':usd,
              'per_case_estimated_maximum_usd':CASE_MAX_USD,'timeout_seconds':seconds,'attempts':1,'retries':0}
    write_json(output/'manifest.json',identity)
    rows=[{'alias':item['alias'],'status':'pending','attempts':0,'latency_seconds':None,'result':None} for item in plan['inputs']]
    stop_reason=None
    def persist():
        write_json(output/'outputs.json',rows)
        summary=summarize(rows);summary['mode']=plan['mode'];summary['simulated_usage']=plan['mode']=='simulation';summary['stop_reason']=stop_reason;summary['outputs_sha256']=sha256(output/'outputs.json')
        write_json(output/'summary.json',summary)
    persist()
    try:
        for item,row in zip(plan['inputs'],rows):
            summary=summarize(rows)
            if not summary['cost']['certified']:
                stop_reason='usage_uncertified';break
            remaining=authorized_nanodollars-summary['cost']['known_nanodollars']
            if usd and remaining<CASE_MAX_NANODOLLARS:
                stop_reason='aggregate_budget_exhausted';break
            row['attempts']=1;start=time.monotonic();persist()
            try:
                if sha256(item['input_path'])!=item['input_sha256']:raise ValueError('Input identity mismatch')
                if runner is not None:
                    result=runner(item['input_path']);timed_out=False
                else:
                    result,timed_out=run_worker(item,traces,CASE_MAX_USD if usd else 0.,seconds,candidate=candidate,protocol_dir=protocol_dir,effort=effort)
                if result.get('status') not in TERMINAL:raise ValueError('Invalid result state')
                row['result']=sanitize(result)
                row['status']='timeout' if timed_out else result['status']
            except (KeyboardInterrupt,SystemExit):
                row['result']=_failed('execution_interrupted',paid_ceiling=CASE_MAX_USD if usd else 0.)
                row['status']='technical_error';stop_reason='execution_interrupted';break
            except Exception:
                row['result']=_failed('case_execution_failed',paid_ceiling=CASE_MAX_USD if usd else 0.)
                row['status']='technical_error'
            finally:
                row['latency_seconds']=time.monotonic()-start
                if row['status']=='timeout':row['latency_seconds']=seconds
                persist()
            if row['result'].get('completion_code')=='paid_budget_zero':
                stop_reason='paid_budget_zero';break
    finally:
        persist()
        # Scoring may load labels only after checking this seal and both hashes.
        write_json(output/'seal.json',{'schema':'batch5c-output-seal-v1','manifest_sha256':sha256(output/'manifest.json'),
            'outputs_sha256':sha256(output/'outputs.json'),'summary_sha256':sha256(output/'summary.json'),
            'requested':len(rows),'persisted_rows':len(rows),'created_ns':time.time_ns()})
        register_seal(output)
    return summarize(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--protocol-dir',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--budget-usd',type=float,default=0.)
    p.add_argument('--effort',choices=AUTHORIZED_EFFORTS,default='low')
    a=p.parse_args();summary=execute_plan(a.inputs,a.output,usd=a.budget_usd,candidate=a.candidate,protocol_dir=a.protocol_dir,effort=a.effort)
    print(json.dumps(summary));return 0 if summary['status_counts']['pending']==0 else 2


if __name__=='__main__':raise SystemExit(main())
