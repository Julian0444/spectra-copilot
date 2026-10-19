"""Released explanations are rendered from executor-owned evidence, never free prose.

The LLM selects evidence and a conservative assessment. Its free-form text is
unvalidated draft material; it cannot become a scientific conclusion. This
protects software fidelity, not the accuracy of the predictor or of an LLM.
"""
from copy import deepcopy
import math

POLICY_VERSION = 'explanatory-model-z-v1'
STATES = {'complete', 'invalid_input', 'insufficient_data', 'ambiguous',
          'explanation_incomplete', 'technical_error'}
LIMITS = [
    'Posterior concentration is not a calibrated probability of correctness.',
    'Stability under masking does not establish redshift correctness.',
    'Neighbors from the same supervised encoder are not independent evidence.',
    'Spectral matching is descriptive; absence of support does not refute a hypothesis.',
]


def canonical_z(prediction):
    value = prediction['z_pred_map'] if 'z_pred_map' in prediction else prediction['z_pred']
    lower_bound = 0 if 'z_pred_map' in prediction else -1
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or value < lower_bound or value == -1):
        raise ValueError('Invalid official prediction')
    return float(value)


def result(prediction=None, observations=(), selected=(), assessment='descriptive',
           status=None, violations=()):
    by_id = {o['id']: o for o in observations}
    if any(key not in by_id for key in selected):
        raise ValueError('Unknown observation; invented tool evidence is forbidden')
    if status is None:
        status = {'descriptive': 'complete', 'ambiguous': 'ambiguous',
                  'insufficient_data': 'insufficient_data'}[assessment]
    if status not in STATES:
        raise ValueError('Invalid result state')
    z = canonical_z(prediction) if prediction is not None else None
    if status in {'complete', 'ambiguous', 'insufficient_data'} and z is None:
        raise ValueError('A valid report requires an official prediction')
    explanations, alternatives = [], []
    for key in selected:
        obs = by_id[key]
        tool, data = obs['tool'], obs['result']
        if obs.get('error'):
            explanations.append({'observation_id': key, 'text': f'{tool} failed ({obs["error"]}); no measurement is asserted.'})
            continue
        if tool == 'predict_redshift':
            text = f'The official predictor returned model_z={z!r}.'
            if 'z_confidence' in data:
                text += f' Posterior concentration is {data["z_confidence"]!r}; it is not calibrated accuracy.'
        elif tool == 'identify_spectral_lines':
            text = (f'At hypothesis z={data["z_tested"]!r}, the matcher counted '
                    f'{data["n_matched"]} matches among {data["n_expected_in_coverage"]} line positions in coverage. '
                    'These are descriptive measurements, not physical confirmation.')
            alternatives.extend(dict(c, observation_id=key) for c in data.get('candidates', []))
            if data.get('ambiguous'):
                status = 'ambiguous' if status == 'complete' else status
        elif tool == 'reconstruct_spectrum':
            text = f'One masking draw returned z={data["z_pred_under_masking"]!r}; this measures stability, not correctness.'
        elif tool == 'find_similar_spectra':
            text = (f'{data["k"]} neighbors have catalog redshifts in {data["neighbor_z_range"]!r}. '
                    'The shared encoder makes this non-independent evidence; index compatibility remains unverified.')
        elif tool == 'lookup_reference':
            text = 'Retrieved reference IDs: ' + ', '.join(d['id'] for d in data['results']) + '. Existence alone does not establish claim support.'
        else:
            raise ValueError('Unknown tool evidence')
        explanations.append({'observation_id': key, 'text': text})
    return deepcopy({'policy': POLICY_VERSION, 'status': status, 'model_z': z,
                     'predictor': prediction.get('model_identity') if prediction else None,
                     'input_contract': prediction.get('coverage', {}).get('contract') if prediction else None,
                     'prediction': prediction, 'alternatives': alternatives,
                     'observations': list(observations), 'explanation': explanations,
                     'limitations': LIMITS, 'policy_violations': list(violations),
                     'free_text_publication': 'disabled; requires independent semantic review'})


def render(report):
    # Never render assistant message text or a submit payload as the result.
    z = report['model_z']
    lines = ['## Observation report', f'Status: {report["status"]}',
             'Official model_z: '+('unavailable' if z is None else repr(z)),
             'Predictor: '+str(report['predictor']), 'Input contract: '+str(report['input_contract'])]
    lines.extend(f'{e["text"]} [{e["observation_id"]}]' for e in report['explanation'])
    lines.extend(report['limitations'])
    if report['policy_violations']:
        lines.append('Unvalidated or incompatible generated content was withheld: '+', '.join(report['policy_violations']))
    return '\n\n'.join(lines)
