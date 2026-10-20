"""Regressions for independently demonstrated surviving mutations; invented data."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from copilot import acceptance, acceptance_score, tools
from copilot.acceptance_io import sha256, write_json
from test_acceptance import plan, report
from test_eval_persistence import harness


def test_changed_input_hash_prevents_worker_call(tmp_path):
    inputs,_,items=plan(tmp_path,2)
    Path(items[0]['input_path']).write_bytes(b'changed after plan registration')
    calls=[]
    out=tmp_path/'run'
    acceptance.execute_plan(inputs,out,runner=lambda path:(calls.append(path),report())[1])
    rows=json.loads((out/'outputs.json').read_text())
    assert rows[0]['status']=='technical_error' and rows[0]['result']['model_z'] is None
    assert calls==[items[1]['input_path']] and rows[1]['status']=='complete'


def test_missing_execution_budget_is_unknown_and_stops(tmp_path):
    inputs,_,_=plan(tmp_path);calls=[]
    def missing(path):
        calls.append(path);value=report();value['execution_budget']=None
        return value
    out=tmp_path/'run';summary=acceptance.execute_plan(inputs,out,runner=missing)
    assert len(calls)==1 and summary['attempted']==1 and summary['status_counts']['pending']==2
    assert summary['cost']['certified'] is False and summary['cost']['total_usd'] is None
    assert json.loads((out/'summary.json').read_text())['stop_reason']=='usage_uncertified'


def reseal(directory):
    summary=json.loads((directory/'summary.json').read_text())
    summary['outputs_sha256']=sha256(directory/'outputs.json');write_json(directory/'summary.json',summary)
    seal=json.loads((directory/'seal.json').read_text())
    for name in ('outputs','summary'):seal[name+'_sha256']=sha256(directory/(name+'.json'))
    write_json(directory/'seal.json',seal)
    # The fixture intentionally authorizes this new seal, isolating alias order.
    write_json(directory.with_name(directory.name+'.seal-record.json'),
        {'schema':'batch5c-seal-record-v1','seal_sha256':sha256(directory/'seal.json')})


def test_alias_order_checked_before_labels_even_with_matching_file_hashes(tmp_path,monkeypatch):
    inputs,labels,_=plan(tmp_path);out=tmp_path/'run'
    acceptance.execute_plan(inputs,out,runner=lambda _:report())
    rows=json.loads((out/'outputs.json').read_text());write_json(out/'outputs.json',rows[::-1]);reseal(out)
    original=Path.read_bytes
    def read(path):
        if path==labels:pytest.fail('Labels must not open for a reordered output')
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',read)
    with pytest.raises(ValueError,match='Requested identities changed'):
        acceptance_score.score_sealed(out,labels)


def test_resume_rejects_internally_consistent_alternative_redshift(harness,monkeypatch):
    mod,run,rows,out,_=harness
    run();saved=rows();row=saved[0]
    row['z_final']='0.75';dzn=mod.dz_norm(.75,.5)
    row.update(dzn=str(dzn),ok15=str(int(dzn<.15)),ok05=str(int(dzn<.05)))
    mod.write_csv(out,saved);before=out.read_bytes()
    monkeypatch.setattr(mod.agent,'run_structured',lambda *a,**k:pytest.fail('Invalid resume must stop before agent'))
    with pytest.raises(ValueError,match='official model prediction'):run('--resume')
    assert out.read_bytes()==before


@pytest.mark.parametrize('gap_mode',['mask','ivar','missing_coordinates'])
def test_outside_support_and_gap_lines_are_excluded_from_denominator(tmp_path,gap_mode):
    wave=np.arange(5500.,9000.5,.5);flux=np.ones_like(wave);ivar=np.ones_like(wave);mask=np.zeros_like(wave,dtype=bool)
    gap=(wave>7950)&(wave<8250)
    if gap_mode=='mask':mask[gap]=True
    elif gap_mode=='ivar':ivar[gap]=0
    else:flux,wave,ivar,mask=(a[~gap] for a in (flux,wave,ivar,mask))
    path=tmp_path/'partial-support.npz';np.savez(path,flux=flux,wavelength=wave,ivar=ivar,mask=mask)
    z=8000/6562.8-1;result=tools.identify_spectral_lines_impl(str(path),z)
    wavelengths=np.array(list(tools.LINES.values()))*(1+z)
    expected=sum((5512<=w<=7938) or (8262<=w<=8988) for w in wavelengths)
    assert 0<expected<len(tools.LINES)
    assert result['n_expected_in_coverage']==expected and result['n_matched']==0
    assert any(line['support']=='outside_support_or_gap' and abs(line['lambda_expected']-8000)<.1 for line in result['line_support'])


def test_wrong_controls_retain_expected_line_count_condition():
    source=Path(__file__).resolve().parents[1]/'scripts/batch5b_development.py'
    spec=importlib.util.spec_from_file_location('development_controls',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rests=list(tools.LINES.values());intervals=(np.array([4500.]),np.array([7000.]));reference=.42
    groups,_=module.wrong_controls({'case_id':'invented-controls-only'},reference,rests,intervals)
    def coverage_bin(z):
        count=sum(4500<=rest*(1+z)<=7000 for rest in rests)
        return count if count<3 else 3 if count<6 else 6
    assert len(groups['coverage_conditioned'])==len(groups['unconditional'])==10
    assert all(coverage_bin(z)==coverage_bin(reference) for z in groups['coverage_conditioned'])
    assert any(coverage_bin(z)!=coverage_bin(reference) for z in groups['unconditional'])
    assert all(abs(z-reference)/(1+reference)>.15 for group in groups.values() for z in group)
