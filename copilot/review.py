"""Mechanical citation checks plus explicit human semantic-review accounting.

No regex, overlap score or model grades semantic support. Independent reviewers
supply atomic claims and judgments; disagreement needs a third adjudicator.
"""
from copilot import rag

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
            result['textual_supported'] += sum(v=='supported' for v in agreed['reference_support'].values())
            result['scientific_correct'] += science == 'correct' and c.get('scientific', c.get('external_scientific', False))
            result['unsupported_claims'] += support == 'unsupported' or missing
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
