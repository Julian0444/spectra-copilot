"""Deterministic metadata-only 5B selection. No spectra, inference or LLM calls.

Acceptance is written directly to a NEW private directory (0700/0600). stdout
contains only its SHA-256, bytes and counts. Never print rows or exceptions.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys

from check_batch5b_leaks import TOKEN, git, texts

SEED = 20261018
FAMILIES = ('emission', 'absorption', 'noise', 'coverage_gap', 'reversed_grid',
            'permuted_grid', 'invalid_support', 'single_line')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(data):
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n').encode()


def rank(domain, value):
    return digest(f'batch5b-v1:{SEED}:{domain}:{value}'.encode())


def case_id(domain, value):
    return 'case-' + rank(domain, value)[:24]


def synthetic(role):
    cases = []
    for family in FAMILIES:
        for index in range(6):
            key = rank(role+'-synthetic', f'{family}:{index}')
            seed = int(key[:8], 16)
            z = round(.05 + (int(key[8:16], 16) / 2**32) * 1.4, 8)
            peak = round(4800 + (int(key[16:24], 16) / 2**32) * 3400, 6)
            cid = case_id(role+'-synthetic', f'{family}:{index}')
            expected = {'case_id': cid, 'model_z_rule': 'equal_to_predict_tool_if_available',
                        'must_abstain_unique_z': family in ('single_line', 'noise', 'invalid_support'),
                        'must_reject_input': family == 'invalid_support'}
            if family == 'single_line':
                expected['admissible_z'] = [peak/rest-1 for rest in (1215.7, 3727.1, 5006.8, 6562.8) if peak/rest >= 1]
            cases.append({'case_id': cid, 'kind': 'synthetic', 'family': family,
                          'recipe': {'seed': seed, 'z': z, 'peak_angstrom': peak,
                                     'snr': (0, 2, 5, 10, 20, 50)[index]},
                          'label': {'z': None if family in ('noise', 'single_line', 'invalid_support') else z},
                          'v21_exposure': 'none_synthetic', 'cnn_exposure': 'none_synthetic',
                          'expected_answer': expected})
    return cases


def choose(rows, splits, excluded, dev_per_role=24, accept_per_role=40):
    """Rows follow eligible ordinal order; labels never affect ranking."""
    dev, accept, available = [], [], {}
    for role in ('train', 'validation'):
        pool = [(position, row) for position, row in enumerate(rows)
                if position >= 82000 and row['object_id'] in splits[role]
                and row['object_id'] not in excluded]
        pool.sort(key=lambda item: (rank('real-'+role, item[1]['object_id']), item[1]['object_id']))
        available[role] = len(pool)
        if len(pool) < dev_per_role + accept_per_role:
            raise ValueError('insufficient population')
        for phase, selected in [('development', pool[:dev_per_role]),
                                ('acceptance', pool[dev_per_role:dev_per_role+accept_per_role])]:
            target = dev if phase == 'development' else accept
            for position, row in selected:
                cid = case_id(phase+'-real', row['object_id'])
                target.append({'case_id': cid, 'kind': 'real', 'object_id': row['object_id'],
                               'eligible_position': position, 'label': {'z': row['z'], 'zwarn': row['zwarn']},
                               'v21_exposure': 'neither_train_nor_historical_validation',
                               'cnn_exposure': role,
                               'expected_answer': {'case_id': cid,
                                   'model_z_rule': 'equal_to_predict_tool_if_available',
                                   'catalog_reference_z': row['z'],
                                   'catalog_warning_caveat_if_quality_disclosed': not bool(row['zwarn']),
                                   'independent_predictor_accuracy_claim_allowed': False}})
    return dev, accept, available


def load_population(index, split_root, historical, labels, examples):
    with sqlite3.connect(f'file:{index.resolve()}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(
            'select object_id,z,zwarn,ordinal from objects where label_eligible=1 and input_eligible=1 order by ordinal')]
    all_ids = {row['object_id'] for row in rows}
    splits = {role: set(json.loads((split_root/role/'ids.json').read_text()))
              for role in ('train', 'validation', 'test')}
    if (len(rows) != 84759 or len(all_ids) != len(rows) or
        {role: len(ids) for role, ids in splits.items()} != {'train':64759, 'validation':10000, 'test':10000} or
        set.union(*splits.values()) != all_ids or sum(map(len, splits.values())) != len(all_ids)):
        raise ValueError('population identity failed')
    if any(not math.isfinite(row['z']) or row['z'] < 0 for row in rows):
        raise ValueError('invalid labels')
    historical_ids = set(json.loads(historical.read_text())['ids'])
    if historical_ids != {row['object_id'] for row in rows[80000:82000]}:
        raise ValueError('historical positions differ')
    with labels.open() as stream:
        label_rows = list(csv.DictReader(stream))
    if len(label_rows) != 150:
        raise ValueError('historical cases differ')
    case_ids = {rows[80000+int(row['heldout_index'])]['object_id'] for row in label_rows}
    if len(case_ids) != 150 or not case_ids <= historical_ids:
        raise ValueError('historical case identity failed')
    # Exclude all known design/demo objects. Synthetic demo files cannot be
    # selected as real rows; new synthetic recipes have different identities.
    import numpy as np
    demo_ids = set()
    for directory in examples:
        for path in sorted(directory.glob('*.npz')):
            with np.load(path, allow_pickle=False) as example:
                if 'object_id' in example:
                    demo_ids.add(str(example['object_id'].item()))
    tail_ids = {row['object_id'] for row in rows[82000:]}
    tail = {role: len(ids & tail_ids) for role, ids in splits.items()}
    if tail != {'train':2114, 'validation':333, 'test':312}:
        raise ValueError('tail identity failed')
    report = {'eligible':len(rows), 'splits':{k:len(v) for k,v in splits.items()}, 'tail':tail,
              'historical_cases_excluded':len(case_ids), 'demo_object_ids_excluded':len(demo_ids),
              'historical_validation_excluded':len(historical_ids)}
    return rows, splits, historical_ids | case_ids | demo_ids, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--splits', type=Path, required=True)
    parser.add_argument('--historical', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--examples', type=Path, action='append', required=True)
    parser.add_argument('--repository', nargs=2, action='append', required=True, metavar=('ROOT','BASE'))
    parser.add_argument('--visible', type=Path, action='append', required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--development', type=Path, required=True)
    parser.add_argument('--commitment', type=Path, required=True)
    args = parser.parse_args()
    try:
        os.umask(0o077)
        if args.private_dir.exists() or args.development.exists() or args.commitment.exists():
            raise ValueError('destination exists')
        roots = [Path(root).resolve() for root, _ in args.repository]
        private_root = args.private_dir.resolve()
        if any(private_root == root or root in private_root.parents for root in roots):
            raise ValueError('private custody must be outside repos')
        rows, splits, excluded, population = load_population(
            args.index, args.splits, args.historical, args.labels, args.examples)
        candidates = {row['object_id'] for row in rows[82000:]}
        visible_ids = set()
        visible_hashes = []
        for root, base in args.repository:
            for name in git(root, 'ls-tree', '-rz', '--name-only', base).split(b'\0'):
                if name:
                    content = git(root, 'show', base+':'+name.decode()).decode('utf-8', errors='replace')
                    visible_ids.update(candidates.intersection(TOKEN.findall(content)))
                    visible_ids.update(candidates.intersection(TOKEN.findall(name.decode())))
        for path in args.visible:
            visible_hashes.append({'sha256':digest(path.read_bytes()),'bytes':path.stat().st_size})
            for content in texts(path):
                visible_ids.update(candidates.intersection(TOKEN.findall(content)))
        excluded |= visible_ids
        dev, accept, available = choose(rows, splits, excluded)
        dev += synthetic('development')
        accept += synthetic('acceptance')
        if {x['case_id'] for x in dev} & {x['case_id'] for x in accept}:
            raise ValueError('case overlap')
        dev_document = {'schema':'batch5b-development-v1','seed':SEED,'cases':dev}
        private_document = {'schema':'batch5b-acceptance-v1','seed':SEED,'cases':accept}
        private_bytes = encode(private_document)
        counts = {'total':len(accept),'real':sum(x['kind']=='real' for x in accept),
                  'synthetic':sum(x['kind']=='synthetic' for x in accept),
                  'cnn_exposure':dict(Counter(x['cnn_exposure'] for x in accept)),
                  'synthetic_families':dict(Counter(x['family'] for x in accept if x['kind']=='synthetic'))}
        commitment = {'schema':'batch5b-commitment-v1','sha256':digest(private_bytes),
                      'bytes':len(private_bytes),'counts':counts,'seed':SEED,
                      'development_sha256':digest(encode(dev_document)),
                      'population':population, 'available_tail_after_exclusions':available,
                      'preexposed_tail_ids_excluded':len(visible_ids),
                      'source_identities':{name:{'sha256':digest(path.read_bytes()),'bytes':path.stat().st_size}
                           for name,path in [('index',args.index),('historical',args.historical),('labels',args.labels)]},
                      'split_identities':{role:{'sha256':digest((args.splits/role/'ids.json').read_bytes()),
                                              'bytes':(args.splits/role/'ids.json').stat().st_size}
                                          for role in splits},
                      'visible_source_identities':visible_hashes,
                      'repository_bases':[base for _,base in args.repository]}
        args.private_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        with (args.private_dir/'acceptance.json').open('xb') as stream:
            stream.write(private_bytes)
        for path,data in [(args.development,encode(dev_document)),(args.commitment,encode(commitment))]:
            with path.open('xb') as stream:
                stream.write(data)
        print(json.dumps({key:commitment[key] for key in ('sha256','bytes','counts')}))
        return 0
    except Exception:
        print(json.dumps({'errors':1}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
