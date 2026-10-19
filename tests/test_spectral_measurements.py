"""Mechanism controls; not performance calibration or acceptance cases."""
import numpy as np
import pytest

from copilot import tools
from copilot.spectral import candidate_z
from desi_fm.inputs import SpectrumInputError


def spectrum(center=8000., sign=1, n=2048):
    w = np.linspace(3600., 9800., n)
    return dict(wavelength=w, flux=1+sign*30*np.exp(-.5*((w-center)/5)**2),
                ivar=np.ones(n), mask=np.zeros(n, bool))


def measure(tmp_path, arrays, z=8000/6562.8-1):
    p=tmp_path/'observation.npz';np.savez(p, **arrays)
    return tools.identify_spectral_lines_impl(str(p), z)


@pytest.mark.parametrize('field', ['mask','ivar'])
def test_invalidated_peak_cannot_contribute(tmp_path, field):
    a=spectrum(); valid=measure(tmp_path,a)
    assert valid['n_matched']==1 and valid['n_peaks_detected']==1
    bad=abs(a['wavelength']-8000)<40
    a[field][bad]=True if field=='mask' else 0
    r=measure(tmp_path,a)
    assert r['n_matched']==0 and r['n_peaks_detected']==0 and r['candidates']==[]
    halpha=next(x for x in r['line_support'] if x['line']=='Hα 6563')
    assert halpha['support']=='outside_support_or_gap'


@pytest.mark.parametrize('mode',['mask','ivar','absent'])
def test_gap_and_line_window_never_imply_absence(tmp_path, mode):
    a=spectrum(); gap=(a['wavelength']>7995)&(a['wavelength']<8100)
    if mode=='absent': a={k:v[~gap] for k,v in a.items()}
    else:a[mode][gap]=True if mode=='mask' else 0
    r=measure(tmp_path,a)
    assert r['n_matched']==0
    assert next(x for x in r['line_support'] if x['line']=='Hα 6563')['support']!='full_window'
    # Center is on valid pixels, but its matching window touches the gap.
    edge=measure(tmp_path,a,7990/6562.8-1)
    assert next(x for x in edge['line_support'] if x['line']=='Hα 6563')['support']=='incomplete_window'


def test_all_alternatives_arithmetic_and_uniform_comparison(tmp_path):
    r=measure(tmp_path,spectrum())
    assert r['ambiguous'] and r['physical_confirmation'] is False and 'verdict' not in r
    assert {x['lambda_rest'] for x in r['candidates']}=={1215.7,3727.1,5006.8,6562.8}
    for c in r['candidates']:
        assert c['z']==c['lambda_observed']/c['lambda_rest']-1
        assert c['measurement_id'] in {p['measurement_id'] for p in r['measurements']}
        direct=measure(tmp_path,spectrum(),c['z'])
        assert c['comparison']=={k:direct[k] for k in c['comparison']}
    wrong=measure(tmp_path,spectrum(),.9)
    assert wrong['n_matched']==0


def test_order_equivalence_including_provenance(tmp_path):
    a=spectrum(); expected=measure(tmp_path,a)
    for idx in [np.arange(2047,-1,-1),np.random.default_rng(77).permutation(2048)]:
        assert measure(tmp_path,{k:v[idx] for k,v in a.items()})==expected


def test_absorption_is_not_emission(tmp_path):
    z=.6;a=spectrum(3933.7*(1+z),-1)
    a['flux']-=30*np.exp(-.5*((a['wavelength']-3968.5*(1+z))/5)**2)
    r=measure(tmp_path,a,z)
    assert {x['line'] for x in r['matched_lines']}=={'Ca K 3934','Ca H 3969'}
    assert {x['modality'] for x in r['measurements']}=={'absorption'}
    assert all(x['snr']>=5 and x['residual_flux']<0 for x in r['measurements'])
    unsupported=measure(tmp_path,spectrum(6562.8,-1),0)
    assert unsupported['n_matched']==0
    assert 'unsupported' in ' '.join(unsupported['limitations'])


def test_noise_outside_coverage_and_invalid_support(tmp_path):
    a=spectrum();a['flux']=1+np.random.default_rng(3).normal(0,1,2048)
    r=measure(tmp_path,a)
    assert r['n_peaks_detected']==0 and r['assessment']=='insufficient_line_evidence'
    high=measure(tmp_path,spectrum(),20)
    assert high['n_expected_in_coverage']==high['n_matched']==0
    for mode in ('mask','ivar','flux'):
        b=spectrum();b[mode][:]=True if mode=='mask' else 0 if mode=='ivar' else np.nan
        with pytest.raises(SpectrumInputError):measure(tmp_path,b)


@pytest.mark.parametrize('obs,rest',[(np.nan,1),(1,0),(1,-1),(np.inf,3),(True,1)])
def test_invalid_candidate_domain(obs,rest):
    with pytest.raises(ValueError):candidate_z(obs,rest)


def test_candidate_negative_rejection_and_snr_formula(tmp_path):
    assert candidate_z(3600,6562.8) is None
    a=spectrum();r=measure(tmp_path,a)
    p=r['measurements'][0]
    assert p['snr']==pytest.approx(p['residual_flux'])
    a['ivar']*=4; s=measure(tmp_path,a)['measurements'][0]
    assert s['snr']==pytest.approx(2*p['snr'])
    assert '51-pixel' in r['snr_definition'] and 'instrumental' in r['resolution']
