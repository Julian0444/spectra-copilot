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


import pytest

@pytest.mark.parametrize("alias", [False, True])
def test_provenance_inside_opaque_destination_rejected_before_write(tmp_path, alias):
    spec = importlib.util.spec_from_file_location("derive_agent_inputs", Path(__file__).resolve().parents[1]/"scripts/derive_agent_inputs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = tmp_path/"opaque"
    parent = tmp_path
    if alias:
        parent = tmp_path/"alias"
        parent.symlink_to(tmp_path, target_is_directory=True)
    provenance = parent/"opaque"/"nested"/"map.json"
    source = tmp_path/"heldout_z020.npz"
    w = np.geomspace(3600, 9800, 64).astype(np.float32)
    np.savez(source, flux=np.sin(w/500), wavelength=w)
    with pytest.raises(ValueError, match="outside"):
        module.derive([source], destination, provenance)
    assert not destination.exists()
    assert not provenance.exists()


@pytest.mark.parametrize("dangling", [False, True])
def test_provenance_case_alias_on_case_insensitive_volume(tmp_path, monkeypatch, dangling):
    # macOS commonly aliases differently cased nonexistent child paths.
    alias=tmp_path.with_name(tmp_path.name.swapcase())
    if not alias.exists() or not alias.samefile(tmp_path):
        pytest.skip('case-sensitive filesystem')
    spec=importlib.util.spec_from_file_location('derive_agent_inputs',Path(__file__).resolve().parents[1]/'scripts/derive_agent_inputs.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if dangling:
        broken = tmp_path/'broken-link'
        broken.symlink_to(tmp_path/'missing-target')
        original_iterdir = Path.iterdir
        monkeypatch.setattr(Path, 'iterdir', lambda path: iter([broken, tmp_path/'source.npz']) if path == tmp_path else original_iterdir(path))
    source=tmp_path/'source.npz';w=np.geomspace(3600,9800,64).astype(np.float32)
    np.savez(source,flux=np.sin(w/500),wavelength=w)
    destination=tmp_path/'Opaque'
    with pytest.raises(ValueError,match='outside'):
        module.derive([source],destination,tmp_path/'opaque'/'map.json')
    assert not destination.exists()
