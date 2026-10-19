"""Offline tests for the plan-11 eval harness: no API key, no network.

run_structured is exercised against a fake tool runner injected through
anthropic.Anthropic, so the structured-output contract (submit_report payload
+ token accounting) is tested without spending a single token. The eval
scripts in eval/ are plain scripts, not a package — they are loaded by path.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from copilot import agent

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, EVAL_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeMessage:
    usage = SimpleNamespace(input_tokens=100, output_tokens=20,
        cache_creation_input_tokens=0, cache_read_input_tokens=0)
    content = []
    def to_dict(self):
        return {"content": []}


def _install_fake_runner(monkeypatch, submit_args=None, captured=None, callback=None):
    from desi_fm.model import DESIFoundationModel, DESIFoundationModelConfig
    small = DESIFoundationModel(DESIFoundationModelConfig(n_pixels=64,n_tokens=8,d_model=16,n_layers=1,n_heads=2,n_z_bins=16))
    monkeypatch.setattr(agent.tools, '_model', lambda: small)
    class Runner:
        def __init__(self, kwargs): self.kwargs=kwargs
        def __iter__(self):
            offered={t.name:t for t in self.kwargs['tools']}
            if callback: callback(self.kwargs,offered)
            if submit_args is not None: offered['submit_report'].call(submit_args)
            body={k:v for k,v in self.kwargs.items() if k in {'model','max_tokens','system','messages'}}
            body['tools']=[t.to_dict() for t in self.kwargs['tools']]
            yield fake.beta.messages._post('/v1/messages',body=body)
            yield fake.beta.messages._post('/v1/messages',body=body)
        def generate_tool_call_response(self): return None
    def tool_runner(**kwargs):
        if captured is not None: captured.update(kwargs)
        return Runner(kwargs)
    fake=SimpleNamespace(max_retries=0,beta=SimpleNamespace(messages=SimpleNamespace(tool_runner=tool_runner,_post=lambda *a,**k:_FakeMessage())))
    monkeypatch.setattr(agent.anthropic, 'Anthropic', lambda **kwargs: fake)
    # Positive budgets are confined to simulated clients in these contract tests.
    monkeypatch.setattr(agent,'new_budget',lambda model:agent.Budget(model,agent.Limits(usd=1.,input_tokens=1000000)))


def _source(tmp_path):
    import numpy as np
    path=tmp_path/'private_z_true_0.2036'/'heldout_z020.npz'
    path.parent.mkdir()
    w=np.geomspace(3600,9800,64).astype(np.float32)
    np.savez(path,flux=np.sin(w/500),wavelength=w,z_true=.2036,
             object_name='label_z020',metadata={'z_true':.2036})
    return path


def test_submit_report_returns_validated_payload():
    import json, pytest
    args=dict(observation_ids=['obs-1'], assessment='ambiguous', reference_ids=None)
    assert json.loads(agent.submit_report.call(args))==args
    for fields in [dict(observation_ids=[]), dict(assessment='high'), dict(model_z=9.),
                   dict(z_final=9.), dict(lines_matched=99), dict(summary='z is 9')]:
        with pytest.raises((ValueError, TypeError)):
            agent.submit_report.call(dict(args, **fields))


def test_run_structured_returns_payload_with_token_accounting(monkeypatch,tmp_path):
    captured={}
    _install_fake_runner(monkeypatch,submit_args=dict(observation_ids=['obs-1'],assessment='ambiguous'),captured=captured)
    source=_source(tmp_path);before=source.read_bytes()
    r=agent.run_structured(str(source),model='claude-haiku-4-5')
    assert r['model_z']==agent.tools.official_z(r['prediction']) and r['tokens_in']==100 and r['tokens_out']==20
    assert r['status']=='ambiguous'
    assert captured['max_iterations']==8
    assert 'submit_report exactly once' in captured['system']
    assert 'thinking' not in captured
    assert source.read_bytes()==before
    assert r['input_provenance']['source_sha256']


def test_successive_runs_have_no_stale_report(monkeypatch,tmp_path):
    source=_source(tmp_path)
    _install_fake_runner(monkeypatch,submit_args=dict(observation_ids=['obs-1'],assessment='ambiguous'))
    assert agent.run_structured(str(source))['status']=='ambiguous'
    _install_fake_runner(monkeypatch)
    assert agent.run_structured(str(source))['status']=='explanation_incomplete'


def test_agent_receives_no_labels_paths_or_metadata(monkeypatch,tmp_path):
    import json,numpy as np
    source=_source(tmp_path);payloads=[]
    def prediction(p):
        payloads.append({'path':p})
        return {'z_pred_map':.7,'z_confidence':.4,'z_pred':.71,
                'model_identity':{'predictor':'invented'}, 'coverage':{'contract':'spectra-input-v3'}}
    monkeypatch.setattr(agent.tools,'predict_redshift_impl',prediction)
    def callback(kwargs,offered):
        text=kwargs['messages'][0]['content'];path=text.split(' in ')[1].split(' and ')[0]
        assert Path(path).name=='spectrum.npz'
        with np.load(path,allow_pickle=False) as data:
            assert set(data.files)=={'flux','wavelength','ivar','mask','wavelength_unit'}
        assert Path(path).parent!=source.parent
        response=offered['predict_redshift'].call({'npz_path':path})
        payloads.append({'request':kwargs['messages'],'system':kwargs['system'],
                         'schemas':[t.to_dict() for t in kwargs['tools']], 'response':response})
    _install_fake_runner(monkeypatch,callback=callback)
    agent.run_structured(str(source));agent.run_structured(str(source))
    actual=json.dumps(payloads)
    for forbidden in ('z_true','z020','0.2036','label_z020',str(source.parent),'8/11','0.227'):
        assert forbidden not in actual
    assert len(payloads)==4


def test_budget_multi_submit_and_path_guard(monkeypatch):
    import pytest
    monkeypatch.setattr(agent.tools,'predict_redshift_impl',lambda p:{'z_pred_map':.4})
    state=agent.RunTools('/tmp/spectrum.npz',True);offered={t.name:t for t in state.tools}
    for _ in range(6): offered['predict_redshift'].call({'npz_path':state.path})
    with pytest.raises(ValueError,match='budget'): offered['predict_redshift'].call({'npz_path':state.path})
    args=dict(observation_ids=['obs-1'],assessment='ambiguous')
    offered['submit_report'].call(args)
    with pytest.raises(ValueError,match='already'): offered['submit_report'].call(dict(args,assessment='descriptive'))
    assert state.result['model_z']==.4
    other=agent.RunTools('/tmp/spectrum.npz',True)
    with pytest.raises(ValueError,match='opaque'): other.tools[0].call({'npz_path':'heldout_z020.npz'})
    assert other.result is None


def test_select_cases_is_stratified_and_deterministic():
    import csv

    export = _load_script("export_cases")
    with open(EVAL_DIR / "heldout_predictions_v21.csv") as f:
        z = [float(r["z_true"]) for r in csv.DictReader(f)]
    idx = export.select_cases(z, n=150, seed=7)
    assert len(idx) == 150 and len(set(idx)) == 150
    assert idx == sorted(idx)
    assert all(0 <= i < len(z) for i in idx)
    # The failure band the eval exists to measure must be oversampled.
    assert sum(z[i] > 1.5 for i in idx) >= 20
    assert idx == export.select_cases(z, n=150, seed=7)


def test_summarize_reports_both_systems_and_confidence_correlation():
    run_evals = _load_script("run_evals")
    rows = [
        # agent right, model right, high confidence
        {"case": "a", "z_true": "0.5", "z_model": "0.51", "z_final": "0.5",
         "confidence": "high", "dzn": "0.0", "ok15": "1", "ok05": "1",
         "tokens": "1000", "status": "ok"},
        # agent right where the model was catastrophic (the recovery story)
        {"case": "b", "z_true": "1.6", "z_model": "0.9", "z_final": "1.58",
         "confidence": "medium", "dzn": "0.0077", "ok15": "1", "ok05": "1",
         "tokens": "2000", "status": "ok"},
        # agent wrong, low confidence — honesty preserved in by_confidence
        {"case": "c", "z_true": "2.0", "z_model": "1.0", "z_final": "1.0",
         "confidence": "low", "dzn": "0.3333", "ok15": "0", "ok05": "0",
         "tokens": "3000", "status": "ok"},
        # agent errored: still counts in the model-only baseline
        {"case": "d", "z_true": "0.2", "z_model": "0.21", "z_final": "",
         "confidence": "", "dzn": "", "ok15": "", "ok05": "",
         "tokens": "", "status": "error"},
    ]
    s = run_evals.summarize(rows)
    assert s["n"] == 4 and s["n_ok"] == 3 and s["n_error"] == 1
    assert s["model_only"]["n"] == 4
    assert s["model_only"]["rate_015"] == 0.5  # a, d fine; b, c catastrophic
    assert s["agent"]["rate_015"] == round(2 / 3, 3)
    assert s["agent"]["by_confidence"]["high"] == {"n": 1, "rate_015": 1.0}
    assert s["agent"]["by_confidence"]["low"] == {"n": 1, "rate_015": 0.0}
    assert s["agent"]["total_tokens"] == 6000


def test_dz_norm_matches_convention():
    run_evals = _load_script("run_evals")
    assert abs(run_evals.dz_norm(1.15, 1.0) - 0.075) < 1e-12  # |dz| / (1 + z_true)
    assert abs(run_evals.dz_norm(0.85, 1.0) - 0.075) < 1e-12


def test_runner_multiple_submits_keep_first(monkeypatch,tmp_path):
    import pytest
    args=dict(observation_ids=['obs-1'],assessment='ambiguous')
    def callback(kwargs,offered):
        offered['submit_report'].call(args)
        with pytest.raises(ValueError,match='already'):
            offered['submit_report'].call(dict(args,assessment='descriptive'))
    _install_fake_runner(monkeypatch,callback=callback)
    assert agent.run_structured(str(_source(tmp_path)))['status']=='ambiguous'
