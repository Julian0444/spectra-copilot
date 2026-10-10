"""Cross-repository acceptance: shared FM fixtures, actual handlers, simulated UI host."""
import ast
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch
import desi_fm
import desi_fm.api as api
import desi_fm.predict as prediction
from desi_fm.inputs import SpectrumInputError
from desi_fm.model import DESIFoundationModel, DESIFoundationModelConfig
from copilot import tools, agent

FM_ROOT = Path(desi_fm.__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('contract_fixtures',FM_ROOT/'tests/contract_fixtures.py')
fixture_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture_module)

@pytest.fixture
def interfaces(monkeypatch):
    from fastapi.testclient import TestClient
    torch.manual_seed(17)
    model=DESIFoundationModel(DESIFoundationModelConfig(n_pixels=64,n_tokens=8,d_model=16,n_layers=1,n_heads=2,n_z_bins=16,dropout=.4))
    monkeypatch.setattr(api,'_model',model)
    monkeypatch.setattr(tools,'_model',lambda:model)
    monkeypatch.setattr(prediction,'load_model_from_checkpoint',lambda *a,**k:model)
    monkeypatch.setenv('DESI_FM_CKPT','local-test-checkpoint')
    # Replace hosting/layout only. The two real handlers and their core calls run.
    class Interface:
        def __init__(self,*a,**k): pass
        def queue(self,*a,**k): pass
    gr=SimpleNamespace(Error=SpectrumInputError,Interface=Interface,
                       File=lambda **k:None,Slider=lambda *a,**k:None,
                       Textbox=lambda **k:None,Plot=lambda **k:None)
    monkeypatch.setitem(sys.modules,'gradio',gr)
    monkeypatch.setitem(sys.modules,'spaces',SimpleNamespace(GPU=lambda **k:lambda f:f))
    loaded=[]
    for name,path in [('demo_handler','demo/app.py'),('tester_handler','api/app.py')]:
        spec=importlib.util.spec_from_file_location(name,FM_ROOT/path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        loaded.append(module)
    return model,TestClient(api.app),*loaded

@pytest.mark.parametrize('name',['valid','nonfinite','masked','partial','reordered','gap'])
def test_actual_interfaces_share_results(name,interfaces,tmp_path):
    model,client,demo,tester=interfaces
    arrays=fixture_module.spectra()[name]
    path=tmp_path/'input.npz';np.savez(path,**arrays)
    expected=prediction.predict_spectrum(**arrays,model=model)
    from desi_fm.data import preprocess_spectrum,SpectrumPreprocessConfig
    from desi_fm.inputs import read_npz
    f,w,v,m=read_npz(path).single()
    processed=preprocess_spectrum(f,v,w,m,SpectrumPreprocessConfig(n_pixels=64))
    np.testing.assert_array_equal(processed['flux'],expected['normalized_input'])
    np.testing.assert_array_equal(processed['valid'].astype(bool),expected['valid_model_grid'])
    rest=client.post('/predict',files={'file':('input.npz',path.read_bytes())})
    assert rest.status_code==200,rest.text
    result=rest.json()
    assert result['z_pred'][0]==pytest.approx(expected['z_pred'],abs=1e-6)
    payload={k:np.asarray(a).tolist() for k,a in arrays.items()}
    rest_json=client.post('/predict_json',content=json.dumps(payload),headers={'Content-Type':'application/json'})
    assert rest_json.status_code==200,rest_json.text
    assert rest_json.json()['z_pred']==pytest.approx(expected['z_pred'],abs=1e-6)
    text,figure=demo.analyze(str(path),0)
    assert f"z_pred_map = {expected['z_pred_map']:.4f}" in text
    import matplotlib.pyplot as plt
    plt.close(figure)
    for r in (json.loads(tester.predict_ui(str(path),0)),tools.predict_redshift_impl(str(path)),
              json.loads(agent.predict_redshift.call({'npz_path':str(path)}))):
        assert r['z_pred_map']==pytest.approx(expected['z_pred_map'],abs=5.1e-5)
        assert r['z_pred']==pytest.approx(expected['z_pred'],abs=5.1e-5)
        assert r['coverage']==expected['coverage']
    assert result['coverage']==[expected['coverage']]

@pytest.mark.parametrize('name',['no_coverage','bad_mask','bad_ivar','empty','strings','container'])
def test_invalid_interfaces_are_domain_errors(name,interfaces,tmp_path,monkeypatch):
    model,client,demo,tester=interfaces
    arrays=fixture_module.spectra()[name];p=tmp_path/'input.npz';np.savez(p,**arrays)
    assert client.post('/predict',files={'file':('input.npz',p.read_bytes())}).status_code==422
    for call in (lambda:prediction.predict_spectrum(**arrays,model=model),
                 lambda:demo.analyze(str(p),0),lambda:tester.predict_ui(str(p),0),
                 lambda:tools.predict_redshift_impl(str(p)),lambda:tools.find_similar_spectra_impl(str(p)),
                 lambda:tools.identify_spectral_lines_impl(str(p),.42)):
        with pytest.raises(SpectrumInputError):call()


def test_http_does_not_misclassify_internal_error(interfaces,monkeypatch):
    _,client,_,_=interfaces
    def broken(*a,**k):raise ValueError('internal model error')
    monkeypatch.setattr(api,'predict_spectrum',broken)
    with pytest.raises(ValueError,match='internal model'):
        client.post('/predict_json',json={k:v.tolist() for k,v in fixture_module.spectra()['valid'].items()})


def test_line_contract_reordering_and_all_bad(interfaces,tmp_path):
    arrays=fixture_module.spectra()['masked'];p=tmp_path/'input.npz'
    np.savez(p,**arrays);a=tools.identify_spectral_lines_impl(str(p),.42)
    np.savez(p,**{k:v[::-1] for k,v in arrays.items()});b=tools.identify_spectral_lines_impl(str(p),.42)
    assert a==b
    np.savez(p,**dict(arrays,mask=np.ones(64,bool)))
    with pytest.raises(SpectrumInputError):tools.identify_spectral_lines_impl(str(p),.42)


def test_cli_matches_python_and_keeps_metadata_json(interfaces,tmp_path):
    import subprocess
    model,_,_,_=interfaces
    arrays=fixture_module.spectra()['masked'];source=tmp_path/'input.npz';np.savez(source,**arrays)
    checkpoint=tmp_path/'checkpoint.pt';torch.save(dict(config=model.config.to_dict(),model=model.state_dict()),checkpoint)
    output=tmp_path/'output.npz'
    result=subprocess.run([sys.executable,'-m','desi_fm.predict','--checkpoint',str(checkpoint),'--input',str(source),'--output',str(output),'--device','cpu'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    expected=prediction.predict_spectrum(**arrays,model=model)
    with np.load(output,allow_pickle=False) as actual:
        np.testing.assert_allclose(actual['normalized_input'][0],expected['normalized_input'],atol=0,rtol=0)
        assert actual['z_pred'][0]==pytest.approx(expected['z_pred'],abs=1e-6)
        assert json.loads(str(actual['coverage_json']))==[expected['coverage']]
        assert json.loads(str(actual['model_identity_json']))['checkpoint']['sha256']
