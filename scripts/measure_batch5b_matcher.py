"""Development-only matcher measurement; frozen baseline and later descriptive check."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from batch5b_development import (read_development, materialize, supported_intervals,
                               in_support, wrong_controls, SINGLE)


def summarize(rows, bootstrap=True):
    descriptive = {'status_counts': {s: sum(r['status'] == s for r in rows) for s in ('measured', 'invalid_input')},
                   'line_counts': {k: sum(r.get(k, 0) for r in rows) for k in
                                   ('injected_visible', 'injected_matched', 'false_line_matches', 'line_positions_tested')},
                   'noise_probes': sum(len(r.get('noise_controls', [])) for r in rows),
                   'noise_positive_probes': sum(c['positive'] for r in rows for c in r.get('noise_controls', [])),
                   'objects_with_false_line_matches': sum(r.get('false_line_matches', 0) > 0 for r in rows)}
    eligible = [r for r in rows if r.get('reference') is not None and r.get('controls')]
    n, wrong_n = len(eligible), sum(len(r['controls']) for r in eligible)
    if not n:
        return dict(descriptive, **{'requested': len(rows), 'reference_objects': 0, 'controls': 0,
                'auroc_paired': None, 'tpr': None, 'fpr_per_candidate': None, 'fpr_any_per_object': None}
        )
    pairs = np.array([np.mean([float(r['reference']['score'] > c['score']) +
                               .5*float(r['reference']['score'] == c['score']) for c in r['controls']]) for r in eligible])
    tpr = np.array([r['reference']['positive'] for r in eligible], dtype=float)
    false = np.array([sum(c['positive'] for c in r['controls']) for r in eligible], dtype=float)
    counts = np.array([len(r['controls']) for r in eligible])
    any_false = (false > 0).astype(float)
    report = {'requested': len(rows), 'reference_objects': n, 'controls': wrong_n,
              'missing_controls': sum(r['missing_controls'] for r in eligible),
              'auroc_paired': float(pairs.mean()), 'tpr': float(tpr.mean()),
              'fpr_per_candidate': float(false.sum()/counts.sum()),
              'fpr_any_per_object': float(any_false.mean())}
    report.update(descriptive)
    if bootstrap:
        draw = np.random.Generator(np.random.PCG64(20261020)).integers(0, n, (2000, n))
        values = {'auroc_paired': pairs[draw].mean(1), 'tpr': tpr[draw].mean(1),
                  'fpr_per_candidate': false[draw].sum(1)/counts[draw].sum(1),
                  'fpr_any_per_object': any_false[draw].mean(1)}
        report['object_bootstrap_95'] = {k: np.quantile(v, [.025, .975]).tolist() for k, v in values.items()}
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--development', type=Path, required=True)
    p.add_argument('--raw-root', type=Path, required=True)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--expected-commit', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    cases = read_development(args.development)  # refuses acceptance before JSON parsing
    actual = subprocess.check_output(['git', '-C', str(args.code_root), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != args.expected_commit:
        raise ValueError('Matcher code commit mismatch')
    sys.path.insert(0, str(args.code_root))
    from copilot import tools
    from desi_fm.inputs import SpectrumInputError
    if Path(tools.__file__).resolve() != (args.code_root/'copilot/tools.py').resolve():
        raise ValueError('Wrong matcher import')
    expected_source = subprocess.check_output(['git', '-C', str(args.code_root), 'show', actual+':copilot/tools.py'])
    if Path(tools.__file__).read_bytes() != expected_source:
        raise ValueError('Uncommitted matcher source')
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = materialize(cases, args.output/'inputs', args.raw_root, args.index)
    rows = []
    def measure(path, z):
        result = tools.identify_spectral_lines_impl(str(path), z)
        return {'z': z, 'score': result['match_fraction'],
                'positive': result.get('verdict') == 'consistent' if 'verdict' in result else result['match_fraction'] >= .4,
                'measurement': result}
    for case, path, arrays, injected in inputs:
        row = {'case_id': case['case_id'], 'kind': case['kind'], 'family': case.get('family', 'real'),
               'cnn_exposure': case['cnn_exposure'], 'zwarn': case.get('label', {}).get('zwarn'),
               'snr': case.get('recipe', {}).get('snr'), 'reference': None, 'controls': []}
        intervals = supported_intervals(arrays)
        reference = case['label']['z']
        try:
            first = measure(path, reference if reference is not None else 0.)
            row['status'] = 'measured'
            cov = first['measurement']['coverage']
            row['coverage'] = cov
            fraction = cov['model_valid_fraction']
            row['coverage_bin'] = ('0-.5' if fraction < .5 else '.5-.9' if fraction < .9 else
                                   '.9-.99' if fraction < .99 else '>=.99')
            if reference is not None:
                row['reference'] = first
                controls, proposals = wrong_controls(case, reference, list(tools.LINES.values()), intervals)
                row['control_proposals'] = proposals
                for group, zs in controls.items():
                    row['controls'] += [dict(measure(path, z), group=group) for z in zs]
                row['missing_controls'] = 20-len(row['controls'])
            elif row['family'] == 'single_line':
                row['alternatives'] = [measure(path, case['recipe']['peak_angstrom']/rest-1)
                                       for rest in SINGLE if case['recipe']['peak_angstrom'] >= rest]
            elif row['family'] == 'noise':
                rng = np.random.Generator(np.random.PCG64(case['recipe']['seed']))
                row['noise_controls'] = [measure(path, float(np.expm1(rng.uniform(0, np.log(7))))) for _ in range(20)]
            if case['kind'] != 'real' and reference is not None:
                visible = [x for x in injected if in_support([x], intervals)[0]]
                matched = first['measurement']['matched_lines']
                row['injected_visible'] = len(visible)
                row['injected_matched'] = sum(any(abs(m['lambda_expected']-x) <= .11 for m in matched) for x in visible)
                row['false_line_matches'] = sum(not any(abs(m['lambda_expected']-x) <= .11 for x in visible) for m in matched)
                row['line_positions_tested'] = first['measurement']['n_expected_in_coverage']
            if row['family'] in {'reversed_grid', 'permuted_grid'}:
                ordered = args.output/'ordered.npz'
                order = np.argsort(arrays['wavelength'])
                np.savez(ordered, **{k: v[order] for k, v in arrays.items()})
                row['ordering_equivalent'] = first == measure(ordered, reference)
                ordered.unlink()
        except SpectrumInputError:
            row['status'] = 'invalid_input'
            row['coverage_bin'] = 'invalid'
        rows.append(row)
        (args.output/'rows.json').write_text(json.dumps(rows, indent=2, allow_nan=False))
    report = {'identity': {'commit': actual, 'tools_sha256': hashlib.sha256(expected_source).hexdigest(),
                           'tools_module': tools.__file__, 'catalog': tools.LINES,
                           'development_sha256': hashlib.sha256(args.development.read_bytes()).hexdigest(),
                           'python': sys.version},
              'global': summarize(rows), 'strata': {}, 'control_groups': {},
              'status_counts': {s: sum(r['status'] == s for r in rows) for s in ('measured', 'invalid_input')},
              'bootstrap': {'replicates': 2000, 'seed': 20261020, 'unit': 'object_with_all_controls'},
              'limitations': ['Development only; no predictor accuracy comparison.',
                             'Paired AUROC is reference-versus-controls within object, ties weighted 0.5.',
                             'Injected recall concerns line matches at reference z; no peak-level completeness claim.',
                             'Historical 20/139 and 17.5% used one control and are not reproduced here; not a general FPR estimate.',
                             'Noise has no true z; 20 unconditional probes use the frozen recipe seed.',
                             'No threshold search; baseline uses historical 0.4.']}
    for dimension in ('kind', 'family', 'snr', 'zwarn', 'cnn_exposure', 'coverage_bin'):
        report['strata'][dimension] = {str(value): summarize([r for r in rows if r[dimension] == value])
                                       for value in sorted({r[dimension] for r in rows}, key=str)}
    for group in ('unconditional', 'coverage_conditioned'):
        selected = [dict(r, controls=[c for c in r['controls'] if c['group'] == group],
                         missing_controls=10-sum(c['group'] == group for c in r['controls'])) for r in rows]
        report['control_groups'][group] = summarize(selected)
    spectral = [r for r in rows if 'injected_visible' in r]
    report['injected_lines'] = {key: sum(r[key] for r in spectral) for key in
                               ('injected_visible', 'injected_matched', 'false_line_matches', 'line_positions_tested')}
    noise = [r for r in rows if 'noise_controls' in r]
    report['noise'] = {'objects': len(noise), 'probes': sum(len(r['noise_controls']) for r in noise),
                       'positive_probes': sum(c['positive'] for r in noise for c in r['noise_controls']),
                       'objects_any_positive': sum(any(c['positive'] for c in r['noise_controls']) for r in noise)}
    report['ordering'] = {r['case_id']: r['ordering_equivalent'] for r in rows if 'ordering_equivalent' in r}
    report['gate_passes'] = bool(report['global']['auroc_paired'] >= .75 and report['global']['tpr'] >= .5
                                and report['global']['fpr_any_per_object'] <= .05 and report['noise']['positive_probes'] == 0
                                and report['global']['missing_controls'] == 0)
    (args.output/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({key: report[key] for key in ('global', 'status_counts', 'noise', 'gate_passes')}))


if __name__ == '__main__':
    main()
