"""Bounded custody mutations in new private copies; no real acceptance is read."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    original = (root/'scripts/check_batch5b_leaks.py').read_text()
    mutations = [
        ('token_v1', 'return set(id_pattern(tuple(sorted(ids))).findall(text))',
         "return set(ids).intersection(re.findall(r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*', text))",
         'test_cli_punctuation_boundaries_and_complete_redaction[hyphen_filename]'),
        ('without_index', 'for name, oid in index_blobs(root):', 'for name, oid in []:',
         'test_cli_reads_npz_metadata_in_every_git_surface[index]'),
        ('without_history', 'for name, oid in history_blobs(root, commit):', 'for name, oid in []:',
         'test_cli_reads_npz_metadata_in_every_git_surface[history]'),
        ('without_messages',
         "check(root/'.commit-message'/commit, git(root, 'show', '-s', '--format=%B', commit).decode())",
         'pass  # mutation: skip commit messages', 'test_cli_reads_empty_commit_message'),
        ('without_generator_rule', 'references = 0 if generator_allowed else acceptance_references(content)',
         'references = 0', 'test_cli_rejects_public_acceptance_generator_reference[direct]'),
    ]
    results = {}
    for name, before, after, target in [('baseline', None, None, None)] + mutations:
        copy = args.output/name
        for relative in ['scripts/check_batch5b_leaks.py', 'scripts/select_batch5b.py',
                         'tests/test_batch5b_protocol.py']:
            destination = copy/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root/relative, destination)
        if before:
            if original.count(before) != 1:
                raise ValueError('mutation anchor changed')
            (copy/'scripts/check_batch5b_leaks.py').write_text(original.replace(before, after))
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_batch5b_protocol.py',
                                 '-q', '--tb=no', '-p', 'no:cacheprovider'], cwd=copy,
                                capture_output=True, text=True, timeout=90)
        output = result.stdout + result.stderr
        (args.output/(name+'.log')).write_text(output)
        passed = re.search(r'(\d+) passed', output)
        failed = re.search(r'(\d+) failed', output)
        detected = result.returncode == 1 and bool(failed) and target in output if target else result.returncode == 0
        results[name] = {'exit': result.returncode, 'passed': int(passed[1]) if passed else 0,
                         'failed': int(failed[1]) if failed else 0, 'expected_outcome': detected}
        (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
        print(json.dumps({name: results[name]}), flush=True)
        if not detected:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
