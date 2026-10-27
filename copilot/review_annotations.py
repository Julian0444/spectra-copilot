"""Validate and join independently registered annotations without reading labels."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from copilot.acceptance_io import sha256
from copilot.campaign import exclusive_json
from copilot.review import OBLIGATIONS,JUDGMENTS


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def added_id(review_id,text):return review_id+':added:'+hashlib.sha256(text.encode()).hexdigest()


def inventory_digest(claims,first,second):
    return digest({'seed':claims,'annotations':[{k:(b or {}).get(k) for k in
        ('inventory_complete','inventory_disputes','added_claims')} for b in (first,second)]})


def disputed_ids(first,second=None):
    return {key for bundle in (first,second) for dispute in (bundle or {}).get('inventory_disputes',[])
            for key in dispute['claim_ids']}


def validate_inventory_resolution(claims,first,second,resolution):
    """An inventory adjudication may change only registered disputes/additions."""
    if first is None and second is None:
        raise ValueError('Original annotation context required for inventory resolution')
    disputes=disputed_ids(first,second)
    additions={c['id']:c for b in (first,second) for c in (b or {}).get('added_claims',[])}
    has_disputes=any((b or {}).get('inventory_disputes') for b in (first,second))
    if not has_disputes and not additions:
        raise ValueError('No registered inventory dispute or addition to resolve')
    if (not isinstance(resolution,dict) or resolution.get('input_sha256')!=inventory_digest(claims,first,second)
        or not isinstance(resolution.get('reason'),str) or not resolution['reason'].strip()
        or not isinstance(resolution.get('claims'),list)):
        raise ValueError('Invalid or stale inventory resolution')
    final=resolution['claims']
    if any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id']
           or not isinstance(c.get('text'),str) or not c['text'].strip() for c in final):
        raise ValueError('Distinct nonempty final inventory claims required')
    by_id={c['id']:c for c in final}
    if len(by_id)!=len(final):raise ValueError('Distinct final inventory required')
    for c in claims:
        if c['id'] not in disputes and (c['id'] not in by_id or by_id[c['id']]['text']!=c['text']):
            raise ValueError('Undisputed inventory claim must retain its ID and text')
    original={c['id']:c for c in claims};original.update(additions)
    return {'excluded':sorted(set(original)-set(by_id)),
            'changed':sorted(k for k in set(original)&set(by_id) if original[k]['text']!=by_id[k]['text']),
            'added':sorted(set(by_id)-set(original))}


def validate_claim_references(claim,judgment,*,disputed=False,emitted=None):
    refs=judgment['reference_ids']
    if emitted is not None and set(refs)-emitted:
        raise ValueError('Reference IDs must be emitted citations of this case')
    if not disputed and set(refs)!=set(claim.get('reference_ids',[])):
        raise ValueError('Reference pairs must match the seed unless inventory is disputed')
    quotation=claim.get('equivalence_key','').startswith('quotation:') or ':quotation:' in claim['id']
    if quotation and not disputed and (refs or judgment['scientific'] or judgment['external_scientific']
            or not judgment['factual'] or judgment['scientific_accuracy']!='not_applicable'):
        raise ValueError('Quotation is factual extraction fidelity, not an external scientific assertion or reference pair')


def validate_case(case,packet,*,adjudication=False,first=None,second=None):
    """Raise ValueError for malformed annotation fields before hash registration."""
    if not isinstance(case,dict) or not isinstance(case.get('reviewer'),str) or not case['reviewer'] or case.get('independent') is not True:
        raise ValueError('An independent named reviewer is required')
    obligations=case.get('case_obligations')
    if (not isinstance(obligations,dict) or (set(obligations)-set(OBLIGATIONS)) or
        (not adjudication and set(obligations)!=set(OBLIGATIONS)) or
        any(not isinstance(v,str) or v not in {'met','unmet','not_applicable'} for v in obligations.values())):
        raise ValueError('case_obligations must map obligation names to enum strings; put notes in obligation_notes')
    claims={c['id']:c for c in packet['claims']}
    if adjudication:
        for bundle in (first,second):
            for c in (bundle or {}).get('added_claims',[]):
                if c['id'] in claims and claims[c['id']]['text']!=c['text']:raise ValueError('Conflicting claim identity')
                claims[c['id']]=c
    additions=case.get('added_claims',[])
    if not isinstance(additions,list):raise ValueError('added_claims must be a list')
    seen=set()
    for c in additions:
        if (not isinstance(c,dict) or not isinstance(c.get('text'),str) or not c['text'].strip()
            or c.get('id')!=added_id(packet['review_id'],c['text']) or c['text'] in seen
            or c['id'] in claims or not isinstance(c.get('occurrences'),list)):
            raise ValueError('Invalid or duplicate added claim; use exact text and its derived ID')
        seen.add(c['text']);claims[c['id']]=c
    if not adjudication:
        if type(case.get('inventory_complete')) is not bool or type(case.get('identity_incident')) is not bool:
            raise ValueError('Explicit inventory_complete and identity_incident booleans required')
        disputes=case.get('inventory_disputes')
        if not isinstance(disputes,list):raise ValueError('inventory_disputes must be a list')
        if disputes and case['inventory_complete']:raise ValueError('A disputed inventory cannot be marked complete')
        for d in disputes:
            if (not isinstance(d,dict) or d.get('kind') not in {'split','merge','exclude','add'}
                or not isinstance(d.get('claim_ids'),list) or set(d['claim_ids'])-set(claims)
                or not isinstance(d.get('spans'),list) or not isinstance(d.get('proposed_texts'),list)
                or not isinstance(d.get('reason'),str) or not d['reason'].strip()):
                raise ValueError('Invalid structured inventory dispute')
    resolution=case.get('inventory_resolution')
    if resolution is not None:
        if not adjudication:
            raise ValueError('Invalid inventory resolution')
        validate_inventory_resolution(packet['claims'],first,second,resolution)
        claims={c['id']:c for c in resolution['claims']}
        if len(claims)!=len(resolution['claims']) or any(not isinstance(c.get('text'),str) or not c['text'].strip() for c in claims.values()):
            raise ValueError('Distinct nonempty final inventory claims required')
    judgments=case.get('judgments')
    if not isinstance(judgments,dict) or set(judgments)-set(claims):raise ValueError('Unknown claim judgment')
    if not adjudication and case['inventory_complete'] and set(judgments)!=set(claims):
        raise ValueError('Complete inventories require every claim judgment')
    observation_ids={o['id'] for o in packet['observations']}
    disputed=disputed_ids(first,second) if adjudication else disputed_ids(case)
    emitted={c['id'] for c in (packet.get('report') or {}).get('citations',[])}
    for key,j in judgments.items():
        if not isinstance(j,dict) or any(type(j.get(k)) is not bool for k in ('factual','scientific','external_scientific','critical_error')):
            raise ValueError('Each judgment needs explicit classification booleans')
        if j['external_scientific'] and not (j['scientific'] and j['factual']):raise ValueError('External science must be scientific and factual')
        if any(not isinstance(j.get(k),str) or j[k] not in values for k,values in JUDGMENTS.items()):raise ValueError('Invalid categorical judgment')
        if j['scientific'] and j['scientific_accuracy']=='not_applicable':raise ValueError('Science needs a scientific judgment')
        if j['factual'] and j['textual_support']=='not_applicable':raise ValueError('Facts need an evidence judgment')
        refs=j.get('reference_ids');obs=j.get('observation_ids')
        if not isinstance(refs,list) or any(not isinstance(v,str) for v in refs) or len(refs)!=len(set(refs)):
            raise ValueError('Distinct reference_ids strings required')
        if not isinstance(obs,list) or any(not isinstance(v,str) for v in obs) or len(obs)!=len(set(obs)) or set(obs)-observation_ids:
            raise ValueError('observation_ids must identify supplied observations')
        support=j.get('reference_support')
        if not isinstance(support,dict) or set(support)!=set(refs) or any(v not in {'supported','unsupported'} for v in support.values()):
            raise ValueError('Every emitted reference pair needs a judgment')
        validate_claim_references(claims[key],j,disputed=key in disputed,emitted=emitted)
    return case


def read_package(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('schema')!='batch5c-ai-packet-manifest-v1':raise ValueError('Invalid packet manifest schema')
    cases={}
    for name,expected in manifest['files'].items():
        path=(directory/name).resolve()
        if not path.is_relative_to(directory.resolve()) or sha256(path)!=expected:raise ValueError('Packet hash or location mismatch')
        if name.startswith('chunk-'):
            for case in json.loads(path.read_text())['cases']:
                if case['review_id'] in cases:raise ValueError('Duplicate review ID')
                cases[case['review_id']]=case
    if len(cases)!=manifest['requested']:raise ValueError('Packet case count differs')
    return manifest,cases


def validate_annotation(path,package,*,adjudication=False,first=None,second=None):
    _,packets=read_package(package);value=json.loads(Path(path).read_text())
    expected='batch5c-ai-adjudication-v1' if adjudication else 'batch5c-ai-annotation-v1'
    if value.get('schema')!=expected or value.get('independent') is not True or not value.get('reviewer'):
        raise ValueError('Invalid annotation schema or reviewer')
    if value.get('package_manifest_sha256')!=sha256(Path(package)/'manifest.json'):raise ValueError('Annotation refers to another packet')
    cases=value.get('cases')
    if not isinstance(cases,dict) or set(cases)-set(packets) or (not adjudication and set(cases)!=set(packets)):
        raise ValueError('Annotation must cover every requested case')
    for key,case in cases.items():
        if case.get('reviewer')!=value['reviewer']:raise ValueError('Reviewer identity differs inside annotation')
        validate_case(case,packets[key],adjudication=adjudication,
            first=(first or {}).get('cases',{}).get(key),second=(second or {}).get('cases',{}).get(key))
    return value


def registered_annotations(package,first,second,registration):
    registered=json.loads(Path(registration).read_text())
    hashes={'first_sha256':sha256(first),'second_sha256':sha256(second)}
    if (registered.get('schema')!='batch5c-annotation-registration-v1' or
        registered.get('registered_before_reading_judgments') is not True or
        any(registered.get(k)!=v for k,v in hashes.items())):
        raise ValueError('Both independent annotations must be registered first')
    a=validate_annotation(first,package);b=validate_annotation(second,package)
    if a['reviewer']==b['reviewer']:raise ValueError('Independent distinct sessions required')
    return a,b,hashes


def dispute_worksheet(package,first,second,registration,output):
    """Prepare all adjudication context without opening labels or private aliases."""
    if Path(output).resolve().is_relative_to(Path(package).resolve()):
        raise ValueError('Worksheet must be outside blinded package')
    a,b,hashes=registered_annotations(package,first,second,registration)
    _,packets=read_package(package)
    from copilot.review import score_annotation_pair
    cases={}
    for key,packet in packets.items():
        ca,cb=deepcopy(a['cases'][key]),deepcopy(b['cases'][key])
        for c in (ca,cb):c['identity_incident'] |= exposed_notes(c)
        score=score_annotation_pair(packet['claims'],ca,cb,blindness_intact=packet['blindness_intact'])
        cases[key]={'input_sha256':inventory_digest(packet['claims'],ca,cb),
                    'claims':packet['claims'],'first':ca,'second':cb,
                    'disagreements':score['disagreements'],'forced':score['forced'],
                    'obligation_disagreements':score['obligation_disagreements'],
                    'inventory_pending':score['inventory_pending'],
                    'pending_claims':[r['claim_id'] for r in score['rows'] if r['judgment'] is None],
                    'pending_obligations':[k for k,v in score['case_obligations'].items() if v is None]}
    result={'schema':'batch5c-adjudication-worksheet-v1','labels_read':False,
            'package_manifest_sha256':sha256(Path(package)/'manifest.json'),
            **hashes,'registration_sha256':sha256(registration),'cases':cases}
    exclusive_json(output,result);return result


def exposed_notes(value,in_notes=False):
    from copilot.review_packet import IDENTITY_WORDS
    if isinstance(value,dict):return any(exposed_notes(v,in_notes or k in {'notes','identity_note','obligation_notes'}) for k,v in value.items() if k!='reviewer')
    if isinstance(value,list):return any(exposed_notes(v,in_notes) for v in value)
    return in_notes and isinstance(value,str) and bool(IDENTITY_WORDS.search(value))


def join_annotations(package,mapping,first,second,registration,output,adjudication=None):
    """Deterministic alias join; registration is written before either judgment is read."""
    output=Path(output)
    if output.exists():raise FileExistsError('Preserve previous review join')
    if output.resolve().is_relative_to(Path(package).resolve()):raise ValueError('Review join must be outside blinded package')
    a,b,hashes=registered_annotations(package,first,second,registration)
    manifest,packets=read_package(package);private=json.loads(Path(mapping).read_text())
    if private['seal_sha256']!=manifest['seal_sha256'] or set(private['map'])!=set(packets) or len(set(private['map'].values()))!=len(packets):
        raise ValueError('Private alias map differs from sealed package')
    j=validate_annotation(adjudication,package,adjudication=True,first=a,second=b) if adjudication else None
    if len({x['reviewer'] for x in (a,b,j) if x})!=(3 if j else 2):raise ValueError('Independent distinct sessions required')
    cases={}
    for key,packet in packets.items():
        first_case=deepcopy(a['cases'][key]);second_case=deepcopy(b['cases'][key])
        for case in (first_case,second_case):case['identity_incident'] |= exposed_notes(case)
        cases[private['map'][key]]={'schema':'batch5c-ai-case-review-v1','review_id':key,
            'claims':packet['claims'],'blindness_intact':packet['blindness_intact'],
            'first':first_case,'second':second_case,'adjudication':j['cases'].get(key) if j else None}
    result={'schema':'batch5c-ai-reviews-v1','seal_sha256':manifest['seal_sha256'],
        'outputs_sha256':manifest['outputs_sha256'],'package_manifest_sha256':sha256(Path(package)/'manifest.json'),
        **hashes,'registration_sha256':sha256(registration),'map_sha256':sha256(mapping),
        'adjudication_sha256':sha256(adjudication) if adjudication else None,'cases':cases}
    exclusive_json(output,result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['validate','join','worksheet'])
    parser.add_argument('--package',type=Path,required=True)
    for name in ('annotation','mapping','first','second','registration','output','adjudication'):
        parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    if args.action=='validate':
        if bool(args.annotation)==bool(args.adjudication):parser.error('Supply exactly one of --annotation or --adjudication')
        if args.adjudication:
            if any(getattr(args,n) is None for n in ('first','second','registration')):parser.error('Adjudication requires registered --first and --second')
            a,b,_=registered_annotations(args.package,args.first,args.second,args.registration)
            result=validate_annotation(args.adjudication,args.package,adjudication=True,first=a,second=b)
            if result['reviewer'] in {a['reviewer'],b['reviewer']}:raise ValueError('Independent distinct sessions required')
        else:result=validate_annotation(args.annotation,args.package)
        print(json.dumps({'valid':True,'cases':len(result['cases']),'sha256':sha256(args.annotation or args.adjudication)}))
    elif args.action=='worksheet':
        if any(getattr(args,n) is None for n in ('first','second','registration','output')):parser.error('Worksheet requires registered annotation paths and --output')
        result=dispute_worksheet(args.package,args.first,args.second,args.registration,args.output)
        print(json.dumps({'cases':len(result['cases']),'sha256':sha256(args.output)}))
    else:
        if any(getattr(args,n) is None for n in ('mapping','first','second','registration','output')):parser.error('All join paths are required')
        result=join_annotations(args.package,args.mapping,args.first,args.second,args.registration,args.output,args.adjudication)
        print(json.dumps({'cases':len(result['cases']),'sha256':sha256(args.output)}))


if __name__=='__main__':main()
