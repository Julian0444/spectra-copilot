"""Seven required 5B-2.2 mutations, each with a green baseline in private copies."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

CASES={
    'haiku45_price':('copilot/budget.py', [('PINNED_MODEL:(100,500)','PINNED_MODEL:(1000,5000)')],
        'tests/test_haiku55_budget.py::test_fixed_model_explicit_settings_and_official_two_tier_prices'),
    'old_worker_ceiling':('copilot/acceptance.py', [("TERMINAL=explanation.STATES | {'timeout'}", "TERMINAL=explanation.STATES | {'timeout'}\nCASE_MAX_USD=.08448")],
        'tests/test_haiku55_accounting.py::test_all_128_invented_cases_receive_new_worker_budget_without_float_drift'),
    'round_to_integer_microdollars':('copilot/budget.py', [('cost=n_in*RATES[self.model][0]+n_out*RATES[self.model][1]',
        'cost=((n_in*RATES[self.model][0]+n_out*RATES[self.model][1])//1000)*1000')],
        'tests/test_haiku55_budget.py::test_sub_microdollar_reservation_and_settlement_are_exact'),
    'arbitrary_output_config':('copilot/budget.py', [('if any(body.get(k)!=v for k,v in request_configuration().items()):',
        "if body.get('thinking')!=request_configuration()['thinking']:")],
        'tests/test_haiku55_budget.py::test_unapproved_request_settings_rejected'),
    'over_100000_prompt':('copilot/budget.py', [
        ("if model==PINNED_MODEL and n_in>PROMPT_TIER_LIMIT:raise BudgetStop('prompt_tier_exceeded')",'if False:pass'),
        ("if self.model==PINNED_MODEL and n_in>PROMPT_TIER_LIMIT:raise BudgetStop('prompt_tier_exceeded')",'if False:pass')],
        'tests/test_haiku55_budget.py::test_prompt_bound_at_threshold_is_allowed_and_above_is_rejected'),
    'refusal_not_terminal':('copilot/agent.py', [("if stop_reason in {'refusal','max_tokens'}:","if stop_reason in {'max_tokens'}:")],
        'tests/test_haiku55_agent.py::test_terminal_model_stop_preserves_prediction_and_never_executes_tool_or_retries'),
    'scorer_without_state':('copilot/acceptance_score.py', [("('status','explanation','alternatives','citations')", "('explanation','alternatives','citations')")],
        'tests/test_scorer_state.py'),
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    source=Path(__file__).resolve().parents[1];results={}
    for name,(file,changes,test) in CASES.items():
        copy=args.output/name;copy.mkdir(mode=0o700)
        shutil.copytree(source/'copilot',copy/'copilot',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        (copy/'tests').mkdir()
        # Copy only selected regressions and their fixture dependencies. In particular,
        # protocol-generator tests are authorized only at the original exact path.
        for filename in ('conftest.py','test_haiku55_budget.py','test_haiku55_accounting.py',
                         'test_haiku55_agent.py','test_scorer_state.py','test_evals.py',
                         'test_explanatory_policy.py','test_eval_persistence.py'):
            shutil.copyfile(source/'tests'/filename,copy/'tests'/filename)
        shutil.copyfile(source/'pyproject.toml',copy/'pyproject.toml')
        offline=copy/'offline';offline.mkdir()
        (offline/'sitecustomize.py').write_text('import socket\ndef blocked(*a,**k): raise RuntimeError("Mutation tests forbid network")\nsocket.socket.connect=socket.socket.connect_ex=socket.create_connection=socket.getaddrinfo=blocked\n')
        env={k:v for k,v in os.environ.items() if not k.endswith(('API_KEY','AUTH_TOKEN'))}
        env.update(PYTHONPATH=os.pathsep.join([str(offline),str(copy),env.get('PYTHONPATH','')]),PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-m','pytest','-q',test,'-p','no:cacheprovider']
        def run(phase):
            r=subprocess.run(command,cwd=copy,env=env,capture_output=True,text=True)
            (args.output/(name+'-'+phase+'.log')).write_text(r.stdout+r.stderr)
            return r
        green=run('green')
        if green.returncode:raise RuntimeError('Baseline failed: '+name)
        path=copy/file;content=path.read_text()
        for before,after in changes:
            expected=2 if name=='round_to_integer_microdollars' else 1
            if content.count(before)!=expected:raise RuntimeError('Unexpected mutation targets: '+name)
            content=content.replace(before,after)
        path.write_text(content)
        red=run('red')
        detected=red.returncode==1 and 'failed' in red.stdout and 'ERROR collecting' not in red.stdout and 'ImportError' not in red.stdout
        results[name]={'file':file,'test':test,'baseline_exit':green.returncode,'mutated_exit':red.returncode,'detected':detected}
        (args.output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
        if not detected:raise RuntimeError('Mutation survived or infrastructure failed: '+name)
    print(json.dumps({'mutations':len(results),'detected':sum(r['detected'] for r in results.values()),'green_baselines':len(results)}))


if __name__=='__main__':main()
