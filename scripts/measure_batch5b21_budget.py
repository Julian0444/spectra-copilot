"""HISTORICAL 5B-2.1 / Haiku 4.5 replay, never acceptance.

Real SDK/tool results, scripted responses, mandatory MockTransport and blocked
sockets. Counterfactual conversations serialize 3..8 turns even beyond the
production reservation stop. Replay uses unchanged Budget/Limits to report
which requests would be admitted; no production policy or limits are replaced.
Token usage is unknowable without a real LLM: bound and illustrative estimates
are explicitly separate. There is no provider call, billing or LLM validation.
"""
import argparse
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

import anthropic
import httpx
import numpy as np
import torch

from copilot import agent, rag, tools
from copilot.acceptance_io import sha256,write_json
from copilot.budget import Budget,Limits,BudgetStop,HISTORICAL_MODEL,request_bound
from desi_fm.inputs import SpectrumInputError
from batch5b_development import read_development,materialize

PROFILES=('full_reserved_bound','illustrative_2_bytes_per_token','illustrative_4_bytes_per_token')
PINNED_MODEL=HISTORICAL_MODEL
HISTORICAL_LIMITS=Limits(input_tokens=64000,output_tokens=4096,max_output_per_call=512)


def replay(requests,profile):
    from dataclasses import replace
    ledger=Budget(model=HISTORICAL_MODEL,limits=replace(HISTORICAL_LIMITS,usd=.1));ledger.begin();admitted=0;reason=None
    for row in requests:
        try:ticket=ledger.reserve(row['input_bound'],512)
        except BudgetStop as exc:reason=exc.code;break
        if profile=='full_reserved_bound':n_in,n_out=row['input_bound'],512
        else:
            divisor=2 if profile=='illustrative_2_bytes_per_token' else 4
            n_in=min(row['input_bound'],math.ceil(row['wire_bytes']/divisor)+496)
            n_out=min(512,math.ceil(row['response_bytes']/divisor))
        ledger.settle(ticket,{'input_tokens':n_in,'output_tokens':n_out});admitted+=1
    return {'admitted_calls':admitted,'requested_calls':len(requests),'all_fit':admitted==len(requests),
            'stop_reason':reason,'simulated_ledger':ledger.snapshot(),
            'interpretation':'Assumed usage only; not observed tokens or provider billing.'}


def probe(path,turns,request_directory):
    """Serialize the current SDK conversation with scripted tool choices."""
    state=agent.RunTools(path);state.bootstrap()
    errors=max(0,turns-6)
    actions=['schema_error']*errors+['lines','reference','neighbors','alternative','reconstruction'][:turns-errors-1]+['submit']
    assert len(actions)==turns and state.calls==1
    requests=[];request_directory=Path(request_directory);request_directory.mkdir(parents=True,exist_ok=False)

    def reply(request):
        row=requests[-1];row['wire_bytes']=len(request.content);row['wire_sha256']=hashlib.sha256(request.content).hexdigest()
        file=request_directory/f'request-{len(requests):02d}.json';file.write_bytes(request.content);file.chmod(0o600)
        action=actions[len(requests)-1];z=agent.explanation.canonical_z(state.prediction)
        if action=='schema_error':name,args='lookup_reference',{'query':'spectral lines','k':0}
        elif action=='lines':name,args='identify_spectral_lines',{'npz_path':path,'z':z}
        elif action=='reference':name,args='lookup_reference',{'query':'single line ambiguity emission absorption','k':3}
        elif action=='neighbors':name,args='find_similar_spectra',{'npz_path':path,'k':5}
        elif action=='alternative':
            candidates=[c for o in state.observations if o['tool']=='identify_spectral_lines' and not o.get('error') for c in o['result']['candidates']]
            name,args='identify_spectral_lines',{'npz_path':path,'z':candidates[0]['z'] if candidates else z}
        elif action=='reconstruction':name,args='reconstruct_spectrum',{'npz_path':path,'mask_ratio':.5}
        else:name,args='submit_report',{'observation_ids':[o['id'] for o in state.observations],'assessment':'descriptive'}
        content=[{'type':'tool_use','id':f'turn-{len(requests)}','name':name,'input':args}]
        row['response_bytes']=len(json.dumps(content,ensure_ascii=False,separators=(',',':')).encode())
        row['scripted_action']=action
        return httpx.Response(200,json={'id':f'message-{len(requests)}','type':'message','role':'assistant','model':PINNED_MODEL,
            'content':content,'stop_reason':'tool_use','stop_sequence':None,'usage':{'input_tokens':0,'output_tokens':0}})

    with anthropic.Anthropic(api_key='unused-offline-fixture',max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(reply))) as client:
        original=client.beta.messages._post
        def record_request(endpoint,*args,**kwargs):
            bound,n_out=request_bound(kwargs['body'],PINNED_MODEL)
            assert n_out==512 and endpoint.split('?')[0]=='/v1/messages'
            requests.append({'turn':len(requests)+1,'input_bound':bound,'bytes_used_by_bound':bound-4096,'output_reserved':n_out})
            return original(endpoint,*args,**kwargs)
        client.beta.messages._post=record_request
        runner=client.beta.messages.tool_runner(model=PINNED_MODEL,max_tokens=512,max_iterations=8,
            system=agent.system_prompt(state.prediction['model_identity'])+agent.STRUCTURED_RULE,tools=state.tools,
            messages=[{'role':'user','content':f'Analyze the spectrum in {path} and '+
                'submit the result via submit_report. Initial executor observation: '+json.dumps(state.observations[0])}],
            **agent.request_kwargs(PINNED_MODEL))
        for message in runner:
            runner.generate_tool_call_response()
            if state.result is not None:break
    assert len(requests)==turns
    measurements=[o for o in state.observations if o['tool']=='identify_spectral_lines' and not o.get('error')]
    return {'turns':turns,'requests':requests,'profiles':{name:replay(requests,name) for name in PROFILES},
            'analysis_calls_including_bootstrap':state.calls,'scripted_terminal_state':state.finish()['status'],
            'spectral_results':[{'full_json_bytes':len(json.dumps(o).encode()),'wire_json_bytes':len(json.dumps(agent.wire_observation(o)).encode()),
                                 'candidates':len(o['result']['candidates'])} for o in measurements]}


@contextmanager
def cached_measurements():
    """Reuse exact deterministic payloads within one case across turn scenarios."""
    with ExitStack() as stack:
        for module,name in [(tools,n) for n in ('predict_redshift_impl','identify_spectral_lines_impl','find_similar_spectra_impl','reconstruct_spectrum_impl')]+[(rag,'lookup_reference_impl')]:
            original=getattr(module,name);cache={}
            def memo(*args,_original=original,_cache=cache,**kwargs):
                key=json.dumps([args,kwargs],sort_keys=True)
                if key not in _cache:_cache[key]=_original(*args,**kwargs)
                return deepcopy(_cache[key])
            stack.enter_context(patch.object(module,name,memo))
        yield


def aggregate(rows):
    result={}
    for turns in range(3,9):
        runs=[run for row in rows for run in row.get('conversations',[]) if run['turns']==turns]
        sizes=[request['wire_bytes'] for run in runs for request in run['requests']]
        result[str(turns)]={'valid_conversations':len(runs),'serialized_requests':len(sizes),
            'wire_bytes':{'minimum':min(sizes),'median':float(np.median(sizes)),'p95':float(np.quantile(sizes,.95)),'maximum':max(sizes)} if sizes else None,
            'profiles':{name:{'complete':sum(run['profiles'][name]['all_fit'] for run in runs),
                 'admitted_histogram':{str(n):sum(run['profiles'][name]['admitted_calls']==n for run in runs) for n in range(9)}} for name in PROFILES}}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('development','raw-root','index','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();cases=read_development(args.development)
    checkpoint=os.environ.get('DESI_FM_CKPT')
    if not checkpoint or not Path(checkpoint).is_file():raise ValueError('Verified explicit local checkpoint required; no downloads')
    root=Path(__file__).resolve().parents[1]
    old=json.loads((root/'docs/evidence/batch5b2-candidate.json').read_text())
    for name,path in [('predictor_checkpoint',Path(checkpoint)),('faiss_index',Path(os.environ.get('DESI_FM_INDEX_DIR',tools.DATA_DIR))/'spectra.faiss'),
                      ('index_metadata',Path(os.environ.get('DESI_FM_INDEX_DIR',tools.DATA_DIR))/'spectra_meta.npz')]:
        expected=old['behavior']['assets'][name]
        if sha256(path)!=expected['sha256'] or path.stat().st_size!=expected['bytes']:raise ValueError('Local asset identity changed')
    args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    inputs=materialize(cases,args.output/'inputs',args.raw_root,args.index)
    network_attempts=[]
    def forbidden(*a,**k):network_attempts.append(True);raise AssertionError('Offline budget probe forbids network')
    socket.create_connection=socket.getaddrinfo=forbidden;socket.socket.connect=forbidden
    torch.manual_seed(20261019)
    rows=[]
    for position,(case,path,_,_) in enumerate(inputs):
        row={'case_id':case['case_id'],'kind':case['kind'],'family':case.get('family','real'),'status':'pending','conversations':[]}
        try:
            with agent.agent_input(str(path)) as (opaque,_),cached_measurements():
                for turns in range(3,9):row['conversations'].append(probe(opaque,turns,args.output/'requests'/f'case-{position:03d}-turns-{turns}'))
            row['status']='measured'
        except SpectrumInputError:row['status']='invalid_input'
        rows.append(row);write_json(args.output/'rows.json',rows)
    assert not network_attempts
    summary={'scope':'Offline scripted request-size measurement, not real LLM acceptance or billing',
        'requested':len(rows),'status_counts':{s:sum(r['status']==s for r in rows) for s in ('measured','invalid_input','pending')},
        'real_measured':sum(r['kind']=='real' and r['status']=='measured' for r in rows),
        'synthetic_measured':sum(r['kind']=='synthetic' and r['status']=='measured' for r in rows),
        'by_turns':aggregate(rows),'network_attempts':0,'remote_calls':0,'real_paid_usd':0,
        'historical_limits':vars(HISTORICAL_LIMITS),'model':PINNED_MODEL,
        'cost_maximum_from_registered_rates':{'per_case':(64000+4096*5)/1e6,'all_128':128*(64000+4096*5)/1e6},
        'identity':{'head':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),
                    'harness_sha256':sha256(__file__),'development_sha256':sha256(args.development),'corpus_revision':rag.corpus_revision()},
        'limits':['Serialized requests beyond the production stop are offline counterfactual probes only.',
                  '3..6 turns add lines, reference, neighbors, alternate lines, reconstruction and then submit; initial predict counts as one of six analysis tools.',
                  '7..8 turns add one/two rejected schema calls before the six-turn sequence; they illustrate argument repair, not retries of network requests.',
                  'Real tool payloads cached within each case across scenarios; masking draw seed 20261019; no training or test data.',
                  'No actual tokenizer usage exists: full-bound replay is conservative; 2/4 bytes per token plus 496 overhead are illustrative, not provider guarantees.',
                  'All replays use unchanged 64000 input /4096 output /512 per call /8 calls /zero retries and monetary ceilings.',
                  'Prices inherited from the registered 5B-2 candidate ($1/M input, $5/M output); reconfirm model and rates when Julian authorizes 5C.']}
    write_json(args.output/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ('requested','status_counts','real_measured','synthetic_measured','network_attempts','remote_calls','real_paid_usd')}))


if __name__=='__main__':main()
