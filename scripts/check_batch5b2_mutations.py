"""Bounded destructive variants only in new private copies; originals are read-only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
CASES={
 'model_z':('copilot/explanation.py',"    z = canonical_z(prediction) if prediction is not None else None", "    z = 9.99 if prediction is not None else None",'tests/test_explanatory_policy.py::test_valid_report_and_abstention_keep_executor_prediction'),
 'ignore_mask_ivar':('copilot/spectral.py',"    segments = _segments(f, w, v, m)","    m = np.zeros_like(m, dtype=bool)\n    v = np.ones_like(v)\n    segments = _segments(f, w, v, m)",'tests/test_spectral_measurements.py::test_invalidated_peak_cannot_contribute'),
 'invented_citation':('copilot/explanation.py',"    citations = [retrieved[i] for i in reference_ids]", "    citations = [dict(retrieved[i], id='fabricated-citation') for i in reference_ids]",'tests/test_citation_policy.py::test_exact_fragment_provenance_is_rendered_without_new_attribution'),
}


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output.mkdir(mode=0o700,parents=True,exist_ok=False);records={}
 for name,(relative,before,after,target) in CASES.items():
  directory=a.output/name;directory.mkdir(mode=0o700)
  shutil.copytree(ROOT/'copilot',directory/'copilot',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  (directory/'tests').mkdir()
  for source in (ROOT/'tests').glob('*.py'):shutil.copyfile(source,directory/'tests'/source.name)
  env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=str(directory)+os.pathsep+env.get('PYTHONPATH','')
  cmd=[sys.executable,'-m','pytest','-q',target]
  green=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True)
  (a.output/(name+'-green.log')).write_text(green.stdout+green.stderr)
  if green.returncode:raise RuntimeError('Unmutated copy must pass before mutation')
  source=directory/relative;text=source.read_text()
  if text.count(before)!=1:raise RuntimeError('Mutation target must be unique')
  source.write_text(text.replace(before,after))
  red=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True)
  (a.output/(name+'-red.log')).write_text(red.stdout+red.stderr)
  detected=red.returncode==1 and 'failed' in red.stdout and 'ERROR collecting' not in red.stdout
  records[name]={'green_exit':green.returncode,'mutated_exit':red.returncode,'detected':detected,'test':target,
                 'source_file':relative,'copy':str(directory),'mutation':after.strip()}
  if not detected:raise RuntimeError('Mutation survived or test infrastructure failed')
 (a.output/'summary.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps({name:record['detected'] for name,record in records.items()}))


if __name__=='__main__':main()
