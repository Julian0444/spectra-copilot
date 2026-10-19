"""Frozen development inputs only. No selector imports or private custody access."""
import hashlib
import json
from pathlib import Path

import numpy as np

DEVELOPMENT_SHA = '60b2b4584e5a57030a4ff82a1b13d23065505a4d8bb878a20f5d4caecbe3f7c4'
EMISSION = (1215.7, 1549.1, 1908.7, 2798.8, 3727.1, 4861.3, 4958.9, 5006.8, 6562.8)
ABSORPTION = (3933.7, 3968.5)
SINGLE = (1215.7, 3727.1, 5006.8, 6562.8)


def read_development(path):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != DEVELOPMENT_SHA:
        raise ValueError('Only the frozen development manifest is authorized')
    cases = json.loads(data)['cases']
    if len(cases) != 96 or sum(c['kind'] == 'real' for c in cases) != 48:
        raise ValueError('Unexpected development population')
    return cases


def render_recipe(case):
    """Implement §3 of the frozen protocol, never derive recipes from roles."""
    recipe, family = case['recipe'], case['family']
    wave = np.linspace(3600., 9800., 2048)
    rng = np.random.Generator(np.random.PCG64(recipe['seed']))
    flux = 1 + .05*np.sin(wave/700) + rng.normal(0, 1, len(wave))
    ivar, mask = np.ones(len(wave)), np.zeros(len(wave), dtype=bool)
    injected = []
    if family == 'single_line':
        injected = [recipe['peak_angstrom']]
    elif family not in {'noise', 'invalid_support'}:
        rests = ABSORPTION if family == 'absorption' else EMISSION
        injected = [rest*(1+recipe['z']) for rest in rests if 3600 <= rest*(1+recipe['z']) <= 9800]
    sign = -1 if family == 'absorption' else 1
    for center in injected:
        flux += sign*recipe['snr']*np.exp(-.5*((wave-center)/5)**2)
    replica = [0, 2, 5, 10, 20, 50].index(recipe['snr'])
    if family == 'coverage_gap':
        gap = ((wave >= 5000) & (wave <= 6000)) | ((wave >= 7000) & (wave <= 7500))
        if replica % 3 == 0:
            mask[gap] = True
        elif replica % 3 == 1:
            ivar[gap] = 0
        else:
            flux, wave, ivar, mask = (x[~gap] for x in (flux, wave, ivar, mask))
    elif family == 'invalid_support':
        if replica % 3 == 0:
            mask[:] = True
        elif replica % 3 == 1:
            ivar[:] = 0
        else:
            flux[:] = np.nan
    elif family == 'reversed_grid':
        flux, wave, ivar, mask = (x[::-1] for x in (flux, wave, ivar, mask))
    elif family == 'permuted_grid':
        order = np.random.Generator(np.random.PCG64(recipe['seed']+1)).permutation(len(wave))
        flux, wave, ivar, mask = (x[order] for x in (flux, wave, ivar, mask))
    return {'flux': flux, 'wavelength': wave, 'ivar': ivar, 'mask': mask}, injected if recipe['snr'] > 0 else []


def materialize(cases, output, raw_root, index):
    """Write scientific arrays only; labels/provenance remain in the harness."""
    from desi_fm.local_data import LocalDESIStore
    from desi_fm.data import extract_mmu_desi_example
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = LocalDESIStore(raw_root, index)  # verifies local raw and index hashes
    results = []
    for position, case in enumerate(cases):
        if case['kind'] == 'real':
            f, v, w, m, _ = extract_mmu_desi_example(store.raw(case['object_id']))
            arrays, injected = dict(flux=f, wavelength=w, ivar=v, mask=m), []
        else:
            arrays, injected = render_recipe(case)
        path = output/f'input_{position:04d}.npz'
        np.savez(path, **arrays, wavelength_unit='angstrom')
        results.append((case, path, arrays, injected))
    return results


def supported_intervals(arrays):
    """Observed adjacent valid pixels; absent-coordinate gaps use the v3 rule."""
    order = np.argsort(arrays['wavelength'])
    f, w, v, m = (arrays[k][order] for k in ('flux', 'wavelength', 'ivar', 'mask'))
    good = np.isfinite(f) & np.isfinite(w) & (w > 0) & np.isfinite(v) & (v > 0) & ~m
    delta = np.diff(w)
    if len(delta) == 0:
        return np.array([]), np.array([])
    left = np.r_[delta[1], delta[:-1]] if len(delta) > 1 else delta
    right = np.r_[delta[1:], delta[-2]] if len(delta) > 1 else delta
    contiguous = good[:-1] & good[1:] & (delta > 0) & (delta <= 1.5*np.minimum(left, right))
    return w[:-1][contiguous], w[1:][contiguous]


def in_support(values, intervals):
    lo, hi = intervals
    return np.array([bool(np.any((lo <= x) & (hi >= x))) for x in values])


def wrong_controls(case, reference, rests, intervals):
    seed = int(hashlib.sha256(('batch5b-wrong-z:20261019:'+case['case_id']).encode()).hexdigest()[:16], 16)
    rng = np.random.Generator(np.random.PCG64(seed))
    def support_bin(z):
        n = int(in_support(np.array(rests)*(1+z), intervals).sum())
        return n if n < 3 else 3 if n < 6 else 6
    groups, proposals = {}, {}
    for name in ('unconditional', 'coverage_conditioned'):
        zs = []
        for attempt in range(10000):
            z = float(np.expm1(rng.uniform(0, np.log(7))))
            if abs(z-reference)/(1+reference) <= .15:
                continue
            if name == 'coverage_conditioned' and support_bin(z) != support_bin(reference):
                continue
            if z not in zs:
                zs.append(z)
            if len(zs) == 10:
                break
        groups[name], proposals[name] = zs, attempt+1
    return groups, proposals
