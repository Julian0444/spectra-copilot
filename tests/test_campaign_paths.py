"""Real parent/worker/campaign flow keeps the child's cwd boundary explicit."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from copilot import acceptance,acceptance_worker,agent,candidate_identity
from copilot.acceptance_io import sha256,write_json
from test_development_execution import fixtures,campaign


@pytest.mark.parametrize('relative',['none','campaign','output','protocol','candidate'])
def test_parent_worker_flow_resolves_paths_before_claim(tmp_path,monkeypatch,relative):
    base=tmp_path.resolve();reg,plan=fixtures(base);_,root,docs=campaign(base,sha256(reg))
    (docs/'protocol/batch5c-development-registry.json').write_bytes(reg.read_bytes())
    low=base/'low.json';medium=base/'medium.json';write_json(low,{});write_json(medium,{})
    reached=[]
    monkeypatch.setattr(candidate_identity,'verify',lambda *a,**k:None)
    def scientific(payload,**kwargs):
        reached.append(kwargs['effort']);return agent.explanation.result(status='technical_error')
    monkeypatch.setattr(agent,'run_structured',scientific)
    def process(args,*,cwd,**kwargs):
        start=args.index('copilot.acceptance_worker');old=os.getcwd();argv=sys.argv
        try:
            os.chdir(cwd);sys.argv=['worker',*args[start+1:]]
            try:code=acceptance_worker.main()
            except SystemExit as exc:code=exc.code
        finally:os.chdir(old);sys.argv=argv
        return SimpleNamespace(returncode=code,stdout='',stderr='')
    monkeypatch.setattr(acceptance.subprocess,'run',process)
    monkeypatch.chdir(base)
    result=acceptance.execute_plan(plan,Path('run') if relative=='output' else base/'run',usd=2.4,
        candidate=Path('low.json') if relative=='candidate' else low,
        candidate_medium=Path('medium.json') if relative=='candidate' else medium,
        campaign_dir=Path('campaign') if relative=='campaign' else root,
        protocol_dir=Path('docs') if relative=='protocol' else docs)
    assert len(reached)==24 and reached==['low','medium','medium','low']*6
    assert len(list(root.glob('pilot.*.worker.json')))==24 and result['cost']['certified']
