"""Bounded P3 regressions with invented sealed outputs and local corpus data."""
import json
from pathlib import Path

import pytest

from copilot import acceptance, acceptance_score, agent, rag, review
from copilot.acceptance_io import sha256, write_json
from copilot.budget import Budget, Limits
from test_acceptance import plan, report
from test_citation_policy import claims, reviewer
from test_explanatory_policy import setup_run


def registered_seal(out):
    path=out.with_name(out.name+'.seal-record.json')
    write_json(path,{'schema':'batch5c-seal-record-v1','seal_sha256':sha256(out/'seal.json')})
    return path


def forbid_labels(monkeypatch,labels):
    original=Path.read_bytes
    def read(path):
        if path==labels:pytest.fail('Labels opened before integrity verification')
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',read)


def test_executor_registers_seal_outside_outputs_and_scorer_records_verification(tmp_path):
    inputs,labels,_=plan(tmp_path);out=tmp_path/'run'
    acceptance.execute_plan(inputs,out,runner=lambda _:report())
    record=out.with_name('run.seal-record.json')
    assert json.loads(record.read_text())['seal_sha256']==sha256(out/'seal.json')
    scored=acceptance_score.score_sealed(out,labels)
    assert scored['seal_verified_before_label_read'] is True
    assert scored['seal_verified_ns']<=scored['labels_read_started_ns']<=scored['labels_loaded_ns']
    assert scored['seal_sha256']==sha256(out/'seal.json')


@pytest.mark.parametrize('damage',['missing_record','changed_seal','summary_disagrees'])
def test_external_seal_and_summary_checked_before_labels(tmp_path,monkeypatch,damage):
    inputs,labels,_=plan(tmp_path);out=tmp_path/'run'
    acceptance.execute_plan(inputs,out,runner=lambda _:report())
    record=registered_seal(out)
    if damage=='missing_record':record.unlink()
    elif damage=='changed_seal':
        seal=json.loads((out/'seal.json').read_text());seal['created_ns']+=1
        write_json(out/'seal.json',seal)
    else:
        summary=json.loads((out/'summary.json').read_text());summary['outputs_sha256']='0'*64
        write_json(out/'summary.json',summary)
        seal=json.loads((out/'seal.json').read_text());seal['summary_sha256']=sha256(out/'summary.json')
        write_json(out/'seal.json',seal);registered_seal(out)
    forbid_labels(monkeypatch,labels)
    with pytest.raises((ValueError,FileNotFoundError)):
        acceptance_score.score_sealed(out,labels)


def test_symlink_to_record_inside_outputs_is_not_an_external_registration(tmp_path,monkeypatch):
    inputs,labels,_=plan(tmp_path);out=tmp_path/'run'
    acceptance.execute_plan(inputs,out,runner=lambda _:report())
    record=registered_seal(out);record.rename(out/'internal-record.json')
    record.symlink_to(out/'internal-record.json')
    forbid_labels(monkeypatch,labels)
    with pytest.raises(ValueError,match='outside'):
        acceptance_score.score_sealed(out,labels)


def test_existing_external_registration_is_never_overwritten(tmp_path):
    inputs,_,_=plan(tmp_path);out=tmp_path/'run'
    record=out.with_name('run.seal-record.json');record.write_text('prior registration')
    with pytest.raises(FileExistsError):
        acceptance.execute_plan(inputs,out,runner=lambda _:report())
    assert not out.exists() and record.read_text()=='prior registration'


def test_nonexistent_citation_cannot_count_as_supported_even_if_reviewers_agree():
    bundles=[reviewer(name,'supported','correct') for name in ('A','B')]
    for bundle in bundles:
        bundle['judgments']['claim-1']['reference_support']={'invented-missing-id':'supported'}
    result=review.score_claim_review(claims('invented-missing-id'),*bundles)
    assert result['textual_supported']==0 and result['unsupported_claims']==1
    assert result['rates']['textual_support']['rate']==0
    assert result['evaluation_failures']['invalid_citation_ids']==1


@pytest.mark.parametrize('submitted',[False,True])
def test_corpus_change_during_run_returns_technical_error_with_prediction_and_usage(monkeypatch,tmp_path,submitted):
    import numpy as np
    setup_run(monkeypatch)
    path=tmp_path/'invented.npz';wave=np.linspace(3600,9800,128)
    np.savez(path,flux=np.ones_like(wave),wavelength=wave,ivar=np.ones_like(wave))
    def execute(path,model,structured,state,budget,progress):
        state.bootstrap();budget.begin();ticket=budget.reserve(100,20)
        budget.settle(ticket,{'input_tokens':50,'output_tokens':10})
        lookup={t.name:t for t in state.tools}['lookup_reference']
        lookup.call({'query':'Halpha OII confusion'})
        if submitted:state.tools[-1].call({'observation_ids':[o['id'] for o in state.observations]})
        monkeypatch.setattr(rag,'corpus_revision',lambda:'changed-revision')
        return state,None,state.usage,state.history
    monkeypatch.setattr(agent,'execute_run',execute)
    result=agent.run_structured(str(path),budget=Budget(limits=Limits(usd=.1)))
    assert result['status']=='technical_error' and result['model_z']==.42
    assert result['citations']==[] and [o['tool'] for o in result['observations']]==[
        'predict_redshift','identify_spectral_lines','lookup_reference']
    assert 'reference_validation_failed' in result['policy_violations']
    assert result['execution_budget']['calls']==1 and result['execution_budget']['cost_certified']
