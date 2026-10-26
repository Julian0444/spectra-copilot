"""Register the development choice once; gate later phases without reading labels."""
import argparse
import json
from pathlib import Path

from copilot.acceptance_io import sha256
from copilot.acceptance_score import validate_seal
from copilot.campaign import exclusive_json,locked
from copilot.pilot_score import score,choose


def check_transition(phase,effort,llm_path,decision,final,correction=None):
    if effort!=decision['chosen_effort']:raise ValueError('Effort differs from registered pilot choice')
    if phase=='confirmation':
        if llm_path==decision['pilot_llm_path_sha256']:raise ValueError('Confirmation requires a demonstrated code-path correction')
        if (not correction or correction.get('old_llm_path_sha256')!=decision['pilot_llm_path_sha256']
                or correction.get('new_llm_path_sha256')!=llm_path
                or not all(correction.get(k) for k in ('description','reproduction_sha256','before_commit','after_commit'))):
            raise ValueError('Demonstrated correction record required')
    elif phase=='proposal':
        if final['effort']!=effort or final['llm_path_sha256']!=llm_path or not final['gate_passed']:
            raise ValueError('Final pilot code, effort and preparation gate required')
    else:raise ValueError('Unknown subsequent phase')


def read_assessment(root,phase):
    value=json.loads((root/(phase+'.assessment.json')).read_text())
    rows,manifest,seal,seal_hash,_=validate_seal(value['run'])
    closed=json.loads((root/(phase+'.close.json')).read_text())
    if not closed['certified'] or seal_hash!=closed['seal_sha256'] or seal_hash!=value['seal_sha256']:
        raise ValueError('Assessment does not match certified phase seal')
    if sha256(value['score_path'])!=value['score_sha256']:raise ValueError('Assessment score changed')
    metrics=json.loads(Path(value['score_path']).read_text())
    if metrics['seal_sha256']!=seal_hash or metrics['chosen_effort']!=value['effort'] or metrics['gate_passed']!=value['gate_passed']:
        raise ValueError('Assessment decision changed')
    identity=json.loads(Path(value['identity_path']).read_text())
    if (sha256(value['identity_path'])!=manifest['variant_identities'][value['effort']]
            or identity['llm_path_sha256']!=value['llm_path_sha256']):
        raise ValueError('Assessment identity changed')
    return value,metrics


def authorize(directory,phase,effort,candidate):
    root=Path(directory);decision=json.loads((root/'decision.json').read_text())
    pilot,metrics=read_assessment(root,'pilot')
    if decision!={'chosen_effort':choose(metrics['variants']),'pilot_llm_path_sha256':pilot['llm_path_sha256'],
                  'pilot_assessment_sha256':sha256(root/'pilot.assessment.json')}:
        raise ValueError('Registered decision changed')
    final=read_assessment(root,'confirmation')[0] if (root/'confirmation.claim.json').exists() else pilot
    correction=json.loads((root/'correction.json').read_text()) if (root/'correction.json').exists() else None
    if phase=='confirmation' and correction:
        if sha256(correction['reproduction_path'])!=correction['reproduction_sha256']:raise ValueError('Correction evidence changed')
    current=json.loads(Path(candidate).read_text())
    check_transition(phase,effort,current['llm_path_sha256'],decision,final,correction)


def register(directory,protocol_dir,run,labels,identity):
    from copilot.candidate_identity import verify
    root=Path(directory);metrics=score(run,labels);phase=metrics['phase'];effort=metrics['chosen_effort']
    verify(identity,protocol_dir,effort=effort,require_installed=True)
    saved=json.loads(Path(identity).read_text())
    if sha256(identity)!=metrics['variant_identities'][effort]:raise ValueError('Chosen identity differs from sealed run')
    with locked(root,protocol_dir):
        closed=json.loads((root/(phase+'.close.json')).read_text())
        claimed=json.loads((root/(phase+'.claim.json')).read_text())
        if not closed['certified'] or closed['seal_sha256']!=metrics['seal_sha256'] or Path(claimed['output']).resolve()!=Path(run).resolve():
            raise ValueError('Certified claimed run required')
        if phase=='confirmation':
            decision=json.loads((root/'decision.json').read_text())
            if effort!=decision['chosen_effort']:raise ValueError('Confirmation changed chosen effort')
        score_path=root/(phase+'.operational-score.json');exclusive_json(score_path,metrics)
        assessment={'effort':effort,'gate_passed':metrics['gate_passed'],'llm_path_sha256':saved['llm_path_sha256'],
                    'identity_path':str(Path(identity).resolve()),'run':str(Path(run).resolve()),
                    'seal_sha256':metrics['seal_sha256'],'score_path':str(score_path.resolve()),'score_sha256':sha256(score_path)}
        exclusive_json(root/(phase+'.assessment.json'),assessment)
        if phase=='pilot':exclusive_json(root/'decision.json',{'chosen_effort':effort,
            'pilot_llm_path_sha256':saved['llm_path_sha256'],'pilot_assessment_sha256':sha256(root/'pilot.assessment.json')})
    return metrics


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign-dir','protocol-dir','run','labels','identity'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=register(a.campaign_dir,a.protocol_dir,a.run,a.labels,a.identity)
    print(json.dumps({'chosen_effort':result['chosen_effort'],'gate_passed':result['gate_passed'],'variants':result['variants']}))


if __name__=='__main__':main()
