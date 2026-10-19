"""Harness contracts use development JSON and invented signals only."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from batch5b_development import read_development, render_recipe, supported_intervals, in_support, wrong_controls


def test_manifest_rejects_other_content_before_loading_cases(tmp_path):
    other = tmp_path/'other.json'
    other.write_text('{not even JSON')
    with pytest.raises(ValueError, match='Only the frozen development'):
        read_development(other)
    assert len(read_development(ROOT/'docs/protocol/batch5b-development.json')) == 96


def test_signal_generation_and_noise_do_not_consume_redshift():
    cases = read_development(ROOT/'docs/protocol/batch5b-development.json')
    for case in cases:
        if case['kind'] == 'real':
            continue
        a, lines = render_recipe(case)
        b, _ = render_recipe(case)
        assert all(np.array_equal(a[k], b[k], equal_nan=True) for k in a)
        if case['family'] == 'noise':
            changed = dict(case, recipe=dict(case['recipe'], z=99, snr=100))
            # Noise ignores z and has no injected line. The SNR metadata follows
            # the six frozen replicas, so only change z in this direct control.
            changed['recipe']['snr'] = case['recipe']['snr']
            c, _ = render_recipe(changed)
            assert np.array_equal(a['flux'], c['flux']) and lines == []


def test_support_never_bridges_quality_or_coordinate_gaps():
    wave = np.array([4000., 4001., 4010., 4011., 4020., 4021.])
    arrays = dict(wavelength=wave, flux=np.ones(6), ivar=np.ones(6), mask=np.zeros(6, dtype=bool))
    assert not in_support([4005, 4015], supported_intervals(arrays)).any()
    arrays['mask'][0] = True
    arrays['ivar'][-1] = 0
    assert not in_support([4000.5, 4020.5], supported_intervals(arrays)).any()


def test_wrong_controls_fixed_disjoint_and_reproducible():
    case = {'case_id': 'invented-development-control'}
    intervals = (np.array([3600.]), np.array([9800.]))
    groups, _ = wrong_controls(case, .4, [1215.7, 5006.8, 6562.8], intervals)
    assert groups == wrong_controls(case, .4, [1215.7, 5006.8, 6562.8], intervals)[0]
    assert all(len(zs) == 10 and len(set(zs)) == 10 for zs in groups.values())
    assert all(abs(z-.4)/1.4 > .15 for zs in groups.values() for z in zs)
