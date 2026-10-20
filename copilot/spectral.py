"""Descriptive native-grid measurements; no calibrated confirmation or correction.

No catalog changes or threshold search. A local median is a continuum estimate,
not a continuum fit with propagated uncertainty. IVAR supplies a pixel noise scale.
"""
import hashlib
import json
import math

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

VERSION = 'native-descriptive-v1'
ABSORPTION = {'Ca K 3934', 'Ca H 3969'}
SINGLE_RESTS = {'Lyα 1216', '[OII] 3727', '[OIII] 5007', 'Hα 6563'}


def candidate_z(observed, rest):
    """Only finite, positive wavelengths and nonnegative finite z are admissible."""
    if (isinstance(observed, bool) or isinstance(rest, bool) or
            not math.isfinite(observed) or not math.isfinite(rest) or observed <= 0 or rest <= 0):
        raise ValueError('Invalid candidate wavelengths')
    z = float(observed/rest - 1)
    return z if math.isfinite(z) and z >= 0 else None


def _segments(f, w, v, m):
    good = np.isfinite(f) & np.isfinite(w) & (w > 0) & np.isfinite(v) & (v > 0) & ~m
    delta = np.diff(w)
    left = np.r_[delta[1], delta[:-1]] if len(delta) > 1 else delta
    right = np.r_[delta[1:], delta[-2]] if len(delta) > 1 else delta
    joins = good[:-1] & good[1:] & (delta > 0) & (delta <= 1.5*np.minimum(left, right))
    cuts = np.r_[0, np.flatnonzero(~joins)+1, len(w)]
    return [(int(a), int(b)) for a, b in zip(cuts[:-1], cuts[1:]) if b-a >= 3 and good[a:b].all()]


def measure(flux, wave, ivar, mask, z, catalog, tolerance=12.):
    order = np.argsort(wave, kind='stable')
    f, w, v, m = (np.asarray(x)[order] for x in (flux, wave, ivar, mask))
    segments = _segments(f, w, v, m)
    digest = hashlib.sha256()
    for a in (f, w, v, m):
        digest.update(str(a.dtype).encode()); digest.update(a.tobytes())
    provenance = {'algorithm': VERSION, 'input_arrays_sha256': digest.hexdigest(),
                  'catalog_sha256': hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()}
    peaks, support = [], []
    for lo, hi in segments:
        step = float(np.median(np.diff(w[lo:hi])))
        support.append({'start': float(w[lo]), 'end': float(w[hi-1]), 'median_step_angstrom': step})
        # Fixed 51-pixel median, independently inside each contiguous valid region.
        residual = f[lo:hi] - median_filter(f[lo:hi].astype(float), size=51, mode='nearest')
        signed_snr = residual*np.sqrt(v[lo:hi])
        for modality, sign in (('emission', 1), ('absorption', -1)):
            indices, _ = find_peaks(sign*signed_snr, height=5., distance=max(1, int(round(12/step))))
            for j in indices:
                i = lo+j
                local_step = float(max(w[i]-w[i-1], w[i+1]-w[i]))
                radius = max(tolerance, 2*local_step)
                # Edge or gap-adjacent maxima are not fully supported measurements.
                if w[i]-radius < w[lo] or w[i]+radius > w[hi-1]:
                    continue
                peaks.append({'lambda_observed': float(w[i]), 'modality': modality,
                              'snr': float(sign*signed_snr[j]), 'residual_flux': float(residual[j]),
                              'local_step_angstrom': local_step, 'support_window_angstrom': radius})
    peaks.sort(key=lambda p: (-p['snr'], p['lambda_observed'], p['modality']))
    for i, p in enumerate(peaks):
        p['measurement_id'] = f'peak-{i+1}'

    def compare(hypothesis):
        lines = []
        for name, rest in catalog.items():
            expected = float(rest*(1+hypothesis))
            modality = 'absorption' if name in ABSORPTION else 'emission'
            if not math.isfinite(expected):
                lines.append({'line': name, 'lambda_rest': rest, 'lambda_expected': None,
                              'modality': modality, 'support': 'outside_numeric_domain'})
                continue
            entry = {'line': name, 'lambda_rest': rest, 'lambda_expected': expected, 'modality': modality}
            containing = next(((lo, hi) for lo, hi in segments if w[lo] <= expected <= w[hi-1]), None)
            if containing is None:
                entry['support'] = 'outside_support_or_gap'
            else:
                lo, hi = containing
                i = min(max(int(np.searchsorted(w, expected)), lo+1), hi-1)
                step = float(w[i]-w[i-1])
                radius = max(tolerance, 2*step)
                entry['window_angstrom'] = radius
                entry['support'] = 'full_window' if expected-radius >= w[lo] and expected+radius <= w[hi-1] else 'incomplete_window'
                if entry['support'] == 'full_window':
                    matches = [p for p in peaks if p['modality'] == modality and abs(p['lambda_observed']-expected) <= max(tolerance, 2*p['local_step_angstrom'])]
                    if matches:
                        p = min(matches, key=lambda p: (abs(p['lambda_observed']-expected), -p['snr']))
                        entry.update(matched_peak_at=p['lambda_observed'], delta=abs(p['lambda_observed']-expected),
                                     measurement_id=p['measurement_id'], snr=p['snr'])
            lines.append(entry)
        expected = [x for x in lines if x['support'] == 'full_window']
        matched = [x for x in expected if 'measurement_id' in x]
        return {'z_tested': hypothesis, 'n_expected_in_coverage': len(expected), 'n_matched': len(matched),
                'match_fraction': round(len(matched)/max(len(expected), 1), 2),
                'matched_lines': matched, 'line_support': lines}

    candidates = []
    for peak in peaks[:5]:
        names = SINGLE_RESTS if peak['modality'] == 'emission' else ABSORPTION
        for name, rest in catalog.items():
            if name not in names:
                continue
            alternative = candidate_z(peak['lambda_observed'], rest)
            if alternative is None:
                continue
            candidates.append({'candidate_id': f'candidate-{len(candidates)+1}', 'z': alternative,
                               'assumed_line': name, 'lambda_rest': rest,
                               'lambda_observed': peak['lambda_observed'], 'measurement_id': peak['measurement_id'],
                               'formula': 'lambda_observed / lambda_rest - 1', 'provenance': provenance,
                               'comparison': compare(alternative)})
    ambiguous = len(peaks) == 1 or any(sum(c['measurement_id'] == p['measurement_id'] for c in candidates) > 1 for p in peaks)
    return dict(compare(z), measurement_policy='descriptive_only', physical_confirmation=False,
                n_peaks_detected=len(peaks), strongest_peaks_angstrom=[round(p['lambda_observed'], 1) for p in peaks[:5]],
                measurements=peaks, candidates=candidates, ambiguous=ambiguous,
                assessment='ambiguous' if ambiguous else 'insufficient_line_evidence' if not peaks else 'descriptive',
                support_intervals=support, provenance=provenance,
                wavelength_convention='Frozen historical Angstrom values; no air/vacuum correction; not a metrology catalog.',
                resolution='Native pixel spacing is recorded per peak; instrumental resolution is not inferred.',
                snr_definition='Signed (flux - 51-pixel local median) * sqrt(ivar); detection SNR >= 5.',
                limitations=['SNR ignores continuum-estimation uncertainty, pixel covariance and instrumental line spread.',
                             'The input contract defaults missing IVAR to one; this is not an estimated noise variance.',
                             'Emission is supported for catalog lines except Ca H/K, which use absorption.',
                             'Other absorption lines and Ca H/K emission are unsupported; absence is not refutation.',
                             'Invalid pixels, absent-coordinate gaps and incomplete windows do not count as physical absences.',
                             'Candidate scores use identical support and rules; one line never resolves its interpretations.',
                             'No z correction or calibrated consistency verdict is enabled.'])
