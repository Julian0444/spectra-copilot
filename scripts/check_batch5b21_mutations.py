"""Run the 13 scoped 5B-2.1 mutations in new private copies, never originals.

Each target first passes unchanged. A detected mutation must produce assertion
failures, not collection/import errors. CNN main uses invented fixture identities
and inert outputs only; no real checkpoint, test split or inference is used.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

CP_CASES = {
    'alternative_replaces_model_z': ('copilot/explanation.py',
        "    return deepcopy({'policy': POLICY_VERSION",
        "    if status == 'ambiguous' and alternatives:\n        z = alternatives[0]['z']\n    return deepcopy({'policy': POLICY_VERSION",
        'tests/test_executor_caution.py::test_all_registered_alternatives_and_ambiguity_survive_selection'),
    'drop_ambiguity': ('copilot/explanation.py', '            status = minimum', '            status = status',
        'tests/test_executor_caution.py::test_all_registered_alternatives_and_ambiguity_survive_selection'),
    'drop_alternatives': ('copilot/explanation.py',
        "        alternatives.extend(dict(c, observation_id=obs['id']) for c in data.get('candidates', []))",
        '        pass  # mutation: discard computed alternatives',
        'tests/test_executor_caution.py::test_all_registered_alternatives_and_ambiguity_survive_selection'),
    'skip_input_hash': ('copilot/acceptance.py',
        "                if sha256(item['input_path'])!=item['input_sha256']:raise ValueError('Input identity mismatch')",
        "                if False:raise ValueError('Input identity mismatch')",
        'tests/test_batch5b21_guards.py::test_changed_input_hash_prevents_worker_call'),
    'missing_ledger_certified': ('copilot/acceptance.py',
        "    certified=all(l is not None and l.get('cost_certified') is True and l.get('usd') is not None for l in ledgers)",
        "    certified=all(l is None or (l.get('cost_certified') is True and l.get('usd') is not None) for l in ledgers)",
        'tests/test_batch5b21_guards.py::test_missing_execution_budget_is_unknown_and_stops'),
    'skip_alias_order': ('copilot/acceptance_score.py',
        "    if [r['alias'] for r in rows]!=[r['alias'] for r in manifest['input_identities']]:raise ValueError('Requested identities changed')",
        "    if False:raise ValueError('Requested identities changed')",
        'tests/test_batch5b21_guards.py::test_alias_order_checked_before_labels_even_with_matching_file_hashes'),
    'resume_changed_model_z': ('eval/run_evals.py',
        "            if float(r['z_final']) != float(r['z_model']):", '            if False:',
        'tests/test_batch5b21_guards.py::test_resume_rejects_internally_consistent_alternative_redshift'),
    'outside_lines_as_absences': ('copilot/spectral.py',
        "        expected = [x for x in lines if x['support'] == 'full_window']", '        expected = list(lines)',
        'tests/test_batch5b21_guards.py::test_outside_support_and_gap_lines_are_excluded_from_denominator'),
    'unconditioned_wrong_controls': ('scripts/batch5b_development.py',
        "            if name == 'coverage_conditioned' and support_bin(z) != support_bin(reference):", '            if False:',
        'tests/test_batch5b21_guards.py::test_wrong_controls_retain_expected_line_count_condition'),
}
FM_CASES = {
    'cnn_skip_checkpoint_record': ('scripts/check_batch5b_cnn.py',
        "    artifacts.verify_record(cnn['checkpoint'],CHECKPOINT)", '    pass  # mutation: no checkpoint record verification',
        'tests/test_batch5b_cnn_main.py::test_main_rejects_false_identity_before_loading_checkpoint'),
    'cnn_skip_frozen_identity': ('scripts/check_batch5b_cnn.py',
        "    if cnn['step']!=6000 or cnn['file']!=CHECKPOINT or identity['source_sha256']!=frozen['source']['sha256']:", '    if False:',
        'tests/test_batch5b_cnn_main.py::test_main_rejects_false_identity_before_loading_checkpoint'),
    'cnn_skip_source_environment': ('scripts/check_batch5b_cnn.py',
        "    if artifacts.source_identity()['files']!=frozen['source']['files'] or artifacts.environment()!=identity['environment']:", '    if False:',
        'tests/test_batch5b_cnn_main.py::test_main_rejects_false_identity_before_loading_checkpoint'),
    'cnn_skip_parity_gate': ('scripts/check_batch5b_cnn.py',
        " and report['parity_passed']==24", '',
        'tests/test_batch5b_cnn_main.py::test_main_gate_rejects_one_failed_validation_parity'),
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copilot-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--fm-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    records={}
    for family,source,cases in [('copilot',args.copilot_root,CP_CASES),('fm',args.fm_root,FM_CASES)]:
        for name,(relative,before,after,target) in cases.items():
            copy=args.output/name;copy.mkdir(mode=0o700)
            if family=='copilot':
                shutil.copytree(source/'copilot',copy/'copilot',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
                for path in ('eval/run_evals.py','scripts/batch5b_development.py'):
                    (copy/path).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/path,copy/path)
            else:
                (copy/'scripts').mkdir()
                for path in ('check_batch5b_cnn.py','batch5b_development.py'):
                    shutil.copyfile(source/'scripts'/path,copy/'scripts'/path)
            (copy/'tests').mkdir()
            for path in (source/'tests').glob('*.py'):shutil.copyfile(path,copy/'tests'/path.name)
            env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
            env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(copy)+os.pathsep+str(args.fm_root/'src'),HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
            command=[sys.executable,'-m','pytest','-q',target]
            green=subprocess.run(command,cwd=copy,env=env,capture_output=True,text=True)
            (args.output/(name+'-green.log')).write_text(green.stdout+green.stderr)
            if green.returncode:raise RuntimeError('Unmutated copy failed: '+name)
            path=copy/relative;text=path.read_text()
            if text.count(before)!=1:raise RuntimeError('Mutation target not unique: '+name)
            path.write_text(text.replace(before,after))
            red=subprocess.run(command,cwd=copy,env=env,capture_output=True,text=True)
            (args.output/(name+'-red.log')).write_text(red.stdout+red.stderr)
            detected=red.returncode==1 and 'failed' in red.stdout and 'ERROR collecting' not in red.stdout and 'ImportError' not in red.stdout
            records[name]={'repository':family,'source_file':relative,'test':target,'green_exit':green.returncode,
                           'mutated_exit':red.returncode,'detected':detected,'mutation':after,'copy':str(copy)}
            (args.output/'summary.json').write_text(json.dumps(records,indent=2)+'\n')
            if not detected:raise RuntimeError('Mutation survived or infrastructure failed: '+name)
    print(json.dumps({'mutations':len(records),'detected':sum(r['detected'] for r in records.values())}))


if __name__=='__main__':main()
