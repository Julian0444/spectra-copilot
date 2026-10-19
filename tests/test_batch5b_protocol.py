"""Custody/selection tests use invented metadata only; never the private oracle."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import check_batch5b_leaks as leaks
import select_batch5b as selection


@pytest.fixture
def invented_cases():
    return [{'case_id':'case-secretfixture123', 'object_id':'987654321987654321',
             'label':{'z':.123456789},
             'expected_answer':{'case_id':'case-secretfixture123', 'must_abstain':True}}]


def test_exact_ids_and_pairs_but_not_isolated_redshift(invented_cases):
    private = leaks.custody(invented_cases)
    assert leaks.inspect_text('a987654321987654321 9876543219876543210 .123456789', private) == (0,0,0)
    ids, pairs, _ = leaks.inspect_text('"987654321987654321", 0.123456789', private)
    assert ids == pairs == 1
    assert leaks.inspect_text('input_987654321987654321.npz', private)[0] == 1
    assert leaks.inspect_text(json.dumps(invented_cases[0]['expected_answer']), private)[2] == 1


def make_repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    subprocess.run(['git','init','-q',str(root)], check=True)
    (root/'clean.txt').write_text('only a redshift: 0.123456789\n')
    commit(root)
    return root, leaks.git(root,'rev-parse','HEAD').decode().strip()


def commit(root):
    subprocess.run(['git','-C',str(root),'add','.'], check=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=Synthetic Test',
                    '-c','user.email=synthetic@example.invalid','commit','-qm','fixture'], check=True)


def test_cli_detects_tree_diff_and_llm_input_without_echoing_secrets(tmp_path, invented_cases):
    root, base = make_repo(tmp_path)
    private = tmp_path/'private.json'
    private.write_text(json.dumps({'cases':invented_cases}))
    llm = tmp_path/'visible.txt'
    llm.write_text('0.123456789 alone is not a leak')
    command = [sys.executable,str(SCRIPTS/'check_batch5b_leaks.py'),'--private',str(private),
               '--repository',str(root),base,'--llm-input',str(llm)]
    def run(expected):
        result = subprocess.run(command,capture_output=True,text=True,timeout=15)
        assert result.returncode == expected
        assert not result.stderr
        for secret in ['987654321987654321','case-secretfixture123','0.123456789','must_abstain']:
            assert secret not in result.stdout
        return json.loads(result.stdout)
    assert run(0)['violating_surfaces'] == 0
    staged = root/'staged.txt'
    staged.write_text(json.dumps(invented_cases[0]))
    subprocess.run(['git','-C',str(root),'add','staged.txt'],check=True)
    staged.write_text('safe working content')
    assert run(1)['violating_surfaces'] > 0  # staged-only leak
    subprocess.run(['git','-C',str(root),'add','staged.txt'],check=True)
    assert run(0)['violating_surfaces'] == 0
    planted = root/'input_987654321987654321.txt'
    planted.write_text(json.dumps(invented_cases[0]))
    assert run(1)['violating_surfaces'] > 0
    commit(root)
    planted.unlink()
    commit(root)
    assert run(1)['violating_surfaces'] > 0  # intermediate commit retained
    # Explicit prompt/LLM input is reported independently of the branch leak.
    llm.write_text(json.dumps(invented_cases[0]))
    report = run(1)
    assert any(row['path'] == str(llm) for row in report['violations'])


def test_cli_fails_closed_on_missing_input(tmp_path, invented_cases):
    root, base = make_repo(tmp_path)
    private = tmp_path/'private.json'; private.write_text(json.dumps({'cases':invented_cases}))
    result = subprocess.run([sys.executable,str(SCRIPTS/'check_batch5b_leaks.py'),
        '--private',str(private),'--repository',str(root),base,
        '--llm-input',str(tmp_path/'missing')],capture_output=True,text=True,timeout=15)
    assert result.returncode == 2 and json.loads(result.stdout)['errors'] == 1
    assert not result.stderr


def population():
    rows = [{'object_id':f'fake-{i:06d}','z':i/100000.,'zwarn':int(i%3!=0)} for i in range(82200)]
    splits = {'train':{r['object_id'] for r in rows[82000:82100]},
              'validation':{r['object_id'] for r in rows[82100:82195]},
              'test':{r['object_id'] for r in rows[82195:]}}
    return rows,splits


def test_selection_reproducible_disjoint_and_excludes_seen_and_test():
    rows,splits = population()
    excluded = {rows[82000]['object_id'], rows[82100]['object_id']}
    dev,accept,counts = selection.choose(rows,splits,excluded)
    assert selection.encode((dev,accept,counts)) == selection.encode(selection.choose(rows,splits,excluded))
    a={row['object_id'] for row in accept};d={row['object_id'] for row in dev}
    assert len(a)==80 and len(d)==48 and not a&d
    assert not (a|d)&(excluded|splits['test'])
    assert all(row['eligible_position']>=82000 for row in dev+accept)
    assert {row['cnn_exposure'] for row in accept} == {'train','validation'}
    assert not ({row['case_id'] for row in selection.synthetic('development')} &
                {row['case_id'] for row in selection.synthetic('acceptance')})
    with pytest.raises(ValueError,match='insufficient population'):
        selection.choose(rows,splits,set(splits['validation']))


def test_selector_writes_private_only_summary_and_never_overwrites(tmp_path, monkeypatch):
    root,base=make_repo(tmp_path)
    rows,splits=population()
    monkeypatch.setattr(selection,'load_population',lambda *a:(rows,splits,set(),{'synthetic_fixture':True}))
    source=tmp_path/'source.json';source.write_text('{}')
    splitroot=tmp_path/'splits'
    for role,ids in splits.items():
        (splitroot/role).mkdir(parents=True)
        (splitroot/role/'ids.json').write_text(json.dumps(sorted(ids)))
    private=tmp_path/'custody'
    dev=root/'development.json';public=root/'commitment.json'
    argv=['select','--index',str(source),'--historical',str(source),'--labels',str(source),
          '--splits',str(splitroot),'--examples',str(tmp_path),
          '--repository',str(root),base,'--visible',str(source),'--private-dir',str(private),
          '--development',str(dev),'--commitment',str(public)]
    monkeypatch.setattr(sys,'argv',argv)
    output=io.StringIO()
    old_umask=os.umask(0o077)
    try:
        with contextlib.redirect_stdout(output): assert selection.main()==0
        manifest=json.loads((private/'acceptance.json').read_text())
        summary=json.loads(output.getvalue())
        assert set(summary)=={'sha256','bytes','counts'}
        assert summary['counts']['total']==128
        assert summary['sha256']==selection.digest((private/'acceptance.json').read_bytes())
        assert private.stat().st_mode&0o777==0o700
        assert (private/'acceptance.json').stat().st_mode&0o777==0o600
        for row in manifest['cases']:
            assert row['case_id'] not in output.getvalue() and row['case_id'] not in dev.read_text()
        before=(private/'acceptance.json').read_bytes()
        with contextlib.redirect_stdout(io.StringIO()): assert selection.main()==2
        assert (private/'acceptance.json').read_bytes()==before
    finally:
        os.umask(old_umask)


def test_npz_metadata_and_filename_are_checked_without_disclosing_ids(tmp_path, invented_cases):
    import numpy as np
    path=tmp_path/'input.npz'
    np.savez(path,flux=np.ones(8),wavelength=np.arange(8),
             object_id=np.array(invented_cases[0]['object_id']))
    private=leaks.custody(invented_cases)
    report=leaks.scan(private,[],[path])
    assert report['violating_surfaces']>0
    assert invented_cases[0]['object_id'] not in json.dumps(report)
    path2=tmp_path/(invented_cases[0]['case_id']+'.txt')
    path2.write_text('safe content')
    report=leaks.scan(private,[],[path2])
    assert report['violating_surfaces']>0
    assert invented_cases[0]['case_id'] not in json.dumps(report)
