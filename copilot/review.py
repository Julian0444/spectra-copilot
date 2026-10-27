"""Mechanical citation checks plus explicit human semantic-review accounting.

No regex, overlap score or model grades semantic support. Independent reviewers
supply atomic claims and judgments; disagreement needs a third adjudicator.
"""
from copilot import rag

OBLIGATIONS=('report','model_z','caution','evidence','citations','limitations')

JUDGMENTS = {'textual_support': {'supported', 'unsupported', 'not_applicable'},
             'scientific_accuracy': {'correct', 'incorrect', 'not_applicable'}}


def score_claim_review(claims, first=None, second=None, adjudication=None):
    """Count all claims, including pending/disputed ones; never reward silence.

    A claim has id, text, reference_ids, external_scientific and factual fields.
    Review bundles have reviewer, independent=True, and judgments keyed by claim
    id. Adjudication has the same schema and covers every disputed claim.
    """
    ids = [c['id'] for c in claims]
    if len(set(ids)) != len(ids) or any(not c['text'].strip() for c in claims):
        raise ValueError('Distinct nonempty atomic claims required')
    if any(len(set(c.get('reference_ids', []))) != len(c.get('reference_ids', [])) for c in claims):
        raise ValueError('Do not duplicate citation mentions within an atomic claim')
    by_id = {c['id']: c for c in claims}
    bundles = [x for x in (first, second, adjudication) if x is not None]
    reviewers = [x['reviewer'] for x in bundles]
    if len(set(reviewers)) != len(reviewers) or any(not x['reviewer'] or x.get('independent') is not True for x in bundles):
        raise ValueError('Distinct independent reviewers required')
    for bundle in bundles:
        if set(bundle['judgments']) - set(ids):
            raise ValueError('Unknown claim judgment')
        for claim_id, j in bundle['judgments'].items():
            if any(j.get(k) not in allowed for k, allowed in JUDGMENTS.items()) or type(j.get('critical_error')) is not bool:
                raise ValueError('Incomplete semantic judgment')
            claim = by_id[claim_id]
            pair_support = j.get('reference_support', {})
            if (set(pair_support) != set(claim.get('reference_ids', [])) or
                    any(v not in {'supported','unsupported'} for v in pair_support.values())):
                raise ValueError('Judge each claim-reference pair separately')
            if claim.get('external_scientific') and (j['textual_support']=='not_applicable' or j['scientific_accuracy']=='not_applicable'):
                raise ValueError('External scientific assertions require semantic review')
    result = {'claims': len(claims), 'citation_mentions': 0, 'valid_citation_mentions': 0,
              'textual_pairs': sum(len(c.get('reference_ids', [])) for c in claims), 'textual_supported': 0,
              'scientific_claims': sum(c.get('scientific', c.get('external_scientific', False)) for c in claims),
              'scientific_correct': 0, 'factual_claims': sum(c.get('factual', True) for c in claims),
              'unsupported_claims': 0, 'missing_required_citations': 0,
              'critical_errors': 0, 'pending_claims': 0, 'disagreements': [], 'rows': []}
    valid = rag.valid_ids()
    for c in claims:
        refs = c.get('reference_ids', [])
        valid_n = sum(r in valid for r in refs)
        result['citation_mentions'] += len(refs)
        result['valid_citation_mentions'] += valid_n
        missing = bool(c.get('external_scientific') and not refs)
        result['missing_required_citations'] += missing
        a = first['judgments'].get(c['id']) if first else None
        b = second['judgments'].get(c['id']) if second else None
        agreed = a if a is not None and a == b else None
        if a is not None and b is not None and a != b:
            result['disagreements'].append(c['id'])
            agreed = adjudication['judgments'].get(c['id']) if adjudication else None
        row = {'claim_id': c['id'], 'id_valid': len(refs) == valid_n,
               'missing_required_citation': missing, 'judgment': agreed}
        if agreed is None:
            result['pending_claims'] += 1
        else:
            support = agreed['textual_support']
            science = agreed['scientific_accuracy']
            # IDs and quotation checks cannot supply these semantic judgments.
            result['textual_supported'] += sum(v=='supported' and ref in valid
                for ref,v in agreed['reference_support'].items())
            result['scientific_correct'] += science == 'correct' and c.get('scientific', c.get('external_scientific', False))
            result['unsupported_claims'] += support == 'unsupported' or missing or valid_n!=len(refs)
            result['critical_errors'] += agreed['critical_error']
        result['rows'].append(row)
    invalid = result['citation_mentions'] - result['valid_citation_mentions']
    result['evaluation_failures'] = {'invalid_citation_ids': invalid,
        'unsupported_claims': result['unsupported_claims'], 'missing_required_citations': result['missing_required_citations'],
        'critical_scientific_errors': result['critical_errors']}
    result['semantic_status'] = 'pending_independent_review' if not claims or result['pending_claims'] else 'reviewed'
    result['rates'] = {}
    for name, numerator, denominator in [('id_validity','valid_citation_mentions','citation_mentions'),
                ('textual_support','textual_supported','textual_pairs'),
                ('scientific_accuracy','scientific_correct','scientific_claims'),
                ('unsupported_claims','unsupported_claims','factual_claims')]:
        n,d = result[numerator], result[denominator]
        result['rates'][name] = {'numerator':n, 'denominator':d,
                                'rate': n/d if d and (name=='id_validity' or not result['pending_claims']) else None}
    return result


def score_annotation_pair(claims,first=None,second=None,adjudication=None,*,blindness_intact=True):
    """5C AI annotations: inventory/classification and omissions are also reviewed.

    Preparatory flags never determine denominators. Disputed classifications use
    their union for provisional counts only; all affected rates remain pending.
    A third adjudicator can resolve disputes, preserving original annotations.
    """
    from copy import deepcopy
    ids=[c['id'] for c in claims]
    if len(set(ids))!=len(ids) or any(not c['text'].strip() for c in claims):raise ValueError('Distinct nonempty claims required')
    bundles=[x for x in (first,second,adjudication) if x is not None]
    reviewers=[x['reviewer'] for x in bundles]
    if len(set(reviewers))!=len(reviewers) or any(not x['reviewer'] or x.get('independent') is not True for x in bundles):
        raise ValueError('Distinct annotation sessions required')
    catalog={c['id']:deepcopy(c) for c in claims};additions=[]
    for bundle in bundles:
        added={c['id']:c for c in bundle.get('added_claims',[])}
        if len(added)!=len(bundle.get('added_claims',[])):raise ValueError('Duplicate proposed claim')
        additions.append(added)
        for key,c in added.items():
            if not c['text'].strip() or key in ids:raise ValueError('Invalid added claim')
            if key in catalog and catalog[key]['text']!=c['text']:raise ValueError('Conflicting claim identity')
            catalog[key]=deepcopy(c)
    original_catalog=deepcopy(catalog)
    resolution=(adjudication or {}).get('inventory_resolution')
    resolved=resolution is not None
    inventory_changes={'excluded':[],'changed':[],'added':[]}
    if resolved:
        from copilot.review_annotations import validate_inventory_resolution
        inventory_changes=validate_inventory_resolution(claims,first,second,resolution)
        final=resolution['claims'];catalog={c['id']:deepcopy(c) for c in final}
        if len(catalog)!=len(final) or any(not c['text'].strip() for c in final):raise ValueError('Distinct final inventory required')
    forced=not blindness_intact or any((b or {}).get('identity_incident',False) for b in (first,second))
    categorical=(*JUDGMENTS,'critical_error','reference_support','factual','scientific','external_scientific','reference_ids')
    def judgment(bundle,key):
        if not bundle or key not in bundle['judgments']:return None
        j=bundle['judgments'][key]
        if any(type(j.get(k)) is not bool for k in ('factual','scientific','external_scientific','critical_error')):
            raise ValueError('Each annotator must classify every claim')
        if any(j.get(k) not in allowed for k,allowed in JUDGMENTS.items()):raise ValueError('Incomplete judgment')
        refs=j.get('reference_ids')
        if not isinstance(refs,list) or len(set(refs))!=len(refs):raise ValueError('Distinct reference IDs required')
        if set(j.get('reference_support',{}))!=set(refs) or any(x not in {'supported','unsupported'} for x in j['reference_support'].values()):
            raise ValueError('Judge every reference pair')
        if j['scientific'] and j['scientific_accuracy']=='not_applicable':raise ValueError('Scientific assertion needs scientific judgment')
        if j['factual'] and j['textual_support']=='not_applicable':raise ValueError('Factual assertion needs evidence judgment')
        if j['external_scientific'] and not (j['scientific'] and j['factual']):raise ValueError('External science must be scientific and factual')
        value={k:deepcopy(j[k]) for k in categorical}
        value['reference_ids']=sorted(refs)
        value['observation_ids']=sorted(j.get('observation_ids',[]))
        return value
    for bundle in bundles:
        allowed=set(catalog) if bundle is adjudication else set(original_catalog)
        if set(bundle['judgments'])-allowed:raise ValueError('Unknown claim')
        obligations=bundle.get('case_obligations',{})
        if (not isinstance(obligations,dict) or set(obligations)-set(OBLIGATIONS)
            or (bundle is not adjudication and set(obligations)!=set(OBLIGATIONS))
            or any(not isinstance(v,str) or v not in {'met','unmet','not_applicable'} for v in obligations.values())):
            raise ValueError('All case obligations require explicit annotation')
        for key in bundle['judgments']:judgment(bundle,key)
    initial_disagreements=[]
    for key in original_catalog:
        a,b=judgment(first,key),judgment(second,key)
        one_added=key not in ids and not all(key in x for x in additions[:2])
        if (a is not None and b is not None and a!=b) or one_added:initial_disagreements.append(key)
    result={'claims':len(catalog),'citation_mentions':0,'valid_citation_mentions':0,'textual_pairs':0,'textual_supported':0,
            'scientific_claims':0,'scientific_correct':0,'factual_claims':0,'unsupported_claims':0,
            'missing_required_citations':0,'critical_errors':0,'pending_claims':0,
            'disagreements':initial_disagreements,'forced':[],'changed':[],
            'inventory_changes':inventory_changes,'rows':[]}
    inventory_pending=not (first and second) or (not resolved and not
        (first.get('inventory_complete') is True and second.get('inventory_complete') is True
         and not first.get('inventory_disputes') and not second.get('inventory_disputes')))
    valid=rag.valid_ids()
    for key,c in catalog.items():
        a,b=judgment(first,key),judgment(second,key)
        added=key not in ids
        existence_agreed=not added or (first and second and any(x['id']==key for x in first.get('added_claims',[])) and any(x['id']==key for x in second.get('added_claims',[])))
        changed=resolved and (key not in original_catalog or c['text']!=original_catalog[key]['text'])
        agreed=a if a is not None and a==b and existence_agreed and not forced and not changed else None
        disputed=(a is not None and b is not None and a!=b) or (added and not existence_agreed)
        if forced:result['forced'].append(key)
        if changed:result['changed'].append(key)
        if disputed or forced or changed or (resolved and agreed is None):
            agreed=judgment(adjudication,key)
        # Provisional inclusive counts are explicitly pending, never a pass.
        flags=agreed or {k:any((j or {}).get(k,False) for j in (a,b)) for k in ('scientific','factual','external_scientific')}
        refs=agreed['reference_ids'] if agreed else sorted(set((a or {}).get('reference_ids',[]))|set((b or {}).get('reference_ids',[])))
        n_valid=sum(r in valid for r in refs);missing=flags['external_scientific'] and not refs
        result['citation_mentions']+=len(refs);result['valid_citation_mentions']+=n_valid;result['textual_pairs']+=len(refs)
        result['scientific_claims']+=flags['scientific'];result['factual_claims']+=flags['factual']
        result['missing_required_citations']+=bool(missing)
        if agreed is None:result['pending_claims']+=1
        else:
            result['textual_supported']+=sum(v=='supported' and r in valid for r,v in agreed['reference_support'].items())
            result['scientific_correct']+=flags['scientific'] and agreed['scientific_accuracy']=='correct'
            result['unsupported_claims']+=flags['factual'] and (agreed['textual_support']=='unsupported' or missing or n_valid!=len(refs))
            result['critical_errors']+=agreed['critical_error']
        result['rows'].append({'claim_id':key,'text':c['text'],'classification':flags,'judgment':agreed,'added':added})
    obligations={};disputes=[]
    for key in OBLIGATIONS:
        a=first['case_obligations'].get(key) if first else None;b=second['case_obligations'].get(key) if second else None
        value=a if a is not None and a==b and not forced else None
        if a is not None and b is not None and a!=b:
            disputes.append(key);value=adjudication.get('case_obligations',{}).get(key) if adjudication else None
        if forced:value=adjudication.get('case_obligations',{}).get(key) if adjudication else None
        obligations[key]=value
    pending=inventory_pending or result['pending_claims'] or any(v is None for v in obligations.values())
    result.update(inventory_pending=bool(inventory_pending),case_obligations=obligations,
        identity_adjudication_required=forced,
        inventory_counts={'initial':len(claims),'first':len(claims)+len((first or {}).get('added_claims',[])),
                          'second':len(claims)+len((second or {}).get('added_claims',[])),
                          'final':len(catalog) if not inventory_pending and not result['pending_claims'] else None},
        obligation_disagreements=disputes,omitted_obligations=[k for k,v in obligations.items() if v=='unmet'],
        semantic_status='pending_independent_review' if pending else 'reviewed',
        review_type='AI semantic review with human adjudication of disagreements',rates={})
    for name,numerator,denominator in [('id_validity','valid_citation_mentions','citation_mentions'),
        ('textual_support','textual_supported','textual_pairs'),('scientific_accuracy','scientific_correct','scientific_claims'),
        ('unsupported_claims','unsupported_claims','factual_claims')]:
        n,d=result[numerator],result[denominator]
        result['rates'][name]={'numerator':n,'denominator':d,'rate':n/d if d and not pending else None}
    return result
