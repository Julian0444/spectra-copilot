"""Deterministic blinded review packets from sealed outputs only; never labels."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from copilot import explanation
from copilot.acceptance_io import sha256
from copilot.acceptance_score import validate_seal
from copilot.campaign import exclusive_json

FIELDS=('status','model_z','predictor','input_contract','alternatives','explanation','citations','limitations','policy_violations')
IDENTITY_WORDS=re.compile(r'\b(claude|haiku|opus|sonnet|fable|anthropic|gpt|openai|codex|astra)\b|\b(msg_|toolu_|req_)',re.I)
CHUNK_BYTES=200000


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def case_packet(row,seal_hash):
    review_id=hashlib.sha256(('batch5c-review-v1\0'+seal_hash+'\0'+row['alias']).encode()).hexdigest()[:16]
    source=row.get('result')
    packet={'schema':'batch5c-ai-packet-v1','review_id':review_id,'published_report':source is not None,
            'report':None,'observations':[],'prediction':None,'rendered_report':None,'claims':[],
            'blindness_intact':True,'identity_exposures':[]}
    if source is None:return packet
    packet.update(report={k:deepcopy(source[k]) for k in FIELDS if k in source},
                  observations=deepcopy(source.get('observations',[])),prediction=deepcopy(source.get('prediction')),
                  rendered_report=explanation.render(source),
                  selection_provenance='llm_selected' if row['status'] in {'complete','ambiguous','insufficient_data'} and not source.get('policy_violations') else 'executor_fallback')
    groups={}
    def add(key,text,pointer,refs=()):
        # Equivalence is explicit for template facts, never a text similarity score.
        duplicate=next((k for k,v in groups.items() if v['text']==text and v['reference_ids']==list(refs)),None)
        if duplicate is not None:key=duplicate
        if key not in groups:groups[key]={'id':review_id+':'+key,'equivalence_key':key,'text':text,
            'reference_ids':list(refs),'occurrences':[]}
        groups[key]['occurrences'].append({'pointer':pointer,'text':text})
    add('status','Status: '+source['status'],'/report/status')
    add('official_model_z','Official model_z: '+('unavailable' if source['model_z'] is None else repr(source['model_z'])),'/report/model_z')
    add('predictor','Predictor: '+str(source['predictor']),'/report/predictor')
    add('input_contract','Input contract: '+str(source['input_contract']),'/report/input_contract')
    for i,text in enumerate(source.get('limitations',[])):add('lim:'+str(i+1),text,f'/report/limitations/{i}')
    by_id={o['id']:o for o in source.get('observations',[])}
    for i,item in enumerate(source.get('explanation',[])):
        obs=by_id[item['observation_id']];tool=obs['tool'];text=item['text'];pointer=f'/report/explanation/{i}/text'
        if obs.get('error'):add(obs['id']+':error',text,pointer);continue
        if tool=='predict_redshift':
            value,_,tail=text.partition(' Posterior concentration is ')
            add('official_model_z',value,pointer)
            if tail:
                amount,sep,qualifier=tail.partition('; ')
                add('posterior_concentration','Posterior concentration is '+amount,pointer)
                if sep:add('lim:1',qualifier,pointer)
        elif tool=='reconstruct_spectrum':
            value,_,qualifier=text.partition('; ');add(obs['id']+':value',value,pointer)
            if qualifier:add('lim:2',qualifier,pointer)
        elif tool=='find_similar_spectra':
            value,_,tail=text.partition(' The shared encoder ');add(obs['id']+':value',value,pointer)
            if tail:
                qualifier,_,compatibility=tail.partition('; ')
                add('lim:3','The shared encoder '+qualifier,pointer)
                if compatibility:add('index_compatibility',compatibility,pointer)
        elif tool=='identify_spectral_lines':
            value,_,qualifier=text.partition(' These are ');add(obs['id']+':value',value,pointer)
            # Not physical confirmation and absence not refutation are different
            # propositions; retain both instead of merging by topical similarity.
            if qualifier:add('matcher_not_confirmation','These are '+qualifier,pointer)
        elif tool=='lookup_reference':
            value,_,qualifier=text.partition(' Existence alone ');add(obs['id']+':value',value,pointer)
            if qualifier:add('existence_not_support','Existence alone '+qualifier,pointer)
    for i,item in enumerate(source.get('alternatives',[])):
        add('alternative:'+str(i),canonical(item).decode(),f'/report/alternatives/{i}')
    for i,item in enumerate(source.get('citations',[])):
        # A quotation is preserved and independently classified, not promoted to
        # a claim about the spectrum and not paired with unrelated observations.
        add('quotation:'+item['id'],item['text'],f'/report/citations/{i}/text')
    if source.get('citations'):
        add('citation_not_certification','This excerpt is not independent certification of this spectrum or its prediction.','/rendered_report')
    if source.get('policy_violations'):add('withheld','Unvalidated or incompatible generated content was withheld: '+', '.join(source['policy_violations']),'/report/policy_violations')
    packet['claims']=list(groups.values())
    def inspect(value,pointer=''):
        if isinstance(value,dict):
            for k,v in value.items():inspect(v,pointer+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):inspect(v,pointer+'/'+str(i))
        elif isinstance(value,str) and (IDENTITY_WORDS.search(value) or value==row['alias'] or '/Users/' in value):
            packet['identity_exposures'].append(pointer)
    for key in ('report','observations','prediction','rendered_report'):inspect(packet[key],'/'+key)
    packet['blindness_intact']=not packet['identity_exposures']
    return packet


def prepare(run,output,private_map,instructions):
    rows,_,_,seal_hash,_=validate_seal(run)
    output,private_map=Path(output),Path(private_map)
    if private_map.resolve().is_relative_to(output.resolve()):raise ValueError('Alias map must be outside annotator packages')
    if output.exists() or private_map.exists():raise FileExistsError('Preserve earlier review package')
    packets=sorted((case_packet(r,seal_hash) for r in rows),key=lambda x:x['review_id'])
    output.mkdir(mode=0o700,parents=True)
    mapping={case_packet(r,seal_hash)['review_id']:r['alias'] for r in rows}
    if len(mapping)!=len(rows):raise ValueError('Review ID collision')
    exclusive_json(private_map,{'seal_sha256':seal_hash,'map':mapping})
    (output/'INSTRUCTIONS.md').write_bytes(Path(instructions).read_bytes())
    chunks=[];current=[];size=0
    for packet in packets:
        n=len(canonical(packet))
        if current and size+n>CHUNK_BYTES:chunks.append(current);current=[];size=0
        current.append(packet);size+=n
    if current:chunks.append(current)
    files={}
    for i,chunk in enumerate(chunks):
        name=f'chunk-{i:03d}.json';exclusive_json(output/name,{'schema':'batch5c-ai-chunk-v1','cases':chunk});files[name]=sha256(output/name)
    files['INSTRUCTIONS.md']=sha256(output/'INSTRUCTIONS.md')
    manifest={'schema':'batch5c-ai-packet-manifest-v1','requested':len(rows),'files':files,
        'identity_exposed_cases':sum(not p['blindness_intact'] for p in packets),
        'seed_claims':sum(len(p['claims']) for p in packets),'chunk_bytes_target':CHUNK_BYTES,
        'claim_definitions_sha256':sha256(__file__),'labels_read':False}
    exclusive_json(output/'manifest.json',manifest)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','output','private-map','instructions'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.run,a.output,a.private_map,a.instructions)))


if __name__=='__main__':main()
