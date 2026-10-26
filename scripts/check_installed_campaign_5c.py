"""Installed worker boundary check with invalid development input; no key or POST."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from copilot import acceptance,campaign,candidate_identity
from copilot.acceptance_io import sha256,write_json
from copilot.budget import CASE_MAX_USD


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','protocol-dir','build-manifest','invalid-input'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(mode=0o700)
    assert not os.environ.get('ANTHROPIC_API_KEY') and not os.environ.get('PYTHONPATH')
    assert 'site-packages' in acceptance.__file__
    docs=a.output/'docs';shutil.copytree(a.protocol_dir,docs)
    root=a.output/'invented-campaign'
    spec=json.loads((docs/'protocol/batch5c-campaign.json').read_text())
    spec['campaign_id']='offline-installed-boundary-fixture'
    spec['directory_sha256']=hashlib.sha256(str(root.resolve()).encode()).hexdigest()
    write_json(docs/'protocol/batch5c-campaign.json',spec);campaign.initialize(root,docs)
    identity=a.output/'identity.json'
    write_json(identity,candidate_identity.capture(docs,kind='installed-5c',build_manifest=a.build_manifest))
    run=a.output/'run';(run/'traces').mkdir(parents=True);(run/'inputs').mkdir()
    alias='a'*24;source=run/'inputs'/(alias+'.npz');source.write_bytes(a.invalid_input.read_bytes())
    item={'alias':alias,'input_path':str(source),'input_sha256':sha256(source),'effort':'low'}
    campaign.claim(root,docs,'pilot',run,{'low':sha256(identity)})
    write_json(run/'manifest.json',{'phase':'pilot','effort':'low','variant_identities':{'low':sha256(identity)},
                                   'input_identities':[{k:v for k,v in item.items() if k!='input_path'}]})
    result,timed_out=acceptance.run_worker(item,run/'traces',CASE_MAX_USD,candidate=identity,protocol_dir=docs,
                                        campaign_dir=root,phase='pilot',audit_path=root/'paid-calls.jsonl')
    assert not timed_out and result['status']=='invalid_input',result.get('completion_code')
    assert result['execution_budget']['calls']==0 and result['execution_budget']['cost_certified']
    assert not (root/'paid-calls.jsonl').exists()
    assert (root/('pilot.'+alias+'.worker.json')).is_file()
    record={'installed_module':acceptance.__file__,'python':sys.executable,'invalid_input_sha256':sha256(source),
            'worker_substituted':False,'timeout':False,'result':'invalid_input','paid_calls':0,
            'known_usd':0,'cost_certified':True,'real_campaign_used':False,'acceptance_opened':False}
    write_json(a.output/'verification.json',record);print(json.dumps(record))


if __name__=='__main__':main()
