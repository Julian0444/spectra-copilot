"""R1-P2-1: invented inventories; no provider calls or private acceptance data."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from copilot import review, review_annotations as A
from copilot.acceptance_io import sha256, write_json
from copilot.acceptance_score import score_sealed
from test_review_closure import case_fixture, joined_fixture, resolution

PRESERVE = 'Undisputed inventory claim must retain its ID, text and reference_ids'
ADJ_ADDITION = 'Adjudicator added_claims are forbidden; use registered inventory resolution'
UNPROPOSED = 'Final inventory changes require registered proposed texts or additions'


def dispute_other(packet, a):
    a['inventory_complete'] = False
    a['inventory_disputes'] = [{'kind': 'split', 'claim_ids': [packet['claims'][0]['id']],
        'spans': [], 'proposed_texts': ['Registered first half', 'Registered second half'],
        'reason': 'Invented compound claim'}]


def joint_addition(packet, a, b):
    text = 'An omitted critical assertion'
    c = {'id': A.added_id(packet['review_id'], text), 'text': text,
         'reference_ids': [], 'occurrences': []}
    for bundle in (a, b):
        bundle['added_claims'] = [deepcopy(c)]
        bundle['judgments'][c['id']] = deepcopy(next(iter(bundle['judgments'].values())))
        bundle['judgments'][c['id']]['critical_error'] = True
    return c


@pytest.mark.parametrize('mutation', ['exclude', 'rewrite', 'references'])
def test_joint_addition_preserved_during_another_dispute(mutation):
    packet, a, b = case_fixture()
    c = joint_addition(packet, a, b)
    dispute_other(packet, a)
    final = deepcopy(packet['claims'] + [c])
    if mutation == 'exclude':
        final.pop()
    elif mutation == 'rewrite':
        final[-1]['text'] = 'Registered first half'
    else:
        final[-1]['reference_ids'] = ['CaH_3969']
    j = resolution(packet, a, b, final)
    with pytest.raises(ValueError, match='^' + PRESERVE + '$'):
        A.validate_case(j, packet, adjudication=True, first=a, second=b)
    with pytest.raises(ValueError, match='^' + PRESERVE + '$'):
        review.score_annotation_pair(packet['claims'], a, b, j)


def test_undisputed_seed_references_cannot_change():
    packet, a, b = case_fixture()
    packet['claims'].append({'id': 'other', 'text': 'Other assertion', 'reference_ids': []})
    dispute_other(packet, a)
    final = deepcopy(packet['claims'])
    final[-1]['reference_ids'] = ['CaH_3969']
    j = resolution(packet, a, b, final)
    with pytest.raises(ValueError, match='^' + PRESERVE + '$'):
        A.validate_case(j, packet, adjudication=True, first=a, second=b)
    with pytest.raises(ValueError, match='^' + PRESERVE + '$'):
        review.score_annotation_pair(packet['claims'], a, b, j)


@pytest.mark.parametrize('mutation', ['new', 'rewritten'])
def test_resolution_text_must_have_been_registered(mutation):
    packet, a, b = case_fixture()
    dispute_other(packet, a)
    final = deepcopy(packet['claims'])
    if mutation == 'new':
        final.append({'id': 'new', 'text': 'Unproposed assertion', 'reference_ids': []})
    else:
        final[0]['text'] = 'Unproposed assertion'
    j = resolution(packet, a, b, final)
    with pytest.raises(ValueError, match='^' + UNPROPOSED + '$'):
        review.score_annotation_pair(packet['claims'], a, b, j)


def test_adjudicator_cannot_create_an_unregistered_pair():
    packet, a, b = case_fixture()
    c = {'id': A.added_id('r', 'New pair'), 'text': 'New pair',
         'reference_ids': ['CaH_3969'], 'occurrences': []}
    judgment = deepcopy(a['judgments']['c1'])
    judgment.update(reference_ids=['CaH_3969'], reference_support={'CaH_3969': 'supported'})
    j = {'reviewer': 'Julian', 'independent': True, 'case_obligations': {},
         'added_claims': [c], 'judgments': {c['id']: judgment}}
    with pytest.raises(ValueError, match='^' + ADJ_ADDITION + '$'):
        A.validate_case(j, packet, adjudication=True, first=a, second=b)
    with pytest.raises(ValueError, match='^' + ADJ_ADDITION + '$'):
        review.score_annotation_pair(packet['claims'], a, b, j)


def test_added_text_cannot_duplicate_a_seed():
    packet, a, _ = case_fixture()
    c = deepcopy(packet['claims'][0])
    c.update(id=A.added_id('r', c['text']), occurrences=[])
    a['added_claims'] = [c]
    a['judgments'][c['id']] = deepcopy(a['judgments']['c1'])
    with pytest.raises(ValueError, match='^Added claim text duplicates a seed$'):
        A.validate_case(a, packet)


def rewrite_registered(files, registration, docs):
    for path, doc in zip(files, docs):
        write_json(path, doc)
    write_json(registration, {'schema': 'batch5c-annotation-registration-v1',
        'first_sha256': sha256(files[0]), 'second_sha256': sha256(files[1]),
        'registered_before_reading_judgments': True})


def adjudication_file(tmp_path, package, key, case):
    path = tmp_path / 'adjudication.json'
    write_json(path, {'schema': 'batch5c-ai-adjudication-v1', 'reviewer': 'Julian',
        'independent': True, 'package_manifest_sha256': sha256(package / 'manifest.json'),
        'cases': {key: case}})
    return path


@pytest.mark.parametrize('include_joint', [False, True])
def test_e2e_worksheet_and_join_preserve_joint_critical_addition(tmp_path, include_joint):
    run, labels, package, mapping, files, registration, _ = joined_fixture(tmp_path)
    _, packets = A.read_package(package)
    key, packet = next(iter(packets.items()))
    docs = [json.loads(p.read_text()) for p in files]
    a, b = [d['cases'][key] for d in docs]
    c = joint_addition(packet, a, b)
    dispute_other(packet, a)
    rewrite_registered(files, registration, docs)
    ws = A.dispute_worksheet(package, *files, registration, tmp_path / 'worksheet.json')
    if include_joint:
        assert c['id'] in {x['id'] for x in ws['cases'][key]['claims']}
        assert ws['cases'][key]['claim_origins'][c['id']] == 'joint_addition'
        final = ws['cases'][key]['claims']
    else:
        final = packet['claims']
    j = resolution(packet, a, b, final)
    adj = adjudication_file(tmp_path, package, key, j)
    output = tmp_path / 'new-join.json'
    if not include_joint:
        with pytest.raises(ValueError, match='^' + PRESERVE + '$'):
            A.join_annotations(package, mapping, *files, registration, output, adj)
        assert not output.exists()
    else:
        A.join_annotations(package, mapping, *files, registration, output, adj)
        score = score_sealed(run, labels, review_path=output)
        assert score['rows'][0]['semantic']['critical_errors'] == len(packet['claims']) + 1
        assert score['global']['inventory_changes'] == {'excluded': 0, 'changed': 0, 'added': 0}
        assert score['strata']['kind']['synthetic']['inventory_changes'] == score['global']['inventory_changes']


def test_e2e_cli_rejects_adjudicator_addition_before_join(tmp_path):
    _, _, package, mapping, files, registration, _ = joined_fixture(tmp_path)
    _, packets = A.read_package(package)
    key, packet = next(iter(packets.items()))
    a, b = [json.loads(p.read_text())['cases'][key] for p in files]
    c = joint_addition(packet, deepcopy(a), deepcopy(b))
    j = {'reviewer': 'Julian', 'independent': True, 'case_obligations': {},
         'added_claims': [c], 'judgments': {}}
    adj = adjudication_file(tmp_path, package, key, j)
    done = subprocess.run([sys.executable, '-B', '-m', 'copilot.review_annotations', 'validate',
        '--package', str(package), '--adjudication', str(adj), '--first', str(files[0]),
        '--second', str(files[1]), '--registration', str(registration)], text=True, capture_output=True)
    assert done.returncode != 0 and ADJ_ADDITION in done.stderr
    with pytest.raises(ValueError, match='^' + ADJ_ADDITION + '$'):
        A.join_annotations(package, mapping, *files, registration, tmp_path / 'bad.json', adj)
