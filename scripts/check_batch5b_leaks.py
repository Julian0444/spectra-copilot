"""Custody check. Outputs counts and sanitized paths only; never private values.

Scan versionable trees (tracked + untracked, respecting Git ignores), every
commit diff since the frozen 5A base, working diff, and explicit LLM inputs.
Ignored scientific assets are not development inputs: pass any file that will
be exposed to the LLM explicitly, including NPZs, via --llm-input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

TOKEN = re.compile(r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*')
NUMBER = re.compile(r'(?<![A-Za-z0-9.])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9.])')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


def tree_files(root):
    names = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
    return [root / name.decode() for name in sorted(set(names.split(b'\0'))) if name]


def texts(path):
    """Names/metadata matter too; explicit NPZ inputs inspect Unicode metadata."""
    yield str(path)
    if path.is_symlink():
        yield str(path.readlink())
    if path.suffix == '.npz':
        import numpy as np
        with np.load(path, allow_pickle=False) as data:
            for key in data.files:
                yield key
                array = data[key]
                if array.dtype.kind in 'US':
                    yield json.dumps(array.tolist(), ensure_ascii=False)
                elif key not in ('flux', 'wavelength', 'ivar', 'mask'):
                    yield json.dumps(array.tolist())
    else:
        # Versioned binary content is also scanned for embedded textual tokens.
        yield path.read_bytes().decode('utf-8', errors='replace')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def custody(cases):
    ids, labels, answers = set(), {}, set()
    for case in cases:
        keys = {str(case[key]) for key in ('case_id', 'object_id') if case.get(key) is not None}
        ids.update(keys)
        label = case.get('label', {}).get('z')
        if label is not None:
            for key in keys:
                labels[key] = float(label)
        if case.get('expected_answer'):
            answers.add(fingerprint(case['expected_answer']))
    if not ids:
        raise ValueError('empty custody')
    return ids, labels, answers


def inspect_text(text, private):
    ids, labels, answers = private
    hits = ids.intersection(TOKEN.findall(text))
    # A redshift alone never triggers a violation. Count ID-label pairs in the
    # same local record/window; numeric spellings are compared by value.
    pairs = set()
    for token in hits:
        if token not in labels:
            continue
        pattern = re.compile(r'(?<![A-Za-z0-9])' + re.escape(token) + r'(?![A-Za-z0-9])')
        for match in pattern.finditer(text):
            window = text[max(0, match.start()-256):match.end()+512]
            if any(float(number) == labels[token] for number in NUMBER.findall(window)):
                pairs.add(token)
                break
    answer_count = 0
    def visit(value):
        nonlocal answer_count
        if isinstance(value, dict):
            if fingerprint(value) in answers:
                answer_count += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    try:
        visit(json.loads(text))
    except (ValueError, RecursionError):
        pass
    return len(hits), len(pairs), answer_count


def safe_path(path, private):
    ids = private[0]
    return TOKEN.sub(lambda match: '[redacted]' if match.group() in ids else match.group(), str(path))


def scan(private, repositories, llm_inputs):
    violations, checked = [], 0
    def check(path, content):
        nonlocal checked
        checked += 1
        counts = inspect_text(content, private)
        if any(counts):
            violations.append({'path': safe_path(path, private), 'id_tokens': counts[0],
                               'id_label_pairs': counts[1], 'expected_answers': counts[2]})
    for root, base in repositories:
        for path in tree_files(root):
            if not path.is_file():
                raise OSError('unreadable tree entry')
            for content in texts(path):
                check(path, content)
        # Include intermediate commits, so deleting a leak later cannot hide it.
        for content in [git(root, 'diff', '--no-ext-diff', '--no-textconv', base, '--'),
                        git(root, 'diff', '--cached', '--no-ext-diff', '--no-textconv', base, '--'),
                        git(root, 'log', '--format=', '-p', '--no-ext-diff', '--no-textconv', base+'..HEAD', '--')]:
            check(root / '.branch-diff', content.decode('utf-8', errors='replace'))
    for path in llm_inputs:
        paths = sorted(path.rglob('*')) if path.is_dir() else [path]
        for file in paths:
            if file.is_dir():
                continue
            for content in texts(file):
                check(file, content)
    return {'checked_surfaces': checked, 'violating_surfaces': len(violations), 'violations': violations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--repository', nargs=2, action='append', required=True, metavar=('ROOT', 'BASE'))
    parser.add_argument('--llm-input', action='append', type=Path, required=True)
    args = parser.parse_args()
    try:
        cases = json.loads(args.private.read_text())['cases']
        private = custody(cases)
        roots = [(Path(root).resolve(), base) for root, base in args.repository]
        # A private oracle inside an inspected tree/input is itself a violation.
        result = scan(private, roots, args.llm_input)
    except Exception:
        print(json.dumps({'errors': 1, 'violating_surfaces': 0}))
        return 2  # Fail closed without printing exception data or private paths.
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result['violating_surfaces'] else 0


if __name__ == '__main__':
    sys.exit(main())
