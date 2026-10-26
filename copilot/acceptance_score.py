"""Score persisted, sealed 5C outputs. Labels are first read inside score_sealed.

Mechanical fidelity and relational redshift checks are distinct from scientific
accuracy, which remains subject to independent review under the frozen rubric.
"""
import argparse
import json
import math
import time
import hashlib
from pathlib import Path

from copilot import explanation,rag,review
from copilot.acceptance_io import sha256,write_json,seal_record_path


def wilson(passed,total):
    if not total:return {'passed':passed,'total':total,'rate':None,'wilson_95':None}
    z=1.959963984540054;p=passed/total;d=1+z*z/total
    center=(p+z*z/(2*total))/d;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return {'passed':passed,'total':total,'rate':p,'wilson_95':[center-half,center+half]}


def validate_seal(directory,seal_record=None):
    directory=Path(directory)
    record=Path(seal_record) if seal_record is not None else seal_record_path(directory)
    if record.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Seal registration must be outside output directory')
    registered=json.loads(record.read_text())
    seal_hash=sha256(directory/'seal.json')
    if (registered.get('schema')!='batch5c-seal-record-v1' or
            registered.get('seal_sha256')!=seal_hash):
        raise ValueError('Seal differs from external registration')
    seal=json.loads((directory/'seal.json').read_text())
    if seal.get('schema')!='batch5c-output-seal-v1':raise ValueError('Invalid output seal')
    for name in ('manifest','outputs','summary'):
        if sha256(directory/(name+'.json'))!=seal[name+'_sha256']:raise ValueError('Sealed output changed')
    rows=json.loads((directory/'outputs.json').read_text())
    manifest=json.loads((directory/'manifest.json').read_text())
    if len(rows)!=seal['requested'] or len(rows)!=seal['persisted_rows'] or len(rows)!=manifest['requested']:
        raise ValueError('Missing requested rows')
    if [r['alias'] for r in rows]!=[r['alias'] for r in manifest['input_identities']]:raise ValueError('Requested identities changed')
    summary=json.loads((directory/'summary.json').read_text())
    if summary.get('outputs_sha256')!=seal['outputs_sha256']:
        raise ValueError('Summary output identity mismatch')
    return rows,manifest,seal,seal_hash,time.time_ns()


def mechanical(report):
    if not report:return {'prediction_available':False,'model_z_preserved':False,'faithful':False,'citation_mentions':0,'valid_citation_mentions':0,'candidate_arithmetic':False}
    observations=report.get('observations',[])
    predictions=[o['result'] for o in observations if o['tool']=='predict_redshift' and not o.get('error')]
    try:
        official=explanation.canonical_z(predictions[0]) if predictions else None
    except (KeyError,ValueError,TypeError):official=None
    preserved=official is not None and report.get('model_z')==official and report.get('prediction')==predictions[0]
    citations=report.get('citations',[])
    valid=sum(c.get('id') in rag.valid_ids() for c in citations)
    faithful=False;arithmetic=True
    try:
        selected=[e['observation_id'] for e in report.get('explanation',[])]
        expected=explanation.result(predictions[0] if predictions else None,observations,selected,status=report['status'],
            violations=report.get('policy_violations',[]),reference_ids=[c['id'] for c in citations])
        faithful=bool(selected) and all(report.get(k)==expected[k] for k in ('status','explanation','alternatives','citations'))
        for alternative in report.get('alternatives',[]):
            value=alternative['lambda_observed']/alternative['lambda_rest']-1
            arithmetic &= value>=0 and math.isfinite(value) and math.isclose(alternative['z'],value,abs_tol=1e-6,rel_tol=1e-6)
    except (KeyError,ValueError,TypeError,ZeroDivisionError):
        faithful=False;arithmetic=False
    units=len(report.get('explanation',[]))+len(report.get('alternatives',[]))
    return {'template_evidence_units':units,'faithful_template_evidence_units':units if faithful else 0,
            'prediction_available':official is not None,'model_z_preserved':preserved,'faithful':faithful,
            'citation_mentions':len(citations),'valid_citation_mentions':valid,'candidate_arithmetic':bool(arithmetic)}


def score_sealed(directory,labels_path,*,review_path=None,seal_record=None,output_path=None):
    target=Path(output_path) if output_path else Path(directory).with_name(Path(directory).name+'.scores.json')
    if target.resolve().is_relative_to(Path(directory).resolve()):raise ValueError('Scores must be outside sealed output directory')
    if target.exists():raise FileExistsError('Preserve earlier score artifacts; choose a new output path')
    rows,manifest,seal,seal_hash,verified_ns=validate_seal(directory,seal_record)
    labels_read_started_ns=time.time_ns()
    label_bytes=Path(labels_path).read_bytes()
    labels_loaded_ns=time.time_ns()
    labels=json.loads(label_bytes)
    if set(labels)!={'schema','cases'} or labels['schema']!='batch5c-scoring-v1':raise ValueError('Invalid scoring view')
    indexed={c['alias']:c for c in labels['cases']}
    if len(indexed)!=len(labels['cases']) or set(indexed)!={r['alias'] for r in rows}:raise ValueError('Labels must cover every requested case exactly once')
    if manifest['mode']=='proposal' and (sum(c['kind']=='real' for c in indexed.values())!=80 or sum(c['kind']=='synthetic' for c in indexed.values())!=48):
        raise ValueError('Frozen real/synthetic denominators changed')
    reviews=json.loads(Path(review_path).read_text()) if review_path else {}
    scored=[]
    for row in rows:
        label=indexed[row['alias']];report=row.get('result');checks=mechanical(report)
        oracle=label['expected_answer'];state=row['status']
        if oracle.get('must_reject_input'):
            completion=state=='invalid_input' and report is not None and report.get('model_z') is None and not report.get('alternatives') and not any(not o.get('error') for o in report.get('observations',[]))
        else:
            completion=state in {'complete','ambiguous','insufficient_data'} and checks['prediction_available'] and checks['model_z_preserved'] and checks['faithful']
        abstention_required=bool(oracle.get('must_abstain_unique_z'))
        abstention=(state in {'ambiguous','insufficient_data'} and checks['model_z_preserved']) if not oracle.get('must_reject_input') else completion
        # No detection/centroid oracle is invented: z candidates are calculations
        # from measured lambda_obs (§5). SNR=0 cannot reveal an injected center.
        # Recipe arithmetic is checked separately by the mechanism tests.
        bundle=reviews.get(row['alias'],{})
        recipe_arithmetic=None
        if 'admissible_z' in oracle:
            peak=label['recipe']['peak_angstrom']
            expected=[peak/rest-1 for rest in (1215.7,3727.1,5006.8,6562.8) if peak>=rest]
            recipe_arithmetic=(len(expected)==len(oracle['admissible_z']) and
                all(math.isclose(a,b,abs_tol=1e-6,rel_tol=1e-6) for a,b in zip(expected,oracle['admissible_z'])))
        scorer=review.score_annotation_pair if bundle.get('schema')=='batch5c-ai-case-review-v1' else review.score_claim_review
        semantic=scorer(bundle.get('claims',[]),bundle.get('first'),bundle.get('second'),bundle.get('adjudication'))
        scored.append({'alias':row['alias'],'kind':label['kind'],'family':label.get('family','real'),
            'cnn_exposure':label.get('cnn_exposure','unspecified'),'status':state,'checks':checks,
            'completion':bool(completion),'recipe_arithmetic_integrity':recipe_arithmetic,'abstention_required':abstention_required,'abstention':bool(abstention),
            'semantic':semantic,'latency_seconds':row['latency_seconds']})
    def summarize(group):
        m=[r for r in group if r['checks']['prediction_available']]
        valid_inputs=[r for r in group if not indexed[r['alias']]['expected_answer'].get('must_reject_input')]
        a=[r for r in group if r['abstention_required']]
        semantic_pending=sum(r['semantic']['semantic_status']!='reviewed' for r in group)
        semantic_metrics={}
        for name,numerator,denominator in [('textual_support','textual_supported','textual_pairs'),
                ('scientific_accuracy','scientific_correct','scientific_claims'),
                ('unsupported_claims','unsupported_claims','factual_claims')]:
            n=sum(r['semantic'][numerator] for r in group);d=sum(r['semantic'][denominator] for r in group)
            semantic_metrics[name]={'numerator':n,'denominator':d,'rate':n/d if d and not semantic_pending else None}
        return {'requested':len(group),'semantic_metrics':semantic_metrics,'completion':wilson(sum(r['completion'] for r in group),len(group)),
            'model_z':wilson(sum(r['checks']['model_z_preserved'] for r in m),len(m)),
            'prediction_coverage':wilson(len(m),len(valid_inputs)),
            'template_evidence_units':sum(r['checks'].get('template_evidence_units',0) for r in group),
            'faithful_template_evidence_units':sum(r['checks'].get('faithful_template_evidence_units',0) for r in group),
            'tool_fidelity_by_case':wilson(sum(r['checks']['faithful'] for r in valid_inputs),len(valid_inputs)),
            'abstention':wilson(sum(r['abstention'] for r in a),len(a)),
            'citation_mentions':sum(r['checks']['citation_mentions'] for r in group),
            'valid_citation_mentions':sum(r['checks']['valid_citation_mentions'] for r in group),
            'semantic_review_pending_cases':sum(r['semantic']['semantic_status']!='reviewed' for r in group),
            'unsupported_claims':sum(r['semantic']['unsupported_claims'] for r in group),
            'critical_scientific_errors':sum(r['semantic']['critical_errors'] for r in group),
            'missing_required_citations':sum(r['semantic']['missing_required_citations'] for r in group),
            'status_counts':{s:sum(r['status']==s for r in group) for s in sorted({r['status'] for r in group})}}
    result={'schema':'batch5c-score-v1','mode':manifest['mode'],'outputs_sha256':seal['outputs_sha256'],
            'labels_sha256':hashlib.sha256(label_bytes).hexdigest(),'labels_loaded_ns':labels_loaded_ns,
            'outputs_sealed_ns':seal['created_ns'],'seal_sha256':seal_hash,
            'seal_verified_ns':verified_ns,'labels_read_started_ns':labels_read_started_ns,
            'seal_verified_before_label_read':verified_ns<=labels_read_started_ns<=labels_loaded_ns,
            'global':summarize(scored),'strata':{key:{str(v):summarize([r for r in scored if r[key]==v]) for v in sorted({r[key] for r in scored},key=str)} for key in ('kind','family','cnn_exposure')},
            'rows':scored,'execution_summary':json.loads((Path(directory)/'summary.json').read_text()),
            'acceptance_status':'not_accepted; independent rubric, omissions and final installed identity require 5C review',
            'interpretation':['model_z preservation is a software guarantee, not LLM accuracy improvement.',
                'Template fidelity is a mechanical check, not semantic claim evaluation.',
                'Zero citation denominator is not success; missing external claims/citations require case-level review.',
                'Synthetic public recipes are mechanism checks, not blind acceptance.',
                'No catalog redshift is substituted for the official model output.']}
    from copilot.campaign import exclusive_json
    exclusive_json(target,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--labels',type=Path,required=True);p.add_argument('--reviews',type=Path)
    p.add_argument('--seal-record',type=Path,help='External registered seal hash; defaults to sibling <run>.seal-record.json')
    p.add_argument('--output',type=Path,help='New external score artifact; never overwritten')
    a=p.parse_args();result=score_sealed(a.run,a.labels,review_path=a.reviews,seal_record=a.seal_record,output_path=a.output);print(json.dumps(result['global']));return 0


if __name__=='__main__':raise SystemExit(main())
