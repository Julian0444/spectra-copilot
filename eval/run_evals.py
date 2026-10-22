"""Historical evaluator (Haiku 4.5); separate from the Haiku 5.5 bounded executor.

Evaluate into a new, mode-specific run directory; preserve historical CSVs.

Each run owns results.csv and an immutable manifest.json. Resume requires the
same selected cases, input bytes, checkpoint, code, assets and LLM model. Every
CSV replacement is atomic and contains the entire selected case map, including
pending/error rows. Completed rows survive interruptions; an in-flight request
may need repeating (including its API cost). SIGKILL cannot flush in-flight work.

    python eval/run_evals.py --baseline-only
    python eval/run_evals.py --out eval/runs/experiment/results.csv
    python eval/run_evals.py --out eval/runs/experiment/results.csv --resume

Agent runs make paid API calls. Baseline runs do not. Historical evaluations
used strict error < 0.15 and < 0.05; these conventions remain unchanged here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import tempfile
import uuid
import sys

from copilot import agent, tools, rag
from desi_fm.inputs import CONTRACT_VERSION

EVAL_DIR = Path(__file__).resolve().parent
FIELDS = ["case", "z_true", "z_model", "z_final", "confidence",
          "dzn", "ok15", "ok05", "tokens", "status"]
SCHEMA_VERSION = 4


def dz_norm(z: float, z_true: float) -> float:
    return abs(z - z_true) / (1.0 + z_true)


@contextmanager
def atomic_file(path: Path):
    """Flush a sibling temporary file, then replace; failures leave old bytes."""
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            yield f
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_csv(path: str | Path, rows: list[dict]) -> None:
    with atomic_file(Path(path)) as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, restval='')
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError('Incompatible results schema')
        return list(reader)


def summarize(rows: list[dict]) -> dict:
    """Metrics are derived only from persisted rows, never invocation usage."""
    ok = [r for r in rows if r['status'] == 'ok']
    model_dzn = [dz_norm(float(r['z_model']), float(r['z_true']))
                 for r in rows if r.get('z_model') not in (None, '')]

    def metrics(values):
        n = len(values)
        return {'n': n,
                'rate_015': round(sum(d < .15 for d in values) / n, 3) if n else None,
                'rate_005': round(sum(d < .05 for d in values) / n, 3) if n else None,
                'mae_norm': round(sum(values) / n, 4) if n else None}

    out = {'n': len(rows), 'n_ok': len(ok),
           'n_baseline': sum(r['status'] == 'baseline' for r in rows),
           'n_error': sum(r['status'] == 'error' for r in rows),
           'n_pending': sum(r['status'] == 'pending' for r in rows),
           'model_only': metrics(model_dzn)}
    out['agent'] = metrics([float(r['dzn']) for r in ok])
    out['agent']['by_confidence'] = {}
    out['agent']['total_tokens'] = sum(int(r['tokens']) for r in ok)
    out['agent']['rate_015_all_cases'] = (round(sum(int(r['ok15']) for r in ok) / len(rows), 3)
                                         if rows else None)
    if ok:
        out['agent']['by_confidence'] = {
            level: {'n': len(sub),
                    'rate_015': round(sum(int(r['ok15']) for r in sub) / len(sub), 3)}
            for level in ('high', 'medium', 'low')
            if (sub := [r for r in ok if r['confidence'] == level])}
        out['agent']['total_tokens'] = sum(int(r['tokens']) for r in ok)
        out['agent']['rate_015_all_cases'] = round(
            sum(int(r['ok15']) for r in ok) / len(rows), 3)
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run_identity(items: list[str], labels: dict, cases: Path, baseline: bool,
                 model: str) -> dict:
    """Fingerprint actual local inputs and implementation, without storing secrets."""
    import desi_fm
    code = {'evaluator': sha256(Path(__file__))}
    for prefix, directory in [('copilot', Path(tools.__file__).parent),
                              ('desi_fm', Path(desi_fm.__file__).parent)]:
        code.update({f'{prefix}/{p.name}': sha256(p) for p in sorted(directory.glob('*.py'))})
    checkpoint = Path(os.environ.get('DESI_FM_CKPT') or tools._hub_checkpoint())
    assets = {'checkpoint': sha256(checkpoint)}
    if not baseline:
        index, metadata = tools._index_paths()
        assets.update(index=sha256(Path(index)), index_metadata=sha256(Path(metadata)))
        assets.update(rag.corpus_hashes())
    versions = {}
    for name in ('numpy', 'scipy', 'torch', 'anthropic', 'faiss-cpu', 'rank_bm25', 'mcp', 'pydantic', 'desi-fm', 'spectra-copilot'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {'schema_version': SCHEMA_VERSION,
            'mode': 'baseline' if baseline else 'agent',
            'llm_model': None if baseline else model,
            'protocol': {'model_input': 'full-spectrum', 'ok15': 'dzn < 0.15',
                         'policy': agent.explanation.POLICY_VERSION,
                         'ok05': 'dzn < 0.05', 'agent_attempts': 1,
                         'input_contract': CONTRACT_VERSION,
                         'agent_input': 'opaque-scientific-input-v2',
                         'max_analysis_calls': 6, 'max_runner_iterations': 8},
            'cases': [{'case': c, 'z_true': labels[c],
                       'sha256': sha256(cases / f'{c}.npz')} for c in items],
            'code_sha256': code, 'assets_sha256': assets, 'versions': versions}


def validate_rows(rows: list[dict], labels: dict, items: list[str], baseline: bool) -> dict:
    saved = {}
    statuses = {'pending', 'error', 'baseline' if baseline else 'ok'}
    for r in rows:
        case = r['case']
        if case not in items or case in saved or r['status'] not in statuses:
            raise ValueError('Unknown/duplicate case or incompatible row status')
        if float(r['z_true']) != labels[case]:
            raise ValueError('Saved label differs from manifest')
        for key in ('z_model', 'z_final', 'dzn'):
            if r[key] != '' and not math.isfinite(float(r[key])):
                raise ValueError('Non-finite saved result')
        if r['status'] in {'ok', 'baseline'} and r['z_model'] == '':
            raise ValueError('Completed result lacks model prediction')
        if r['status'] == 'ok':
            if float(r['z_final']) != float(r['z_model']):
                raise ValueError('Saved result violates official model prediction')
            dzn = dz_norm(float(r['z_final']), labels[case])
            if (not math.isclose(float(r['dzn']), dzn, abs_tol=1e-12)
                    or int(r['ok15']) != int(dzn < .15)
                    or int(r['ok05']) != int(dzn < .05)
                    or int(r['tokens']) < 0):
                raise ValueError('Inconsistent saved agent result')
        saved[case] = r
    return saved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', default='claude-haiku-4-5')
    ap.add_argument('--limit', type=int, default=0, help='0 = all; must match on resume')
    ap.add_argument('--cases', default=str(EVAL_DIR / 'cases'))
    ap.add_argument('--out', help='new CSV path; default: eval/runs/<mode>-<unique>/results.csv')
    ap.add_argument('--resume', action='store_true', help='requires explicit --out and matching manifest')
    ap.add_argument('--baseline-only', action='store_true', help='no API calls')
    a = ap.parse_args()
    if a.limit < 0 or (a.resume and not a.out):
        ap.error('--limit must be nonnegative; --resume requires --out')
    cases = Path(a.cases)
    labels = {}
    with (cases / 'labels.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            case, z = r['case'], float(r['z_true'])
            if (case in labels or not case or Path(case).name != case
                    or case in {'.', '..'} or not math.isfinite(z) or z < 0):
                raise ValueError('Duplicate/invalid case or redshift label')
            labels[case] = z
    items = sorted(labels)[:a.limit or None]
    if not items:
        raise ValueError('No evaluation cases selected')
    mode = 'baseline' if a.baseline_only else 'agent'
    run_id = f'{mode}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}'
    out = Path(a.out) if a.out else EVAL_DIR / 'runs' / run_id / 'results.csv'
    manifest_path = out.with_suffix('.manifest.json')
    summary_path = out.with_suffix('.summary.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    # Advisory lock on a separate, persistent inode avoids two writers/resumers.
    with out.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Run is already in use') from None
        if a.resume:
            if not manifest_path.exists():
                raise ValueError('Resume requires a manifest; historical CSVs cannot be adopted')
            manifest = json.loads(manifest_path.read_text())
            if manifest['identity']['mode'] != mode or manifest['identity']['llm_model'] != (None if a.baseline_only else a.model):
                raise ValueError('Incompatible run mode or LLM model')
        elif out.exists() or manifest_path.exists() or summary_path.exists():
            raise ValueError('Output already exists; use a new destination or compatible --resume')
        identity = run_identity(items, labels, cases, a.baseline_only, a.model)
        if a.resume:
            if manifest['identity'] != identity:
                raise ValueError('Incompatible run inputs, code, assets or protocol')
        else:
            manifest = {'run_id': run_id, 'identity': identity}
            with atomic_file(manifest_path) as f:
                json.dump(manifest, f, indent=2, allow_nan=False)
                f.write('\n')
        saved = validate_rows(read_csv(out), labels, items, a.baseline_only) if out.exists() else {}
        rows = {c: saved.get(c, {'case': c, 'z_true': labels[c], 'status': 'pending'}) for c in items}

        def persist():
            write_csv(out, [rows[c] for c in items])
            summary = summarize(read_csv(out))
            valid = summary['n_baseline'] if a.baseline_only else summary['n_ok']
            status = ('complete' if valid == len(items) else 'partial' if valid else
                      'pending' if summary['n_pending'] == len(items) else 'failed')
            summary.update(run_id=manifest['run_id'], mode=mode, results=str(out),
                           results_sha256=sha256(out), n_valid_results=valid,
                           completion_status=status, exit_code=0 if status == 'complete' else 2 if valid else 3)
            with atomic_file(summary_path) as f:
                json.dump(summary, f, indent=2, allow_nan=False)
                f.write('\n')
            return summary

        persist()
        try:
            for i, case in enumerate(items):
                previous = rows[case]
                if previous['status'] == ('baseline' if a.baseline_only else 'ok'):
                    continue
                row = {'case': case, 'z_true': labels[case], 'status': 'error'}
                rows[case] = row
                npz = str(cases / f'{case}.npz')
                try:
                    # Preserve a valid baseline across failed agent attempts/resumes.
                    z_model = (float(previous['z_model']) if previous.get('z_model') not in (None, '')
                               else float(tools.official_z(tools.predict_redshift_impl(npz))))
                    if not math.isfinite(z_model):
                        raise ValueError('Non-finite model prediction')
                    row['z_model'] = z_model
                    if a.baseline_only:
                        row['status'] = 'baseline'
                    else:
                        for attempt in (1,):
                            try:
                                result = agent.run_structured(npz, model=a.model)
                                if result is None or result.get('status') not in {'complete', 'ambiguous', 'insufficient_data'}:
                                    continue
                                z_final = float(result['model_z'])
                                if not math.isfinite(z_final) or z_final != z_model:
                                    raise ValueError('Agent result violates official model prediction')
                                dzn = dz_norm(z_final, labels[case])
                                row.update(z_final=z_model, confidence='not_applicable',
                                           dzn=dzn, ok15=int(dzn < .15), ok05=int(dzn < .05),
                                           tokens=int(result['tokens_in']) + int(result['tokens_out']),
                                           status='ok')
                                break
                            except Exception as exc:
                                # Do not persist exception text: SDK errors may carry secrets.
                                print(f'[{case}] attempt {attempt} ERROR {type(exc).__name__}')
                except Exception as exc:
                    print(f'[{case}] baseline ERROR {type(exc).__name__}')
                persist()
                print(f'[{i + 1}/{len(items)}] {case}: {row["status"]}')
        finally:
            summary = persist()
            print(json.dumps(summary, indent=2, allow_nan=False))
        return summary['exit_code']


if __name__ == '__main__':
    sys.exit(main())
