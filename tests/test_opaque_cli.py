import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from copilot import tools
from copilot.__main__ import main


def test_cli_omits_labels_and_original_path(tmp_path,monkeypatch,capsys):
    from desi_fm.model import DESIFoundationModel,DESIFoundationModelConfig
    model=DESIFoundationModel(DESIFoundationModelConfig(n_pixels=64,n_tokens=8,d_model=16,n_layers=1,n_heads=2,n_z_bins=16))
    monkeypatch.setattr(tools,'_model',lambda:model)
    source=tmp_path/'heldout_z020.npz';w=np.geomspace(3600,9800,64).astype(np.float32)
    np.savez(source,flux=np.sin(w/500),wavelength=w,z_true=.2036)
    monkeypatch.setattr(sys,'argv',['copilot',str(source)])
    main();payload=capsys.readouterr().out
    assert json.loads(payload)['input_id']=='spectrum'
    for forbidden in ('z_true','z020','0.2036',str(source)):assert forbidden not in payload


def test_persistent_opaque_derivative_is_separate_and_traceable(tmp_path):
    script=Path(__file__).resolve().parents[1]/'scripts/derive_agent_inputs.py'
    spec=importlib.util.spec_from_file_location('derive_agent_inputs',script)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    source=tmp_path/'heldout_z020.npz';w=np.geomspace(3600,9800,64).astype(np.float32)
    np.savez(source,flux=np.sin(w/500),wavelength=w,z_true=.2036,object_id='label')
    before=source.read_bytes();destination=tmp_path/'opaque';provenance=tmp_path/'evaluator'/'provenance.json'
    rows=m.derive([source],destination,provenance)
    with np.load(destination/'spectrum_0001.npz',allow_pickle=False) as d:
        assert set(d.files)=={'flux','wavelength','ivar','mask','wavelength_unit'}
    assert source.read_bytes()==before
    assert rows[0]['source_sha256'] and rows[0]['derived_sha256']
    assert provenance.parent!=destination
    import pytest
    with pytest.raises(ValueError):m.derive([source],destination,provenance)
