"""Bounded R5A-01/O-1 checks in fresh copies; never mutate the source checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    files = ['pyproject.toml', 'tests/conftest.py', 'tests/test_mcp_asset_errors.py',
             'tests/test_tool_concurrency.py']
    modules = [str(p.relative_to(root)) for p in (root / 'copilot').rglob('*')
               if p.is_file() and p.suffix in ('.py', '.md', '.json')]
    tests = ['tests/test_mcp_asset_errors.py', 'tests/test_tool_concurrency.py']
    scenarios = [('baseline', None, None, None, 0),
                 ('all_exceptions_invalid_input', 'copilot/mcp_server.py',
                  'except SpectrumInputError:', 'except Exception:', 1),
                 ('asset_invalid_input', 'copilot/mcp_server.py',
                  'except SpectrumInputError:', 'except (SpectrumInputError, FileNotFoundError):', 1)]
    for name in ['predict_redshift_impl', 'reconstruct_spectrum_impl',
                 'find_similar_spectra_impl', '_model', '_index']:
        middle = '@lru_cache(maxsize=1)\n' if name.startswith('_') else ''
        scenarios.append(('unlocked_' + name, 'copilot/tools.py',
                          '@_serialized\n' + middle + 'def ' + name,
                          middle + 'def ' + name, 1))
    scenarios.append(('equivalent_explicit_lock', 'copilot/tools.py',
                      '        with _MODEL_INDEX_LOCK:\n            return function(*args, **kwargs)',
                      '        _MODEL_INDEX_LOCK.acquire()\n        try:\n            return function(*args, **kwargs)\n        finally:\n            _MODEL_INDEX_LOCK.release()', 0))
    results = []
    for name, file, before, after, expected in scenarios:
        target = args.output / name
        target.mkdir()
        for rel in files + modules:
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, dest)
        if file:
            p = target / file
            content = p.read_text()
            assert content.count(before) == 1, name
            p.write_text(content.replace(before, after))
        env = os.environ.copy()
        env.update(PYTHONPATH=str(target) + os.pathsep + env.get('PYTHONPATH', ''),
                   PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1')
        log = args.output / (name + '.log')
        with log.open('w') as output:
            run = subprocess.run([sys.executable, '-m', 'pytest', *tests, '-q',
                                  '-p', 'no:cacheprovider'], cwd=target, env=env,
                                 stdout=output, stderr=subprocess.STDOUT, timeout=60)
        text = log.read_text()
        failed = [line for line in text.splitlines() if line.startswith('FAILED ')]
        passed = run.returncode == expected and (expected == 0 or bool(failed)) and 'ERROR collecting' not in text
        result = dict(name=name, returncode=run.returncode, expected=expected,
                      verified=passed, failed_tests=failed,
                      summary=text.strip().splitlines()[-1],
                      log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
        results.append(result)
        print(json.dumps(result), flush=True)
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return 0 if all(row['verified'] for row in results) else 1


if __name__ == '__main__':
    sys.exit(main())
