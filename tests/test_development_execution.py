"""Invented development registry/campaign fixtures; no custody access or paid HTTP."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from copilot import acceptance
from copilot.acceptance_io import sha256,write_json


def fixtures(tmp_path):
    from copilot.development import DEVELOPMENT_SHA,canonical_arrays_sha256
    registry={'schema':'batch5c-development-registry-v1','development_sha256':DEVELOPMENT_SHA,
              'selection_sha256':'a'*64,'inputs':[]}
    items=[]
    for i in range(12):
        p=tmp_path/f'input-{i}.npz'
        np.savez(p,flux=np.ones(32)*i,wavelength=np.linspace(3600,9800,32),ivar=np.ones(32))
        registry['inputs'].append({'slot':i,'input_sha256':sha256(p),'arrays_sha256':canonical_arrays_sha256(p.read_bytes())})
        for effort in (('low','medium') if i%2==0 else ('medium','low')):
            items.append({'alias':f'{len(items):023x}a','effort':effort,'input_path':str(p),'input_sha256':sha256(p)})
    reg=tmp_path/'registry.json';write_json(reg,registry)
    plan=tmp_path/'plan.json';write_json(plan,{'schema':acceptance.SCHEMA,'mode':'development',
        'phase':'pilot','registry_sha256':sha256(reg),'inputs':items})
    return reg,plan


def test_development_plan_enforces_fixed_membership_sequence_and_bytes(tmp_path):
    from copilot.development import validate_plan
    reg,path=fixtures(tmp_path);plan=acceptance.read_input_plan(path)
    payloads=validate_plan(plan,reg,sha256(reg))
    assert len(payloads)==24
    plan['inputs'][0]['effort']='medium'
    with pytest.raises(ValueError,match='sequence'):validate_plan(plan,reg,sha256(reg))
    plan=acceptance.read_input_plan(path)
    Path(plan['inputs'][0]['input_path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='identity'):validate_plan(plan,reg,sha256(reg))


def test_foreign_input_or_forged_registry_rejected(tmp_path):
    from copilot.development import validate_plan
    reg,path=fixtures(tmp_path);plan=acceptance.read_input_plan(path)
    plan['inputs'][0]['input_sha256']='f'*64
    with pytest.raises(ValueError):validate_plan(plan,reg,sha256(reg))
    plan=acceptance.read_input_plan(path)
    with pytest.raises(ValueError):validate_plan(plan,reg,'f'*64)


def test_invalid_support_can_be_registered_but_input_contract_rejects_it(tmp_path):
    from copilot.development import canonical_arrays_sha256
    from desi_fm.inputs import read_npz,SpectrumInputError
    path=tmp_path/'invalid.npz'
    np.savez(path,flux=np.ones(32),wavelength=np.linspace(3600,9800,32),mask=np.ones(32,dtype=bool))
    assert len(canonical_arrays_sha256(path.read_bytes()))==64
    with pytest.raises(SpectrumInputError):read_npz(path)


def campaign(tmp_path,registry_sha='a'*64):
    from copilot import campaign as c
    root=tmp_path/'campaign';docs=tmp_path/'docs';(docs/'protocol').mkdir(parents=True)
    spec={'schema':'batch5c-campaign-v1','campaign_id':'invented-5c',
          'directory_sha256':hashlib.sha256(str(root.resolve()).encode()).hexdigest(),
          'registry_sha256':registry_sha,'phase_caps_nanodollars':c.CAPS}
    write_json(docs/'protocol/batch5c-campaign.json',spec)
    c.initialize(root,docs)
    return c,root,docs


def test_development_reuses_worker_ledger_seal_and_phase_claim(tmp_path,monkeypatch):
    from copilot import candidate_identity
    from copilot.budget import Budget,Limits
    from copilot.acceptance_score import validate_seal
    reg,plan=fixtures(tmp_path);c,root,docs=campaign(tmp_path,sha256(reg))
    (docs/'protocol/batch5c-development-registry.json').write_bytes(reg.read_bytes())
    low=tmp_path/'low.json';medium=tmp_path/'medium.json'
    write_json(low,{'kind':'installed-5c','effort':'low'});write_json(medium,{'kind':'installed-5c','effort':'medium'})
    verified=[];calls=[]
    def verify(path,protocol_dir,*,effort,require_installed):
        assert protocol_dir==docs and require_installed
        assert json.loads(Path(path).read_text())['effort']==effort
        verified.append(effort)
    monkeypatch.setattr(candidate_identity,'verify',verify)
    def worker(item,directory,usd,seconds,*,candidate,protocol_dir,effort):
        assert sha256(item['input_path'])==item['input_sha256']
        assert json.loads(Path(candidate).read_text())['effort']==effort
        calls.append(effort)
        ledger=Budget(limits=Limits(usd=usd),effort=effort)
        return {'status':'insufficient_data','execution_budget':ledger.snapshot()},False
    monkeypatch.setattr(acceptance,'run_worker',worker)
    out=tmp_path/'run'
    result=acceptance.execute_plan(plan,out,usd=2.4,candidate=low,candidate_medium=medium,campaign_dir=root,protocol_dir=docs)
    assert result['requested']==24 and result['attempted']==24 and result['cost']['certified']
    assert sorted(verified)==['low','medium'] and calls==['low','medium','medium','low']*6
    rows,manifest,*_=validate_seal(out)
    assert manifest['phase']=='pilot' and manifest['registry_sha256']==sha256(reg)
    assert json.loads((root/'pilot.close.json').read_text())['certified']
    with pytest.raises(ValueError,match='attempt'):
        acceptance.execute_plan(plan,tmp_path/'second',usd=2.4,candidate=low,candidate_medium=medium,campaign_dir=root,protocol_dir=docs)
    assert not (tmp_path/'second').exists() and len(calls)==24


def test_foreign_development_rejected_before_output_or_claim(tmp_path,monkeypatch):
    from copilot import candidate_identity
    reg,plan=fixtures(tmp_path);c,root,docs=campaign(tmp_path,sha256(reg))
    (docs/'protocol/batch5c-development-registry.json').write_bytes(reg.read_bytes())
    low=tmp_path/'low.json';write_json(low,{})
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    value=json.loads(plan.read_text());value['inputs'][0]['input_sha256']='d'*64;write_json(plan,value)
    with pytest.raises(ValueError):
        acceptance.execute_plan(plan,tmp_path/'run',usd=2.4,candidate=low,candidate_medium=low,campaign_dir=root,protocol_dir=docs)
    assert not (tmp_path/'run').exists() and not (root/'pilot.claim.json').exists()


def test_campaign_claim_is_single_attempt_and_blocks_other_phases(tmp_path):
    c,root,docs=campaign(tmp_path)
    c.claim(root,docs,'pilot',tmp_path/'run',{'low':'a'*64,'medium':'b'*64})
    for phase in ['pilot','confirmation','proposal']:
        with pytest.raises(ValueError,match='open|attempt'):c.claim(root,docs,phase,tmp_path/phase,{})
    assert c.CAPS=={'pilot':2400000000,'confirmation':1200000000,'proposal':12800000000}
    with pytest.raises(FileNotFoundError):c.claim(tmp_path/'other',docs,'pilot',tmp_path/'run2',{})


def test_concurrent_campaign_claims_have_one_winner(tmp_path):
    c,root,docs=campaign(tmp_path)
    def attempt(i):
        try:c.claim(root,docs,'pilot',tmp_path/str(i),{});return True
        except (ValueError,BlockingIOError,FileExistsError):return False
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(attempt,range(2)))==1


def test_uncertified_closed_phase_still_blocks_new_identity(tmp_path):
    c,root,docs=campaign(tmp_path)
    c.claim(root,docs,'pilot',tmp_path/'run',{})
    write_json(root/'pilot.close.json',{'certified':False,'known_nanodollars':0})
    (docs/'BATCH_5B_PROTOCOL.md').write_text('new D adenda; same campaign commitment')
    with pytest.raises(ValueError,match='uncertified'):c.claim(root,docs,'proposal',tmp_path/'accept',{'low':'d'*64})


def test_paid_agent_cli_requires_campaign_runner(monkeypatch):
    import sys
    from copilot import agent
    monkeypatch.setattr(sys,'argv',['agent','unused.npz','--budget-usd','.1'])
    monkeypatch.setattr(agent,'run',lambda *a,**k:pytest.fail('Unregistered paid entry point'))
    with pytest.raises(SystemExit) as exc:agent.main()
    assert exc.value.code==2
