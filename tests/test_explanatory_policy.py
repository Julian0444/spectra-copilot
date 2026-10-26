"""Simulated contracts only; these do not validate a real LLM's behavior."""
import json
from types import SimpleNamespace

import pytest

from copilot import agent, explanation
from test_evals import _install_fake_runner, _source, _FakeMessage
from test_eval_persistence import harness


PREDICTION = {'z_pred_map': .42, 'z_pred': .45, 'z_confidence': .7,
              'coverage': {'contract': 'spectra-input-v3'},
              'model_identity': {'checkpoint_sha256': 'invented', 'predictor': 'fixture'}}


def setup_run(monkeypatch, **kwargs):
    _install_fake_runner(monkeypatch, **kwargs)
    monkeypatch.setattr(agent.tools, 'predict_redshift_impl', lambda path: PREDICTION.copy())


@pytest.mark.parametrize('field,value', [('model_z', 9.), ('z_final', 9.),
                                       ('lines_matched', 999), ('summary', 'The correct redshift is 9')])
def test_cannot_submit_overrides_or_invented_measurements(monkeypatch, field, value):
    monkeypatch.setattr(agent.tools, 'identify_spectral_lines_impl', lambda path,z: {'z_tested':z,'n_matched':2,'n_expected_in_coverage':2})
    state = agent.RunTools('/opaque.npz')
    monkeypatch.setattr(agent.tools, 'predict_redshift_impl', lambda path: PREDICTION.copy())
    state.bootstrap()
    submit = {t.name: t for t in state.tools}['submit_report']
    with pytest.raises((TypeError, ValueError)):
        submit.call({'observation_ids': ['obs-1'], field: value})
    assert state.finish()['model_z'] == .42
    assert state.result is None


def test_unknown_observation_cannot_fabricate_a_tool(monkeypatch):
    monkeypatch.setattr(agent.tools, 'predict_redshift_impl', lambda path: PREDICTION.copy())
    monkeypatch.setattr(agent.tools, 'identify_spectral_lines_impl', lambda path,z: {'z_tested':z,'n_matched':2,'n_expected_in_coverage':2})
    state = agent.RunTools('/opaque.npz'); state.bootstrap()
    with pytest.raises(ValueError, match='evidence'):
        state.tools[-1].call({'observation_ids': ['invented-tool-result']})
    assert state.finish()['status'] == 'explanation_incomplete'
    assert state.finish()['model_z'] == .42


def test_contradictory_prose_is_quarantined_not_rendered(monkeypatch, tmp_path):
    setup_run(monkeypatch, submit_args={'observation_ids': ['obs-1']})
    monkeypatch.setattr(_FakeMessage, 'content', [SimpleNamespace(type='text', text='The final redshift is 9.99')])
    report = agent.run_structured(str(_source(tmp_path)))
    assert report['status'] == 'explanation_incomplete'
    assert report['model_z'] == .42
    assert 'unvalidated_generated_text' in report['policy_violations']
    assert '9.99' not in explanation.render(report)


@pytest.mark.parametrize('assessment,status', [('descriptive','insufficient_data'), ('ambiguous','insufficient_data'),
                                              ('insufficient_data','insufficient_data')])
def test_valid_report_and_abstention_keep_executor_prediction(monkeypatch, tmp_path, assessment, status):
    setup_run(monkeypatch, submit_args={'observation_ids': ['obs-1'], 'assessment': assessment})
    report = agent.run_structured(str(_source(tmp_path)))
    assert report['status'] == status and report['model_z'] == .42
    assert report['predictor'] == PREDICTION['model_identity']
    assert report['input_contract'] == 'spectra-input-v3'
    assert 'Official model_z: 0.42' in explanation.render(report)
    assert report['alternatives'] == []


def test_technical_failure_after_predict_keeps_model_z(monkeypatch, tmp_path):
    setup_run(monkeypatch)
    monkeypatch.setattr(agent.anthropic, 'Anthropic', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('private path or credential')))
    report = agent.run_structured(str(_source(tmp_path)))
    assert report['status'] == 'technical_error' and report['model_z'] == .42
    assert 'private path' not in json.dumps(report)


def test_invalid_input_distinct_from_missing_server_asset(monkeypatch, tmp_path):
    setup_run(monkeypatch)
    invalid = agent.run_structured(str(tmp_path/'absent.npz'))
    assert invalid['status'] == 'invalid_input' and invalid['model_z'] is None
    source = _source(tmp_path)
    monkeypatch.setattr(agent.tools, '_model', lambda: (_ for _ in ()).throw(FileNotFoundError('server checkpoint')))
    unavailable = agent.run_structured(str(source))
    assert unavailable['status'] == 'technical_error' and unavailable['model_z'] is None


def test_no_report_is_explicit_and_does_not_erase_prediction(monkeypatch, tmp_path):
    setup_run(monkeypatch)
    report = agent.run_structured(str(_source(tmp_path)))
    assert report['status'] == 'explanation_incomplete' and report['model_z'] == .42


def test_budget_and_result_copies_cannot_replace_canonical_prediction(monkeypatch):
    monkeypatch.setattr(agent.tools, 'predict_redshift_impl', lambda path: PREDICTION.copy())
    monkeypatch.setattr(agent.tools, 'identify_spectral_lines_impl', lambda path,z: {'z_tested':z,'n_matched':2,'n_expected_in_coverage':2})
    state = agent.RunTools('/opaque.npz'); state.bootstrap()
    tool = state.tools[0]
    for _ in range(4):
        observed = json.loads(tool.call({'npz_path': state.path}))
        observed['result']['z_pred_map'] = 99.
    with pytest.raises(ValueError, match='budget'):
        tool.call({'npz_path': state.path})
    assert state.finish()['model_z'] == .42


def test_evaluator_rejects_an_override_without_losing_baseline(harness, monkeypatch):
    mod, run, rows, _, _ = harness
    monkeypatch.setattr(mod.agent, 'run_structured', lambda *a, **k: {
        'status': 'complete', 'model_z': 9., 'tokens_in': 1, 'tokens_out': 1})
    run()
    assert len(rows()) == 3
    assert all(r['status'] == 'error' and r['z_model'] == '0.5' and r['z_final'] == '' for r in rows())


def test_unknown_tool_sdk_attempt_is_recorded_without_inventing_results(monkeypatch, tmp_path):
    import anthropic
    import httpx
    constructor = anthropic.Anthropic
    setup_run(monkeypatch)
    requests = []
    def reply(request):
        requests.append(json.loads(request.content))
        name = 'imaginary_observatory' if len(requests) == 1 else 'submit_report'
        arguments = {} if len(requests) == 1 else {'observation_ids': ['obs-1']}
        return httpx.Response(200, json=dict(id='simulated', type='message', role='assistant', model='fixture',
            content=[dict(type='tool_use', id=f'call{len(requests)}', name=name, input=arguments)],
            stop_reason='tool_use', stop_sequence=None, usage=dict(input_tokens=1, output_tokens=1)))
    client = constructor(api_key='synthetic-unused',max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    monkeypatch.setattr(agent.anthropic, 'Anthropic', lambda **kwargs: client)
    report = agent.run_structured(str(_source(tmp_path)))
    assert len(requests) == 2
    assert report['model_z'] == .42 and report['status'] == 'explanation_incomplete'
    assert report['policy_violations'] == ['unknown_tool']
    assert [o['tool'] for o in report['observations']] == ['predict_redshift','identify_spectral_lines']
