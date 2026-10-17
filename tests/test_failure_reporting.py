"""5A: evaluator and real SDK with simulated HTTP; no remote LLM calls."""
import json
import sys
from pathlib import Path
import httpx
import pytest
import anthropic
from copilot import agent
from test_eval_persistence import harness
from test_evals import _source, _install_fake_runner

@pytest.mark.parametrize('baseline', [True, False])
def test_all_failed_is_nonzero_and_summary_is_persisted(harness, monkeypatch, baseline):
    mod, _, rows, out, cases = harness
    if baseline:
        def fail(_): raise ValueError('private-secret-do-not-persist')
        monkeypatch.setattr(mod.tools,'predict_redshift_impl',fail)
    else:
        monkeypatch.setattr(mod.agent,'run_structured',lambda *a,**k: None)
    monkeypatch.setattr(sys,'argv',['eval','--cases',str(cases),'--out',str(out)]+(['--baseline-only'] if baseline else []))
    assert mod.main() == 3
    summary=json.loads(out.with_suffix('.summary.json').read_text())
    assert summary['n']==3 and summary['n_error']==3 and summary['n_valid_results']==0
    assert summary['completion_status']=='failed'
    assert summary['agent']['n']==0 and summary['agent']['rate_015'] is None
    assert summary['results_sha256']==mod.sha256(out)
    assert len(rows())==3
    assert 'private-secret' not in out.with_suffix('.summary.json').read_text()


def test_partial_summary_resume_and_atomic_failure(harness,monkeypatch):
    mod,_,rows,out,cases=harness
    real=mod.agent.run_structured
    monkeypatch.setattr(mod.agent,'run_structured',lambda path,**kw: None if Path(path).stem=='b' else real(path,**kw))
    argv=['eval','--cases',str(cases),'--out',str(out)]
    monkeypatch.setattr(sys,'argv',argv)
    assert mod.main()==2
    target=out.with_suffix('.summary.json'); before=target.read_bytes()
    summary=json.loads(before); assert summary['completion_status']=='partial' and summary['n_valid_results']==2
    replace=mod.os.replace
    def fail(src,dst):
        if Path(dst)==target: raise OSError('simulated atomic failure')
        return replace(src,dst)
    monkeypatch.setattr(mod.os,'replace',fail)
    monkeypatch.setattr(sys,'argv',argv+['--resume'])
    with pytest.raises(OSError):mod.main()
    assert target.read_bytes()==before and len(rows())==3
    monkeypatch.setattr(mod.os,'replace',replace)
    monkeypatch.setattr(mod.agent,'run_structured',real)
    assert mod.main()==0
    final=json.loads(target.read_text())
    assert final['run_id']==summary['run_id'] and final['n_valid_results']==3
    assert final['completion_status']=='complete' and final['results_sha256']==mod.sha256(out)


@pytest.mark.parametrize('preamble',['','Thinking about the spectrum.'])
def test_report_exhaustion_sdk_trace_and_cli(tmp_path,monkeypatch,preamble,capsys):
    sdk_client = anthropic.Anthropic
    source=_source(tmp_path);_install_fake_runner(monkeypatch)
    requests=[]
    def reply(request):
        body=json.loads(request.content); requests.append(body)
        blocks=([{'type':'text','text':preamble}] if preamble else [])
        blocks += [{'type':'tool_use','id':f'call{len(requests)}','name':'lookup_reference','input':{'query':'DESI'}}]
        return httpx.Response(200,json={'id':'simulated','type':'message','role':'assistant','model':'fixture','content':blocks,'stop_reason':'tool_use','stop_sequence':None,'usage':{'input_tokens':1,'output_tokens':1}})
    client=sdk_client(api_key='synthetic-unused',http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    monkeypatch.setattr(agent.anthropic,'Anthropic',lambda:client)
    target=tmp_path/'trace.json'
    with pytest.raises(RuntimeError,match='iteration_limit'):
        agent.run(str(source),model='claude-haiku-4-5',transcript=str(target))
    assert len(requests)==8
    assert len(json.loads(target.read_text()))>=8
    status=json.loads(target.with_suffix('.status.json').read_text())
    assert status['status']=='error' and status['code']=='iteration_limit'
    assert str(source) not in target.read_text() and 'z_true' not in target.read_text()
    monkeypatch.setattr(sys,'argv',['agent',str(source),'--model','claude-haiku-4-5'])
    assert agent.main()==2
    assert 'iteration_limit' in capsys.readouterr().err


def test_all_failed_cli_process_exit_code(harness):
    import subprocess
    mod,_,_,out,cases=harness
    code="from copilot import tools; import runpy; tools.predict_redshift_impl=lambda p: (_ for _ in ()).throw(ValueError('synthetic')); runpy.run_path("+repr(str(Path(mod.__file__)))+",run_name='__main__')"
    result=subprocess.run([sys.executable,'-c',code,'--cases',str(cases),'--out',str(out),'--baseline-only'],capture_output=True,text=True,timeout=15)
    assert result.returncode==3, result.stdout+result.stderr
    assert json.loads(out.with_suffix('.summary.json').read_text())['n_error']==3
