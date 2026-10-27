"""D-r2 regressions using invented reports only; no application API calls."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from copilot import review, review_annotations as annotations
from copilot.acceptance_io import sha256, write_json
from test_ai_review import fixture


def case_fixture():
    claims, a, b = fixture()
    for case in (a, b):
        case.update(identity_incident=False, inventory_disputes=[])
        case['judgments']['c1'].update(observation_ids=[], critical_error=True)
    packet = {'review_id': 'r', 'claims': claims, 'observations': [],
              'report': {'citations': [{'id': 'CaH_3969'}]}}
    return packet, a, b


def resolution(packet, a, b, final):
    return {'reviewer': 'Julian', 'independent': True, 'judgments': {},
            'case_obligations': {}, 'inventory_resolution': {
                'input_sha256': annotations.inventory_digest(packet['claims'], a, b),
                'claims': final, 'reason': 'Invented inventory decision'}}


@pytest.mark.parametrize('change', ['omit', 'rewrite', 'unchanged'])
def test_inventory_resolution_cannot_touch_undisputed_agreement(change):
    packet, a, b = case_fixture()
    final = deepcopy(packet['claims'])
    if change == 'omit':
        final = []
    elif change == 'rewrite':
        final[0]['text'] = 'Rewritten agreed assertion'
    j = resolution(packet, a, b, final)
    with pytest.raises(ValueError, match='^No registered inventory dispute or addition to resolve$'):
        review.score_annotation_pair(packet['claims'], a, b, j)


def test_resolution_of_another_dispute_cannot_drop_critical_agreement():
    packet, a, b = case_fixture()
    packet['claims'].append({'id': 'c2', 'text': 'Disputed assertion', 'reference_ids': []})
    a['inventory_complete'] = False
    a['inventory_disputes'] = [{'kind': 'exclude', 'claim_ids': ['c2'],
                               'spans': [], 'proposed_texts': [], 'reason': 'Invented'}]
    j = resolution(packet, a, b, [])
    with pytest.raises(ValueError, match='^Undisputed inventory claim must retain its ID, text and reference_ids$'):
        review.score_annotation_pair(packet['claims'], a, b, j)


def test_adjudication_validator_requires_original_dispute_context():
    packet, a, b = case_fixture()
    j = resolution(packet, a, b, [])
    with pytest.raises(ValueError, match='^Original annotation context required for inventory resolution$'):
        annotations.validate_case(j, packet, adjudication=True)


def test_registered_split_reports_changes_without_inflating_disagreements():
    packet, a, b = case_fixture()
    a['inventory_complete'] = False
    a['inventory_disputes'] = [{'kind': 'split', 'claim_ids': ['c1'], 'spans': [],
                               'proposed_texts': ['First half', 'Second half'], 'reason': 'Compound'}]
    final = [{'id': 'c1', 'text': 'First half', 'reference_ids': []},
             {'id': 'split2', 'text': 'Second half', 'reference_ids': []}]
    j = resolution(packet, a, b, final)
    j['judgments'] = {c['id']: deepcopy(a['judgments']['c1']) for c in final}
    scored = review.score_annotation_pair(packet['claims'], a, b, j)
    assert scored['inventory_changes'] == {'excluded': [], 'changed': ['c1'], 'added': ['split2']}
    assert scored['changed'] == ['c1', 'split2']
    assert scored['disagreements'] == []
    assert scored['semantic_status'] == 'reviewed'


def test_blindness_forcing_is_not_reviewer_disagreement():
    packet, a, b = case_fixture()
    scored = review.score_annotation_pair(packet['claims'], a, b, blindness_intact=False)
    assert scored['disagreements'] == []
    assert scored['forced'] == ['c1'] and scored['pending_claims'] == 1


@pytest.mark.parametrize('mistake', ['self_pair', 'unreturned', 'external_quotation'])
def test_quotation_never_creates_pair_or_external_assertion(mistake):
    packet, a, _ = case_fixture()
    claim = packet['claims'][0]
    claim.update(id='r:quotation:CaH_3969', equivalence_key='quotation:CaH_3969', text='A literal excerpt')
    j = a['judgments'].pop('c1')
    j.update(factual=True, scientific=False, external_scientific=False,
             scientific_accuracy='not_applicable', critical_error=False)
    a['judgments'][claim['id']] = j
    if mistake == 'external_quotation':
        j.update(scientific=True, external_scientific=True, scientific_accuracy='correct')
    else:
        ref = 'CaH_3969' if mistake == 'self_pair' else 'not-emitted'
        j.update(reference_ids=[ref], reference_support={ref: 'supported'})
    with pytest.raises(ValueError, match='[Rr]eference|[Qq]uotation'):
        annotations.validate_case(a, packet)


def test_quotation_literal_has_no_missing_citation_or_semantic_pair():
    packet, a, b = case_fixture()
    claim = packet['claims'][0]
    claim.update(id='r:quotation:CaH_3969', equivalence_key='quotation:CaH_3969')
    for case in (a, b):
        j = case['judgments'].pop('c1')
        j.update(factual=True, scientific=False, external_scientific=False,
                 textual_support='supported', scientific_accuracy='not_applicable', critical_error=False)
        case['judgments'][claim['id']] = j
        annotations.validate_case(case, packet)
    score = review.score_annotation_pair(packet['claims'], a, b)
    assert score['textual_pairs'] == score['missing_required_citations'] == 0
    assert score['rates']['textual_support']['rate'] is None


def test_human_judgment_on_registered_single_reviewer_addition_validates():
    packet, a, b = case_fixture()
    addition = {'id': annotations.added_id('r', 'An omitted assertion'),
                'text': 'An omitted assertion', 'reference_ids': [], 'occurrences': []}
    a['added_claims'] = [addition]
    a['judgments'][addition['id']] = deepcopy(a['judgments']['c1'])
    j = {'reviewer': 'Julian', 'independent': True, 'case_obligations': {},
         'judgments': {addition['id']: deepcopy(a['judgments']['c1'])}}
    annotations.validate_case(j, packet, adjudication=True, first=a, second=b)
    assert review.score_annotation_pair(packet['claims'], a, b, j)['semantic_status'] == 'reviewed'


def joined_fixture(tmp_path, n=1):
    from test_acceptance import plan, report
    from copilot.acceptance import execute_plan
    from copilot.review_packet import prepare
    p, labels, _ = plan(tmp_path, n)
    run = tmp_path / 'run'
    execute_plan(p, run, runner=lambda _: report())
    if n == 128:  # Re-seal INVENTED simulation as proposal; never real evidence.
        manifest = json.loads((run / 'manifest.json').read_text())
        manifest['mode'] = 'proposal'
        write_json(run / 'manifest.json', manifest)
        seal = json.loads((run / 'seal.json').read_text())
        seal['manifest_sha256'] = sha256(run / 'manifest.json')
        write_json(run / 'seal.json', seal)
        write_json(run.with_name('run.seal-record.json'), {
            'schema': 'batch5c-seal-record-v1', 'seal_sha256': sha256(run / 'seal.json')})
        value = json.loads(labels.read_text())
        for c in value['cases'][:80]:
            c['kind'] = 'real'
        write_json(labels, value)
    instruction = tmp_path / 'INSTRUCTIONS.md'
    instruction.write_text('Invented instructions')
    package, mapping = tmp_path / 'package', tmp_path / 'mapping.json'
    prepare(run, package, mapping, instruction)
    _, packets = annotations.read_package(package)
    files = []
    for name in ('A', 'B'):
        cases = {}
        for key, packet in packets.items():
            _, a, _ = case_fixture()
            a['reviewer'] = name
            judgment = a['judgments']['c1']
            a['judgments'] = {c['id']: deepcopy(judgment) for c in packet['claims']}
            cases[key] = a
        path = tmp_path / (name + '.json')
        write_json(path, {'schema': 'batch5c-ai-annotation-v1', 'reviewer': name,
                         'independent': True, 'package_manifest_sha256': sha256(package / 'manifest.json'),
                         'cases': cases})
        files.append(path)
    registration = tmp_path / 'registration.json'
    write_json(registration, {'schema': 'batch5c-annotation-registration-v1',
        'first_sha256': sha256(files[0]), 'second_sha256': sha256(files[1]),
        'registered_before_reading_judgments': True})
    joined = tmp_path / 'joined.json'
    annotations.join_annotations(package, mapping, *files, registration, joined)
    return run, labels, package, mapping, files, registration, joined


def test_e2e_undisputed_critical_claim_cannot_disappear(tmp_path):
    run, labels, package, mapping, files, registration, joined = joined_fixture(tmp_path)
    _, packets = annotations.read_package(package)
    a, b = [json.loads(p.read_text()) for p in files]
    key = next(iter(packets))
    first = a['cases'][key]
    first['inventory_complete'] = False
    first['inventory_disputes'] = [{'kind': 'exclude', 'claim_ids': [packets[key]['claims'][-1]['id']],
        'spans': [], 'proposed_texts': [], 'reason': 'Another claim is disputed'}]
    write_json(files[0], a)
    registered = json.loads(registration.read_text())
    registered['first_sha256'] = sha256(files[0])
    write_json(registration, registered)
    j = resolution(packets[key], first, b['cases'][key], packets[key]['claims'][1:])
    path = tmp_path / 'adjudication.json'
    write_json(path, {'schema': 'batch5c-ai-adjudication-v1', 'reviewer': 'Julian',
        'independent': True, 'package_manifest_sha256': sha256(package / 'manifest.json'), 'cases': {key: j}})
    with pytest.raises(ValueError, match='^Undisputed inventory claim must retain its ID, text and reference_ids$'):
        annotations.join_annotations(package, mapping, *files, registration, tmp_path / 'bad-join.json', path)


def test_proposal_case_schema_cannot_fall_back_to_legacy(tmp_path):
    from copilot.acceptance_score import score_sealed
    run, labels, *_, joined = joined_fixture(tmp_path, 128)
    value = json.loads(joined.read_text())
    for c in value['cases'].values():
        c.pop('schema')
    write_json(joined, value)
    with pytest.raises(ValueError, match='schema'):
        score_sealed(run, labels, review_path=joined)


def test_score_records_exact_join_hash(tmp_path):
    from copilot.acceptance_score import score_sealed
    run, labels, *_, joined = joined_fixture(tmp_path)
    result = score_sealed(run, labels, review_path=joined)
    assert result['reviews_sha256'] == sha256(joined)


def test_dispute_worksheet_cli_does_not_open_labels(tmp_path):
    _, labels, package, _, files, registration, _ = joined_fixture(tmp_path)
    labels.unlink()  # Tool must operate without labels, map or sealed run paths.
    output = tmp_path / 'worksheet.json'
    command = [sys.executable, '-B', '-m', 'copilot.review_annotations', 'worksheet',
               '--package', str(package), '--first', str(files[0]), '--second', str(files[1]),
               '--registration', str(registration), '--output', str(output)]
    completed = subprocess.run(command, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    worksheet = json.loads(output.read_text())
    assert worksheet['labels_read'] is False
    assert all(len(c['input_sha256']) == 64 for c in worksheet['cases'].values())


def test_cli_validates_adjudication_with_registered_annotation_context(tmp_path):
    _, _, package, _, files, registration, _ = joined_fixture(tmp_path)
    path = tmp_path / 'adjudication.json'
    write_json(path, {'schema': 'batch5c-ai-adjudication-v1', 'reviewer': 'Julian',
        'independent': True, 'package_manifest_sha256': sha256(package / 'manifest.json'), 'cases': {}})
    command = [sys.executable, '-B', '-m', 'copilot.review_annotations', 'validate',
               '--package', str(package), '--adjudication', str(path), '--first', str(files[0]),
               '--second', str(files[1]), '--registration', str(registration)]
    completed = subprocess.run(command, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
