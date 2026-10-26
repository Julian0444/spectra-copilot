"""Operational development comparison, separate from acceptance/scientific scoring."""
import argparse
import json
from pathlib import Path

from copilot import explanation
from copilot.acceptance import summarize
from copilot.acceptance_io import sha256
from copilot.acceptance_score import mechanical,validate_seal
from copilot.budget import Limits,CASE_MAX_NANODOLLARS,nanodollars

VALID={'complete','ambiguous','insufficient_data'}
CAUTION={'complete':0,'ambiguous':1,'insufficient_data':2}


def choose(metrics):
    if set(metrics)!={'low','medium'}:raise ValueError('Both frozen variants required')
    if not all(m['cost_certified'] for m in metrics.values()):raise ValueError('Cannot choose with uncertified cost')
    return min(metrics,key=lambda e:(-metrics[e]['valid_reports'],metrics[e]['max_tokens_or_refusal'],
                                    metrics[e]['known_nanodollars'],e!='low'))


def measure_row(row,label):
    report=row.get('result') or {};state=row['status'];checks=mechanical(report)
    ledger=report.get('execution_budget') or {};events=ledger.get('events',[])
    oracle=label.get('expected_answer',{});invalid=bool(oracle.get('must_reject_input'))
    observations=report.get('observations',[])
    minimum='complete'
    for obs in observations:
        if obs.get('tool')!='identify_spectral_lines' or obs.get('error'):continue
        data=obs['result'];level='insufficient_data' if data.get('assessment')=='insufficient_line_evidence' else 'ambiguous' if data.get('ambiguous') else 'complete'
        if CAUTION[level]>CAUTION[minimum]:minimum=level
    obligations={'fidelity':checks['faithful'],'model_z':checks['model_z_preserved'],
        'citation_ids':checks['citation_mentions']==checks['valid_citation_mentions'],
        'candidate_arithmetic':checks['candidate_arithmetic'],
        'minimum_caution':state in VALID and CAUTION[state]>=CAUTION[minimum],
        'expected_abstention':not oracle.get('must_abstain_unique_z') or state in {'ambiguous','insufficient_data'}}
    cost=summarize([row])['cost']
    zero=(cost['certified'] and cost['known_nanodollars']==0 and ledger.get('calls')==0 and not events)
    correct_invalid=(invalid and state=='invalid_input' and report.get('model_z') is None
        and not report.get('prediction') and not report.get('alternatives')
        and not any(not o.get('error') for o in observations) and zero)
    code=report.get('completion_code')
    return {'alias':row['alias'],'status':state,'completion_code':code,'expected_invalid':invalid,
        'all_obligations':bool(state in VALID and all(obligations.values())),
        'obligations':obligations,'minimum_caution':minimum,'correct_invalid':bool(correct_invalid),
        'prediction_available':checks['prediction_available'],'model_z_preserved':checks['model_z_preserved'],
        'model_z':report.get('model_z'),'turns':ledger.get('calls',0),
        'tools':[o['tool'] for o in observations], 'analysis_calls':report.get('analysis_calls'),
        'stop_reasons':[e.get('stop_reason') for e in events],
        'tokens':[{k:e.get(k) for k in ('input_bound','output_bound','input_tokens','output_tokens','status')} for e in events],
        'beta_header_accepted':bool(events) and all(e.get('beta_header') and e.get('response_received') for e in events),
        'input_tokens':ledger.get('input_tokens',0),'output_tokens':ledger.get('output_tokens',0),
        'cost_certified':cost['certified'],'known_nanodollars':cost['known_nanodollars'],
        'within_case_cap':cost['certified'] and cost['known_nanodollars']<=CASE_MAX_NANODOLLARS,
        'reserved_nanodollars':ledger.get('reserved_nanodollars',nanodollars(ledger.get('reserved_usd',0))),
        'prompt_tier_exceeded':code=='prompt_tier_exceeded', 'latency_seconds':row.get('latency_seconds')}


def aggregate(rows):
    valid=[r for r in rows if not r['expected_invalid']];invalid=[r for r in rows if r['expected_invalid']]
    certified=all(r['cost_certified'] for r in rows)
    metrics={'requested':len(rows),'valid_inputs':len(valid),'invalid_inputs':len(invalid),
        'valid_reports':sum(r['all_obligations'] for r in valid),
        'max_tokens_or_refusal':sum(r['status'] in {'max_tokens','refusal'} for r in valid),
        'status_counts':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},
        'cost_certified':certified,'known_nanodollars':sum(r['known_nanodollars'] for r in rows),
        'llm_calls':sum(r['turns'] for r in rows)}
    checks={'population':len(valid)==11 and len(invalid)==1,
        'valid_reports':metrics['valid_reports']>=10,'max_tokens_or_refusal':metrics['max_tokens_or_refusal']<=1,
        'no_other_failures':all(r['status'] in VALID|{'max_tokens','refusal'} for r in valid),
        'invalid_zero_calls':len(invalid)==1 and invalid[0]['correct_invalid'],
        'certified_cost':certified and all(r['within_case_cap'] for r in rows),
        'no_inflight_or_prompt_tier':all(r['reserved_nanodollars']==0 and not r['prompt_tier_exceeded'] for r in rows),
        'model_z_preserved':all(r['model_z_preserved'] for r in rows if r['prediction_available'])}
    metrics.update(gate_checks=checks,gate_passed=all(checks.values()))
    return metrics


def score(run,labels_path):
    rows,manifest,seal,seal_hash,_=validate_seal(run)
    if manifest['mode']!='development':raise ValueError('Pilot scorer accepts development only')
    labels=json.loads(Path(labels_path).read_text())
    if labels.get('schema')!='batch5c-development-scoring-v1':raise ValueError('Development labels required')
    indexed={c['alias']:c for c in labels['cases']}
    if len(indexed)!=len(rows) or set(indexed)!={r['alias'] for r in rows}:raise ValueError('All development rows required')
    scored=[]
    for row,item in zip(rows,manifest['input_identities']):
        label=indexed[row['alias']]
        if label['effort']!=item['effort']:raise ValueError('Variant label mismatch')
        scored.append({**measure_row(row,label),'effort':item['effort'],'slot':label['slot']})
    variants={e:aggregate([r for r in scored if r['effort']==e]) for e in sorted({r['effort'] for r in scored})}
    chosen=choose(variants) if manifest['phase']=='pilot' else manifest['effort']
    return {'schema':'batch5c-operational-score-v1','phase':manifest['phase'],'seal_sha256':seal_hash,
        'outputs_sha256':seal['outputs_sha256'],'labels_sha256':sha256(labels_path),
        'variant_identities':manifest['variant_identities'],'variants':variants,'chosen_effort':chosen,
        'gate_passed':variants[chosen]['gate_passed'],'rows':scored,
        'interpretation':'Operational development comparison only; no redshift accuracy used; selection precedes gate.'}


def main():
    from copilot.campaign import exclusive_json
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','labels','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=score(a.run,a.labels);exclusive_json(a.output,result)
    print(json.dumps({'chosen_effort':result['chosen_effort'],'gate_passed':result['gate_passed'],'variants':result['variants']}))


if __name__=='__main__':main()
