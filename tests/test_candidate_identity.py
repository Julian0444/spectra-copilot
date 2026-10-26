import json
from pathlib import Path

import pytest

from copilot import candidate_identity as identity
from copilot.acceptance_io import write_json


def test_candidate_identity_detects_asset_change_and_internal_tampering(tmp_path,monkeypatch):
    checkpoint=tmp_path/'checkpoint.pt';checkpoint.write_bytes(b'invented checkpoint')
    index=tmp_path/'index';index.mkdir()
    (index/'spectra.faiss').write_bytes(b'invented index');(index/'spectra_meta.npz').write_bytes(b'invented metadata')
    monkeypatch.setenv('DESI_FM_CKPT',str(checkpoint));monkeypatch.setenv('DESI_FM_INDEX_DIR',str(index))
    monkeypatch.setattr(identity.tools,'_model',lambda:None)
    monkeypatch.setattr(identity,'model_identity',lambda _: {'predictor':'invented','checkpoint_sha256':identity.sha256(checkpoint)})
    docs=Path(__file__).resolve().parents[1]/'docs'
    result=identity.capture(docs);p=tmp_path/'candidate.json';write_json(p,result)
    sdk_source='resources/beta/messages/messages.py'
    sdk_root=Path(identity.anthropic.__file__).resolve().parent
    assert result['behavior']['runtime']['anthropic_source_sha256'][sdk_source]==identity.sha256(sdk_root/sdk_source)
    assert identity.verify(p,docs)==result['behavior_sha256']
    assert 'copilot/acceptance_score.py' in result['behavior']['code_sha256']
    assert result['behavior']['llm_proposal']['paid_default_usd']==0
    proposal=result['behavior']['llm_proposal']
    assert result['kind']=='candidate-5b22' and proposal['model']=='claude-haiku-5-5'
    assert proposal['rates_usd_per_million']==[.1,.5]
    assert proposal['long_prompt_rates_usd_per_million']==[.5,2.5]
    assert proposal['request_configuration']=={'thinking':{'type':'adaptive'},'output_config':{'effort':'low'}}
    assert proposal['case_max_nanodollars']==96384000
    checkpoint.write_bytes(b'changed checkpoint')
    with pytest.raises(ValueError,match='differs'):identity.verify(p,docs)
    result['behavior']['policy']='tampered';write_json(p,result)
    with pytest.raises(ValueError,match='Invalid'):identity.verify(p,docs)
