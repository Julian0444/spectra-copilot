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


def campaign(tmp_path):
    from copilot import campaign as c
    root=tmp_path/'campaign';docs=tmp_path/'docs';(docs/'protocol').mkdir(parents=True)
    spec={'schema':'batch5c-campaign-v1','campaign_id':'invented-5c',
          'directory_sha256':hashlib.sha256(str(root.resolve()).encode()).hexdigest(),
          'registry_sha256':'a'*64,'phase_caps_nanodollars':c.CAPS}
    write_json(docs/'protocol/batch5c-campaign.json',spec)
    c.initialize(root,docs)
    return c,root,docs


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
