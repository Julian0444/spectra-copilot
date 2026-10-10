"""Exercise the actual CLI in temporary directories; never call a model or API."""
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def harness(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'run_evals', Path(__file__).resolve().parents[1] / 'eval/run_evals.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cases = tmp_path / 'cases'
    cases.mkdir()
    (cases / 'labels.csv').write_text('case,z_true\na,0.5\nb,0.5\nc,0.5\n')
    for name in ('a', 'b', 'c'):
        (cases / f'{name}.npz').write_bytes(b'simulated spectrum')
    ckpt = tmp_path / 'checkpoint.pt'
    ckpt.write_bytes(b'simulated checkpoint')
    monkeypatch.setenv('DESI_FM_CKPT', str(ckpt))
    monkeypatch.setattr(mod.tools, '_index_paths', lambda: (str(ckpt), str(ckpt)))
    monkeypatch.setattr(mod.tools, 'predict_redshift_impl', lambda _: {'z_map': 0.5})
    monkeypatch.setattr(mod.tools, 'official_z', lambda r: r['z_map'])
    monkeypatch.setattr(mod.agent, 'run_structured', lambda *a, **k: {
        'z_final': 0.5, 'confidence': 'high', 'usage': {},
        'tokens_in': 10, 'tokens_out': 2})
    monkeypatch.setattr(mod, 'EVAL_DIR', tmp_path)
    out = tmp_path / 'run.csv'

    def run(*args):
        monkeypatch.setattr(sys, 'argv', ['run_evals', '--cases', str(cases),
                                         '--out', str(out), *args])
        mod.main()

    def rows():
        with out.open() as f:
            return list(csv.DictReader(f))

    return mod, run, rows, out, cases


@pytest.mark.parametrize('incomplete_status', ['pending', 'error'])
def test_resume_early_hole_keeps_later_completed_rows(harness, monkeypatch, capsys, incomplete_status):
    mod, run, rows, out, _ = harness
    run()
    existing = rows()
    existing[0]['status'] = incomplete_status
    mod.write_csv(out, existing)
    calls = []
    original = mod.tools.predict_redshift_impl
    monkeypatch.setattr(mod.tools, 'predict_redshift_impl',
                        lambda p: (calls.append(Path(p).stem), original(p))[1])
    run('--resume')
    assert calls == []  # reuse the baseline preserved in the failed agent row
    assert [r['case'] for r in rows()] == ['a', 'b', 'c']
    assert all(r['status'] == 'ok' for r in rows())


def printed_summary(capsys):
    text = capsys.readouterr().out
    return json.loads(text[text.rfind('\n{') + 1:])


def test_normal_completion_and_noop_resume_match_persisted_summary(harness, monkeypatch, capsys):
    mod, run, rows, out, _ = harness
    run()
    summary = printed_summary(capsys)
    for k, v in mod.summarize(rows()).items():
        assert summary[k] == v
    before = out.read_bytes()
    monkeypatch.setattr(mod.agent, 'run_structured', lambda *a, **k: pytest.fail('completed case rerun'))
    run('--resume')
    assert out.read_bytes() == before
    assert printed_summary(capsys) == summary


@pytest.mark.parametrize('interrupt_case', ['a', 'b', 'c'])
def test_interrupt_then_resume_preserves_every_case(harness, monkeypatch, capsys, interrupt_case):
    mod, run, rows, _, _ = harness
    real = mod.agent.run_structured

    def interrupted(path, **kwargs):
        if Path(path).stem == interrupt_case:
            raise KeyboardInterrupt()
        return real(path, **kwargs)

    monkeypatch.setattr(mod.agent, 'run_structured', interrupted)
    with pytest.raises(KeyboardInterrupt):
        run()
    saved = rows()
    assert [r['case'] for r in saved] == ['a', 'b', 'c']
    summary = printed_summary(capsys)
    assert summary['n'] == 3
    assert summary['n_error'] == 1
    completed = [r for r in saved if r['status'] == 'ok']
    monkeypatch.setattr(mod.agent, 'run_structured', real)
    run('--resume')
    assert all(r['status'] == 'ok' for r in rows())
    assert all(r in rows() for r in completed)
    assert printed_summary(capsys)['agent']['total_tokens'] == 36


def test_failure_rows_and_baselines_are_preserved_and_retried(harness, monkeypatch, capsys):
    mod, run, rows, _, _ = harness
    real = mod.agent.run_structured
    calls = []

    def fail(path, **kwargs):
        calls.append(Path(path).stem)
        if Path(path).stem == 'b':
            raise RuntimeError('should not be persisted')
        return real(path, **kwargs)

    monkeypatch.setattr(mod.agent, 'run_structured', fail)
    run()
    assert calls == ['a', 'b', 'b', 'c']
    summary = printed_summary(capsys)
    assert summary['n_error'] == 1 and summary['model_only']['n'] == 3
    assert summary['agent']['n'] == 2
    assert summary['agent']['rate_015_all_cases'] == .667
    calls.clear()
    monkeypatch.setattr(mod.agent, 'run_structured',
                        lambda p, **k: (calls.append(Path(p).stem), real(p, **k))[1])
    run('--resume')
    assert calls == ['b']
    assert all(r['status'] == 'ok' for r in rows())


def test_baseline_failure_does_not_abort_later_cases(harness, monkeypatch, capsys):
    mod, run, rows, _, _ = harness
    real = mod.tools.predict_redshift_impl

    def fail(path):
        if Path(path).stem == 'a':
            raise ValueError('bad input')
        return real(path)

    monkeypatch.setattr(mod.tools, 'predict_redshift_impl', fail)
    run('--baseline-only')
    assert [r['status'] for r in rows()] == ['error', 'baseline', 'baseline']
    assert printed_summary(capsys)['model_only']['n'] == 2
    monkeypatch.setattr(mod.tools, 'predict_redshift_impl', real)
    run('--baseline-only', '--resume')
    assert all(r['status'] == 'baseline' for r in rows())


def test_baseline_resume_skips_completed_rows(harness, monkeypatch):
    mod, run, _, _, _ = harness
    monkeypatch.setattr(mod.agent, 'run_structured', lambda *a, **k: pytest.fail('paid API'))
    run('--baseline-only')
    monkeypatch.setattr(mod.tools, 'predict_redshift_impl', lambda *a: pytest.fail('rerun'))
    run('--baseline-only', '--resume')


def test_default_destinations_are_new_and_mode_specific(harness, monkeypatch, tmp_path):
    mod, _, _, _, cases = harness
    for baseline in (True, False, True):
        monkeypatch.setattr(sys, 'argv', ['run_evals', '--cases', str(cases)] +
                            (['--baseline-only'] if baseline else []))
        mod.main()
    files = list((tmp_path / 'runs').glob('*/results.csv'))
    assert len(files) == 3
    assert sum(p.parent.name.startswith('baseline-') for p in files) == 2
    assert sum(p.parent.name.startswith('agent-') for p in files) == 1


@pytest.mark.parametrize('args', [[], ['--resume', '--baseline-only'],
                                   ['--resume', '--model', 'other-model'],
                                   ['--resume', '--limit', '1']])
def test_incompatible_reuse_rejected_without_writing(harness, args):
    _, run, _, out, _ = harness
    run()
    before = out.read_bytes()
    manifest = out.with_suffix('.manifest.json').read_bytes()
    with pytest.raises(ValueError):
        run(*args)
    assert out.read_bytes() == before
    assert out.with_suffix('.manifest.json').read_bytes() == manifest


@pytest.mark.parametrize('changed', ['label', 'spectrum', 'checkpoint', 'code'])
def test_changed_inputs_or_protocol_rejected(harness, monkeypatch, changed):
    mod, run, _, out, cases = harness
    run()
    before = out.read_bytes()
    if changed == 'label':
        (cases / 'labels.csv').write_text('case,z_true\na,0.6\nb,0.5\nc,0.5\n')
    elif changed == 'spectrum':
        (cases / 'a.npz').write_bytes(b'different input')
    elif changed == 'checkpoint':
        (cases.parent / 'checkpoint.pt').write_bytes(b'different model')
    else:
        monkeypatch.setattr(mod, 'SCHEMA_VERSION', 999)
    with pytest.raises(ValueError, match='Incompatible'):
        run('--resume')
    assert out.read_bytes() == before


def test_legacy_csv_is_never_adopted_or_overwritten(harness):
    _, run, _, out, _ = harness
    out.write_text('case,z_true\na,0.5\n')
    before = out.read_bytes()
    with pytest.raises(ValueError, match='manifest'):
        run('--resume')
    assert out.read_bytes() == before


def test_empty_or_duplicate_cases_rejected(harness):
    _, run, _, out, cases = harness
    for text in ('case,z_true\n', 'case,z_true\na,0.5\na,0.5\n'):
        (cases / 'labels.csv').write_text(text)
        with pytest.raises(ValueError):
            run()
        assert not out.exists()


def test_atomic_write_failure_preserves_old_bytes(harness, monkeypatch):
    mod, run, rows, out, _ = harness
    run()
    before = out.read_bytes()

    def interrupted(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(mod.os, 'replace', interrupted)
    with pytest.raises(KeyboardInterrupt):
        mod.write_csv(out, rows()[:1])
    assert out.read_bytes() == before
    assert not list(out.parent.glob('.run.csv.*'))


def test_all_writes_include_later_completed_rows(harness, monkeypatch):
    mod, run, rows, out, _ = harness
    run()
    saved = rows()
    saved[0]['status'] = 'error'
    mod.write_csv(out, saved)
    writes = []
    original = mod.write_csv

    def record(path, records):
        writes.append([r.copy() for r in records])
        original(path, records)

    monkeypatch.setattr(mod, 'write_csv', record)
    run('--resume')
    assert len(writes) >= 2
    assert all([r['case'] for r in batch] == ['a', 'b', 'c'] for batch in writes)
    assert all(batch[1:] == saved[1:] for batch in writes)


def test_concurrent_writer_rejected(harness):
    mod, run, _, out, _ = harness
    with out.with_suffix('.lock').open('a') as lock:
        mod.fcntl.flock(lock, mod.fcntl.LOCK_EX | mod.fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='already in use'):
            run()
    assert not out.exists()
