"""Custody check: counts and sanitized paths only, never private values.

Inspect versionable working trees, index blobs, every added/modified blob and
commit message since the frozen 5A base, working diffs and explicit LLM inputs.
NPZ metadata uses the same reader for files and Git blobs. Unreadable inputs
fail closed. Pass ignored scientific assets explicitly if exposed to the LLM.
This is a process guard, not a sandbox against deliberately disguised calls.
"""
import argparse
import ast
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import warnings

NUMBER = re.compile(r'(?<![A-Za-z0-9.])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9.])')
GENERATOR_ALLOWED = {'scripts/select_batch5b.py', 'tests/test_batch5b_protocol.py'}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


@lru_cache(maxsize=8)
def id_pattern(ids, boundaries=True):
    alternatives = '|'.join(re.escape(value) for value in sorted(ids, key=lambda value: (-len(value), value)))
    if not alternatives:
        return re.compile(r'(?!)')
    if not boundaries:
        return re.compile('(?:' + alternatives + ')')
    # Real numeric IDs may touch letters (obj<ID>), but never match inside a
    # longer number. Opaque case IDs retain their alphanumeric boundaries.
    numeric = '|'.join(re.escape(value) for value in ids if value.isdecimal())
    opaque = '|'.join(re.escape(value) for value in ids if not value.isdecimal())
    patterns = []
    if numeric:
        patterns.append(r'(?<!\d)(?:' + numeric + r')(?!\d)')
    if opaque:
        patterns.append(r'(?<![^\W_])(?:' + opaque + r')(?![^\W_])')
    return re.compile('|'.join(patterns))


def matching_ids(text, ids):
    return set(id_pattern(tuple(sorted(ids))).findall(text))


def tree_files(root):
    names = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
    return [root / name.decode() for name in sorted(set(names.split(b'\0'))) if name]


def blob_texts(name, data):
    """Identical metadata decoding for working files, staging and history."""
    yield str(name)
    if Path(name).suffix.lower() == '.npz':
        import numpy as np
        with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
            for key in arrays.files:
                yield key
                array = arrays[key]
                if array.dtype.kind in 'US':
                    yield json.dumps(array.tolist(), ensure_ascii=False)
                elif key not in ('flux', 'wavelength', 'ivar', 'mask'):
                    yield json.dumps(array.tolist())
    else:
        yield data.decode('utf-8', errors='replace')


def texts(path):
    if path.is_symlink():
        yield str(path.readlink())
    yield from blob_texts(path, path.read_bytes())


def index_blobs(root):
    for entry in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, oid, stage = header.decode().split()
        if stage != '0' or mode not in ('100644', '100755', '120000'):
            raise ValueError('unsupported index entry')
        yield name.decode(), oid


def history_blobs(root, commit):
    raw = git(root, 'diff-tree', '--root', '-m', '--no-commit-id', '--raw', '-r', '-z',
              '--no-renames', '--diff-filter=AMT', commit, '--').split(b'\0')
    for offset in range(0, len(raw)-1, 2):
        header, name = raw[offset:offset+2]
        fields = header.decode().split()
        if len(fields) != 5 or fields[1] not in ('100644', '100755', '120000'):
            raise ValueError('unsupported historical entry')
        yield name.decode(), fields[3]


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
    hits = matching_ids(text, ids)
    # Isolated redshifts never trigger a violation; count nearby ID-label pairs.
    pairs = set()
    for token in hits:
        if token not in labels:
            continue
        for match in id_pattern((token,)).finditer(text):
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


def acceptance_references(text):
    """Reject executable selector/generator references, regardless of role.

    Development consumers must read the frozen JSON manifest. Documentation
    mentioning a filename and scripts copying source bytes are not imports.
    Full Git blobs are parsed as Python; the lexical fallback also checks
    imports in patches/messages and the previous reserved-role guard.
    """
    direct = re.findall(r'\bsynthetic\s*\(\s*(?:role\s*=\s*)?([\'"])acceptance\1', text)
    count = len(direct) + len(re.findall(
        r'(?:from\s+[\w.]*select_batch5b\s+import\b|'
        r'\bimport\s+[\w.]*select_batch5b\b|'
        r'from\s+[\w.]+\s+import\s+select_batch5b\b)', text))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return count
    # Follow literal command/source assignments into process and exec sinks.
    # Reading bytes for an archive is allowed; executing those bytes is not.
    tainted=set()
    def selector_value(node):
        return any((isinstance(child,ast.Constant) and isinstance(child.value,str)
                    and 'select_batch5b' in child.value) or
                   (isinstance(child,ast.Name) and child.id in tainted)
                   for child in ast.walk(node))
    assignments=[node for node in ast.walk(tree) if isinstance(node,(ast.Assign,ast.AnnAssign))]
    while True:
        before=len(tainted)
        for node in assignments:
            if node.value is not None and selector_value(node.value):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                tainted.update(child.id for target in targets for child in ast.walk(target) if isinstance(child,ast.Name))
        if len(tainted)==before:break
    execution={'run','Popen','call','check_call','check_output','system','popen','exec','eval'}
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module in {'subprocess','os','builtins'}:
            execution.update(alias.asname for alias in node.names if alias.name in execution and alias.asname)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'select_batch5b':
            count += 1
        elif isinstance(node, ast.Attribute) and (node.attr == 'select_batch5b' or
                (node.attr == 'synthetic' and isinstance(node.value, ast.Name) and
                 node.value.id in {'selection', 'select_batch5b'})):
            count += 1
        elif isinstance(node, ast.Call):
            name = (node.func.id if isinstance(node.func, ast.Name) else
                    node.func.attr if isinstance(node.func, ast.Attribute) else '')
            if name == 'synthetic':
                count += 1
            if name in execution and any(selector_value(arg) for arg in
                    [*node.args,*(keyword.value for keyword in node.keywords)]):
                count += 1
            if name in {'__import__', 'import_module', 'run_path', 'spec_from_file_location', 'getattr'}:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if 'select_batch5b' in arg.value or (name == 'getattr' and arg.value == 'synthetic'):
                            count += 1
    return count


def safe_path(path, private):
    ids, labels, _ = private
    # Redaction is deliberately broader than detection: never echo even an ID
    # embedded in a longer token when another violation caused this path report.
    redacted = id_pattern(tuple(sorted(ids)), False).sub('[redacted]', str(path))
    values = {abs(value) for value in labels.values()}
    numbers = r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?'
    return re.sub(numbers, lambda match: '[redacted-label]' if abs(float(match.group())) in values
                  else match.group(), redacted)


def scan(private, repositories, llm_inputs):
    violations, checked = [], 0
    allowed_inputs = {(root/relative).resolve() for root, _ in repositories for relative in GENERATOR_ALLOWED}
    def check(path, content, generator_allowed=False):
        nonlocal checked
        checked += 1
        counts = inspect_text(content, private)
        references = 0 if generator_allowed else acceptance_references(content)
        if any(counts) or references:
            violations.append({'path': safe_path(path, private), 'id_tokens': counts[0],
                               'id_label_pairs': counts[1], 'expected_answers': counts[2],
                               'synthetic_acceptance_references': references})
    for root, base in repositories:
        for path in tree_files(root):
            if not path.is_file():
                raise OSError('unreadable tree entry')
            for content in texts(path):
                check(path, content, path.relative_to(root).as_posix() in GENERATOR_ALLOWED)
        blobs = {}
        def check_blob(surface, name, oid):
            if oid not in blobs:
                blobs[oid] = git(root, 'cat-file', 'blob', oid)
            for content in blob_texts(name, blobs[oid]):
                check(root/surface/name, content, name in GENERATOR_ALLOWED)
        for name, oid in index_blobs(root):
            check_blob('.index', name, oid)
        seen = set()
        for commit in git(root, 'rev-list', '--reverse', base+'..HEAD').decode().splitlines():
            check(root/'.commit-message'/commit, git(root, 'show', '-s', '--format=%B', commit).decode())
            for name, oid in history_blobs(root, commit):
                if (name, oid) not in seen:
                    check_blob('.history/'+commit, name, oid)
                    seen.add((name, oid))
        # Working diffs include removed text; keep per-file provenance for N-1.
        for name in git(root, 'diff', '--name-only', '-z', base, '--').split(b'\0'):
            if name:
                name = name.decode()
                content = git(root, 'diff', '--no-ext-diff', '--no-textconv', base, '--', name)
                check(root/'.branch-diff'/name, content.decode('utf-8', errors='replace'), name in GENERATOR_ALLOWED)
    for path in llm_inputs:
        paths = sorted(path.rglob('*')) if path.is_dir() else [path]
        for file in paths:
            if file.is_dir():
                continue
            for content in texts(file):
                check(file, content, file.resolve() in allowed_inputs)
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
        result = scan(private, roots, args.llm_input)
    except Exception:
        print(json.dumps({'errors': 1, 'violating_surfaces': 0}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result['violating_surfaces'] else 0


if __name__ == '__main__':
    sys.exit(main())
