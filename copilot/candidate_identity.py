"""Content identities for the 5B candidate and the later installed 5C system."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sysconfig
import anthropic

from copilot import agent,rag,tools,explanation
from copilot.budget import (PINNED_MODEL,Limits,RATES,LONG_PROMPT_RATES,request_configuration,
                            PROMPT_TIER_LIMIT,CASE_MAX_NANODOLLARS,ANALYSIS_CALLS,AUTHORIZED_EFFORTS)
from copilot.acceptance_io import sha256,write_json
from desi_fm.predict import model_identity
import desi_fm


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def installed_evidence(build_manifest):
    """Check wheel provenance, import locations and every project RECORD hash."""
    from urllib.parse import unquote,urlparse
    if build_manifest is None:raise ValueError('Installed build manifest required')
    build=json.loads(Path(build_manifest).read_text())
    names={'desi-fm':'desi_fm','spectra-copilot':'copilot'}
    if build.get('schema')!='spectra-installed-build-v1' or set(build.get('packages',{}))!=set(names):
        raise ValueError('Both installed package provenances required')
    purelib=Path(sysconfig.get_path('purelib')).resolve();result={}
    for distribution,module_name in names.items():
        package=build['packages'][distribution];dist=importlib.metadata.distribution(distribution)
        module=importlib.import_module(module_name);location=Path(module.__file__).resolve()
        expected=Path(dist.locate_file(module_name+'/__init__.py')).resolve()
        if not location.is_relative_to(purelib) or location!=expected:
            raise ValueError('Import does not come from installed distribution')
        direct=json.loads(dist.read_text('direct_url.json') or '{}')
        if direct.get('dir_info',{}).get('editable') or not direct.get('archive_info'):
            raise ValueError('Noneditable wheel installation required')
        wheel=Path(package['wheel_path'])
        if (sha256(wheel)!=package['wheel_sha256'] or dist.version!=package['version']
                or not package.get('source_commit') or len(package['source_commit'])!=40):
            raise ValueError('Installed package provenance differs')
        if direct.get('archive_info',{}).get('hashes',{}).get('sha256')!=package['wheel_sha256']:
            raise ValueError('Installed wheel hash differs')
        checked=0
        for file in dist.files or []:
            if file.hash:
                if file.hash.mode!='sha256':raise ValueError('Unexpected distribution hash algorithm')
                actual=base64.urlsafe_b64encode(hashlib.sha256(Path(dist.locate_file(file)).read_bytes()).digest()).decode().rstrip('=')
                if actual!=file.hash.value:raise ValueError('Installed distribution RECORD mismatch')
                checked+=1
        if not checked:raise ValueError('Installed distribution has no verified files')
        result[distribution]={'version':dist.version,'source_commit':package['source_commit'],
            'wheel_sha256':package['wheel_sha256'],'record_sha256':digest(dist.read_text('RECORD')),'files_checked':checked}
    return result


LLM_EXECUTION_MODULES={'__init__.py','acceptance.py','acceptance_io.py','acceptance_worker.py','agent.py',
    'budget.py','campaign.py','candidate_identity.py','explanation.py','rag.py','report.py','spectral.py','tools.py'}


def llm_path_digest(behavior):
    """Pre-registered execution subset; full identity still hashes every source."""
    path={k:v for k,v in behavior.items() if k not in
          {'protocol','auxiliary_code_sha256','installation','source_content_sha256','code_sha256'}}
    path['code_sha256']={k:v for k,v in behavior['code_sha256'].items()
                        if k.startswith('desi_fm/') or k.removeprefix('copilot/') in LLM_EXECUTION_MODULES}
    return digest(path)


def capture(protocol_dir,effort='low',*,kind='candidate-5b22',build_manifest=None):
    request_configuration(effort)
    if kind not in {'candidate-5b22','installed-5c'}:raise ValueError('Unknown identity kind')
    installation=installed_evidence(build_manifest) if kind=='installed-5c' else None
    protocol_dir=Path(protocol_dir)
    code={};locations={}
    for name,module in [('copilot',agent),('desi_fm',desi_fm)]:
        directory=Path(module.__file__).resolve().parent
        locations[name]=str(directory)
        for path in sorted(directory.rglob('*.py')):
            code[name+'/'+str(path.relative_to(directory))]=sha256(path)
    auxiliary={}
    for name,path in [('cnn_harness',Path(desi_fm.__file__).resolve().parents[2]/'scripts/check_batch5b_cnn.py'),
                      ('cnn_development_reader',Path(desi_fm.__file__).resolve().parents[2]/'scripts/batch5b_development.py'),
                      ('legacy_evaluator',Path(agent.__file__).resolve().parent.parent/'eval/run_evals.py')]:
        auxiliary[name]=sha256(path) if path.is_file() else None
    checkpoint=os.environ.get('DESI_FM_CKPT')
    if not checkpoint or not Path(checkpoint).is_file():raise ValueError('Explicit verified local predictor checkpoint required; no downloads')
    index_dir=Path(os.environ.get('DESI_FM_INDEX_DIR') or tools.DATA_DIR)
    assets={name:{'sha256':sha256(path),'bytes':path.stat().st_size} for name,path in
            [('predictor_checkpoint',Path(checkpoint)),('faiss_index',index_dir/'spectra.faiss'),('index_metadata',index_dir/'spectra_meta.npz')]}
    schemas=[t.to_dict() for t in agent.RunTools('spectrum.npz').tools]
    versions={}
    for name in ('numpy','scipy','torch','pyarrow','anthropic','httpx','faiss-cpu','rank_bm25','mcp','pydantic'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    protocol={name:sha256(protocol_dir/name) for name in
              ('BATCH_5B_PROTOCOL.md','protocol/batch5b-development.json','evidence/batch5b-commitment.json')}
    for name in ('protocol/batch5c-development-registry.json','protocol/batch5c-campaign.json'):
        if (protocol_dir/name).is_file():protocol[name]=sha256(protocol_dir/name)
        elif installation:raise ValueError('Installed 5C requires campaign and development commitments')
    sdk_root=Path(anthropic.__file__).resolve().parent
    sdk_sources={name:sha256(sdk_root/name) for name in
                 ('lib/tools/_beta_runner.py','resources/messages/messages.py','resources/beta/messages/messages.py')}
    behavior={'code_sha256':code,'auxiliary_code_sha256':auxiliary,'source_content_sha256':digest(code),'prompt_sha256':digest({'system':agent.SYSTEM,'structured_rule':agent.STRUCTURED_RULE}),
              'corpus_revision':rag.corpus_revision(),'corpus_files':rag.corpus_hashes(),'tool_schemas_sha256':digest(schemas),
              'policy':explanation.POLICY_VERSION,'assets':assets,'predictor':model_identity(tools._model()),
              'input_contract':'spectra-input-v3','index_compatibility':'historical encoder/index compatibility remains unverified',
              'llm_proposal':{'model':PINNED_MODEL,'rates_usd_per_million':[n/1000 for n in RATES[PINNED_MODEL]],
                              'long_prompt_rates_usd_per_million':[n/1000 for n in LONG_PROMPT_RATES[PINNED_MODEL]],
                              'prices_verified_on':'2026-10-25','internal_money_unit':'nanodollars',
                              'prompt_bound_limit':PROMPT_TIER_LIMIT,'over_limit_policy':'reject_before_post',
                              'request_configuration':request_configuration(effort),'analysis_calls':ANALYSIS_CALLS,
                              'case_max_nanodollars':CASE_MAX_NANODOLLARS,'limits':vars(Limits()),'paid_default_usd':0},
              'protocol':protocol,'runtime':{'python':platform.python_version(),'platform':platform.platform(),
                                             'packages':versions,'anthropic_source_sha256':sdk_sources}}
    if installation:
        behavior['installation']=installation
        behavior['endpoint_policy']={'base_url':'https://api.anthropic.com','automatic_retries':0}
    heads={}
    for name,directory in locations.items():
        if installation:
            heads[name]=installation['spectra-copilot' if name=='copilot' else 'desi-fm']['source_commit'];continue
        try:heads[name]=subprocess.check_output(['git','-C',directory,'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL,
                                               env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
        except subprocess.CalledProcessError:heads[name]=None
    return {'schema':'spectra-system-identity-v1','kind':kind,'behavior':behavior,'behavior_sha256':digest(behavior),
            'llm_path_sha256':llm_path_digest(behavior),'build_manifest':str(Path(build_manifest).resolve()) if build_manifest else None,
            'source_locations':locations,'source_heads':heads,
            'closure':'Installed local identity; scientific acceptance remains separate.' if installation else
                      'Candidate only. 5C must record the final installed identity and justify every behavioral difference before real acceptance.'}


def verify(path,protocol_dir,effort='low',require_installed=False):
    saved=json.loads(Path(path).read_text())
    if require_installed and saved.get('kind')!='installed-5c':raise ValueError('Paid execution requires installed-5c identity')
    if saved.get('schema')!='spectra-system-identity-v1' or digest(saved['behavior'])!=saved['behavior_sha256']:
        raise ValueError('Invalid candidate identity')
    current=capture(protocol_dir,effort=effort,kind=saved.get('kind','candidate-5b22'),build_manifest=saved.get('build_manifest'))
    if current['behavior_sha256']!=saved['behavior_sha256']:
        raise ValueError('Runtime differs from registered identity; register and justify final 5C identity first')
    return saved['behavior_sha256']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--effort',choices=AUTHORIZED_EFFORTS,default='low')
    p.add_argument('--kind',choices=['candidate-5b22','installed-5c'],default='candidate-5b22')
    p.add_argument('--build-manifest',type=Path)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('Preserve previous identity; use a new path')
    identity=capture(a.protocol_dir,effort=a.effort,kind=a.kind,build_manifest=a.build_manifest);write_json(a.output,identity)
    print(json.dumps({'output':str(a.output),'sha256':sha256(a.output),'behavior_sha256':identity['behavior_sha256']}))


if __name__=='__main__':main()
