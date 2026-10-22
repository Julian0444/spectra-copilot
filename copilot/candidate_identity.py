"""Content identities for the 5B candidate and the later installed 5C system."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import anthropic

from copilot import agent,rag,tools,explanation
from copilot.budget import (PINNED_MODEL,Limits,RATES,LONG_PROMPT_RATES,request_configuration,
                            PROMPT_TIER_LIMIT,CASE_MAX_NANODOLLARS,ANALYSIS_CALLS)
from copilot.acceptance_io import sha256,write_json
from desi_fm.predict import model_identity
import desi_fm


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def capture(protocol_dir):
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
    sdk_root=Path(anthropic.__file__).resolve().parent
    sdk_sources={name:sha256(sdk_root/name) for name in
                 ('lib/tools/_beta_runner.py','resources/messages/messages.py')}
    behavior={'code_sha256':code,'auxiliary_code_sha256':auxiliary,'source_content_sha256':digest(code),'prompt_sha256':digest({'system':agent.SYSTEM,'structured_rule':agent.STRUCTURED_RULE}),
              'corpus_revision':rag.corpus_revision(),'corpus_files':rag.corpus_hashes(),'tool_schemas_sha256':digest(schemas),
              'policy':explanation.POLICY_VERSION,'assets':assets,'predictor':model_identity(tools._model()),
              'input_contract':'spectra-input-v3','index_compatibility':'historical encoder/index compatibility remains unverified',
              'llm_proposal':{'model':PINNED_MODEL,'rates_usd_per_million':[n/1000 for n in RATES[PINNED_MODEL]],
                              'long_prompt_rates_usd_per_million':[n/1000 for n in LONG_PROMPT_RATES[PINNED_MODEL]],
                              'prices_verified_on':'2026-10-22','internal_money_unit':'nanodollars',
                              'prompt_bound_limit':PROMPT_TIER_LIMIT,'over_limit_policy':'reject_before_post',
                              'request_configuration':request_configuration(),'analysis_calls':ANALYSIS_CALLS,
                              'case_max_nanodollars':CASE_MAX_NANODOLLARS,'limits':vars(Limits()),'paid_default_usd':0},
              'protocol':protocol,'runtime':{'python':platform.python_version(),'platform':platform.platform(),
                                             'packages':versions,'anthropic_source_sha256':sdk_sources}}
    heads={}
    for name,directory in locations.items():
        try:heads[name]=subprocess.check_output(['git','-C',directory,'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:heads[name]=None
    return {'schema':'spectra-system-identity-v1','kind':'candidate-5b22','behavior':behavior,'behavior_sha256':digest(behavior),
            'source_locations':locations,'source_heads':heads,
            'closure':'Candidate only. 5C must record the final installed identity and justify every behavioral difference before real acceptance.'}


def verify(path,protocol_dir):
    saved=json.loads(Path(path).read_text())
    if saved.get('schema')!='spectra-system-identity-v1' or digest(saved['behavior'])!=saved['behavior_sha256']:
        raise ValueError('Invalid candidate identity')
    current=capture(protocol_dir)
    if current['behavior_sha256']!=saved['behavior_sha256']:
        raise ValueError('Runtime differs from registered identity; register and justify final 5C identity first')
    return saved['behavior_sha256']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('Preserve previous identity; use a new path')
    identity=capture(a.protocol_dir);write_json(a.output,identity)
    print(json.dumps({'output':str(a.output),'sha256':sha256(a.output),'behavior_sha256':identity['behavior_sha256']}))


if __name__=='__main__':main()
