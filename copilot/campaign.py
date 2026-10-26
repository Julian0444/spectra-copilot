"""Exclusive, append-only phase claims. No credential or scoring-label access."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from copilot.acceptance_io import sha256,seal_record_path

CAPS={'pilot':2400000000,'confirmation':1200000000,'proposal':12800000000}


def exclusive_json(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def specification(directory,protocol_dir):
    spec=json.loads((Path(protocol_dir)/'protocol/batch5c-campaign.json').read_text())
    if (spec.get('schema')!='batch5c-campaign-v1' or spec.get('phase_caps_nanodollars')!=CAPS
            or spec.get('directory_sha256')!=hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()):
        raise ValueError('Campaign differs from protocol commitment')
    return spec


def initialize(directory,protocol_dir):
    spec=specification(directory,protocol_dir)
    directory=Path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=False)
    exclusive_json(directory/'campaign.json',spec)


@contextmanager
def locked(directory,protocol_dir):
    directory=Path(directory)
    registered=json.loads((directory/'campaign.json').read_text())
    if registered!=specification(directory,protocol_dir):raise ValueError('Campaign commitment changed')
    with (directory/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield registered
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def claim(directory,protocol_dir,phase,output,identities):
    directory=Path(directory)
    if phase not in CAPS:raise ValueError('Unknown phase')
    with locked(directory,protocol_dir) as spec:
        if (directory/(phase+'.claim.json')).exists():raise ValueError('One attempt per phase')
        for prior in CAPS:
            if (directory/(prior+'.claim.json')).exists():
                close=directory/(prior+'.close.json')
                if not close.exists():raise ValueError('An open phase blocks every new paid attempt')
                if json.loads(close.read_text()).get('certified') is not True:
                    raise ValueError('An uncertified phase blocks every new paid attempt')
        if phase!='pilot' and not (directory/'pilot.close.json').exists():
            raise ValueError('Pilot must finish before later phases')
        exclusive_json(directory/(phase+'.claim.json'),{'schema':'batch5c-phase-claim-v1',
            'campaign_id':spec['campaign_id'],'phase':phase,'output':str(Path(output).resolve()),
            'cap_nanodollars':CAPS[phase],'identities':identities,'created_ns':time.time_ns()})
    return CAPS[phase]


def close(directory,protocol_dir,phase,output):
    from copilot.acceptance_score import validate_seal
    from copilot.acceptance import summarize
    directory=Path(directory);output=Path(output)
    with locked(directory,protocol_dir):
        claimed=json.loads((directory/(phase+'.claim.json')).read_text())
        if claimed['output']!=str(output.resolve()):raise ValueError('Different claimed run')
        rows,manifest,seal,seal_hash,_=validate_seal(output)
        summary=summarize(rows);cost=summary['cost']
        certified=cost['certified'] and cost['known_nanodollars']<=CAPS[phase]
        exclusive_json(directory/(phase+'.close.json'),{'schema':'batch5c-phase-close-v1',
            'certified':bool(certified),'known_nanodollars':cost['known_nanodollars'],
            'seal_sha256':seal_hash,'seal_record_sha256':sha256(seal_record_path(output)),
            'outputs_sha256':seal['outputs_sha256'],'calls':summary['llm_calls'],'closed_ns':time.time_ns()})


def authorize_worker(args):
    """Bind one worker attempt to its parent's open, committed campaign."""
    from copilot.budget import CASE_MAX_NANODOLLARS,nanodollars
    import re
    if args.campaign_dir is None or args.phase not in CAPS or not re.fullmatch('[0-9a-f]{24}',args.alias or ''):
        raise ValueError('Registered campaign row required')
    directory=Path(args.campaign_dir)
    with locked(directory,args.protocol_dir):
        claimed=json.loads((directory/(args.phase+'.claim.json')).read_text())
        if (directory/(args.phase+'.close.json')).exists():raise ValueError('Phase already closed')
        output=Path(claimed['output'])
        identity_hash=sha256(args.candidate)
        if claimed['identities'].get(args.effort)!=identity_hash:raise ValueError('Different worker identity')
        manifest=json.loads((output/'manifest.json').read_text())
        if manifest['phase']!=args.phase or manifest['variant_identities'].get(args.effort)!=identity_hash:
            raise ValueError('Different manifest')
        items=[i for i in manifest['input_identities'] if i['alias']==args.alias]
        if len(items)!=1 or items[0].get('effort',manifest['effort'])!=args.effort:
            raise ValueError('Different worker row')
        if items[0]['input_sha256']!=args.expected_sha256:raise ValueError('Different worker bytes')
        required={args.input:output/'inputs'/(args.alias+'.npz'),
                  args.progress:output/'traces'/(args.alias+'.progress.json'),
                  args.result:output/'traces'/(args.alias+'.result.json'),
                  args.audit_path:directory/'paid-calls.jsonl'}
        if any(actual is None or Path(actual).resolve()!=expected.resolve() for actual,expected in required.items()):
            raise ValueError('Worker paths escape claimed run')
        if nanodollars(args.budget_usd)!=CASE_MAX_NANODOLLARS or args.deadline_monotonic is None:
            raise ValueError('Worker ceiling or deadline differs')
        exclusive_json(directory/(args.phase+'.'+args.alias+'.worker.json'),
                       {'identity_sha256':identity_hash,'input_sha256':args.expected_sha256,'created_ns':time.time_ns()})


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init'])
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--protocol-dir',type=Path,required=True)
    a=p.parse_args();initialize(a.directory,a.protocol_dir)


if __name__=='__main__':main()
