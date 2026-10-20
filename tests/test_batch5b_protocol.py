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
    assert leaks.inspect_text('0987654321987654321 9876543219876543210 .123456789', private) == (0,0,0)
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
    path2=tmp_path/(invented_cases[0]['case_id']+'_z0.123456789.txt')
    path2.write_text('safe content')
    report=leaks.scan(private,[],[path2])
    assert report['violating_surfaces']>0
    assert invented_cases[0]['case_id'] not in json.dumps(report)
    assert '0.123456789' not in json.dumps(report)


@pytest.fixture
def custody_cli(tmp_path, invented_cases):
    """Run the real CLI; fixtures are invented and never use actual custody."""
    invented_cases.append({'case_id': 'case-abcdef0123456789abcdef0123',
                           'object_id': '876543219876543219', 'label': {'z': .234567891}})
    root, base = make_repo(tmp_path)
    private = tmp_path/'private.json'
    private.write_text(json.dumps({'cases': invented_cases}))
    visible = tmp_path/'visible.txt'
    visible.write_text('safe')
    command = [sys.executable, str(SCRIPTS/'check_batch5b_leaks.py'), '--private', str(private),
               '--repository', str(root), base, '--llm-input', str(visible)]
    def run(expected):
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        assert result.returncode == expected
        for case in invented_cases:
            for value in [case['case_id'], case['object_id'], str(case['label']['z'])]:
                assert value not in result.stdout and value not in result.stderr
        assert not result.stderr
        return json.loads(result.stdout)
    return root, visible, run


@pytest.mark.parametrize('surface', ['hyphen_filename', 'hyphen_content', 'mixed_filename',
                                     'case_suffix', 'route_separator'], ids=str)
def test_cli_punctuation_boundaries_and_complete_redaction(custody_cli, surface):
    root, visible, run = custody_cli
    if surface == 'hyphen_filename':
        (root/'input-987654321987654321.txt').write_text('safe')
    elif surface == 'hyphen_content':
        visible.write_text('obj-987654321987654321')
    elif surface == 'mixed_filename':
        (root/'x_987654321987654321_obj-876543219876543219_z0.234567891.txt').write_text('safe')
    elif surface == 'case_suffix':
        visible.write_text('case-abcdef0123456789abcdef0123-debug')
    else:
        (root/'987654321987654321').mkdir()
        (root/'987654321987654321'/'input.txt').write_text('safe')
    assert run(1)['violating_surfaces'] > 0


def test_cli_does_not_match_case_substrings_longer_numbers_or_redshift(custody_cli):
    _, visible, run = custody_cli
    visible.write_text('9876543219876543210 '
                      '0987654321987654321 xcase-abcdef0123456789abcdef0123 '
                      'case-abcdef0123456789abcdef0123f 0.123456789')
    assert run(0)['violating_surfaces'] == 0


@pytest.mark.parametrize('surface', ['working', 'index', 'history'], ids=str)
def test_cli_reads_npz_metadata_in_every_git_surface(custody_cli, surface):
    import numpy as np
    root, _, run = custody_cli
    path = root/'sample.npz'
    np.savez_compressed(path, flux=np.ones(4), object_id=np.array('987654321987654321'))
    if surface == 'index':
        leaks.git(root, 'add', 'sample.npz')
        np.savez_compressed(path, flux=np.ones(4), object_id=np.array('safe'))
    elif surface == 'history':
        commit(root)
        path.unlink()
        commit(root)
    assert run(1)['violating_surfaces'] > 0


def test_cli_reads_empty_commit_message(custody_cli):
    root, _, run = custody_cli
    leaks.git(root, '-c', 'user.name=Synthetic Test', '-c', 'user.email=synthetic@example.invalid',
              'commit', '--allow-empty', '-m', 'obj-987654321987654321')
    assert run(1)['violating_surfaces'] > 0


@pytest.mark.parametrize('surface', ['index', 'history'], ids=str)
def test_cli_fails_closed_on_unreadable_npz_blob(custody_cli, surface):
    root, _, run = custody_cli
    path = root/'broken.npz'
    path.write_bytes(b'not a valid numpy archive')
    if surface == 'index':
        leaks.git(root, 'add', 'broken.npz')
        import numpy as np
        np.savez(path, flux=np.ones(4))
    else:
        commit(root)
        path.unlink()
        commit(root)
    assert run(2)['errors'] == 1


@pytest.mark.parametrize('source', [
    "selection.synthetic('acceptance')",
    'selection.synthetic(role="acceptance")',
    "from select_batch5b import synthetic as build\nbuild('acceptance')",
    "role = 'acceptance'\nselection.synthetic(role)",
    "selection.synthetic('accept' + 'ance')",
    "getattr(selection, 'synthetic')('acceptance')",
], ids=['direct', 'keyword', 'alias', 'role_variable', 'concatenation', 'getattr'])
def test_cli_rejects_public_acceptance_generator_reference(custody_cli, source):
    root, _, run = custody_cli
    (root/'consumer.py').write_text(source)
    assert run(1)['violating_surfaces'] > 0


def test_cli_accepts_only_exact_allowed_generator_paths(custody_cli):
    root, _, run = custody_cli
    (root/'consumer.py').write_text("import json\njson.loads('{}')\nif args.synthetic: pass")
    (root/'scripts').mkdir(); (root/'tests').mkdir()
    for name in ['scripts/select_batch5b.py', 'tests/test_batch5b_protocol.py']:
        (root/name).write_text("selection.synthetic('acceptance')")
    assert run(0)['violating_surfaces'] == 0
    (root/'other').mkdir()
    (root/'other'/'select_batch5b.py').write_text("selection.synthetic('acceptance')")
    assert run(1)['violating_surfaces'] > 0


@pytest.mark.parametrize('source', [
    "import select_batch5b as s\nfor role in ['development', 'acceptance']:\n s.synthetic(role)",
    "from select_batch5b import synthetic\nx = [synthetic(r) for r in ['development', 'acceptance']]",
    "import pytest\nfrom select_batch5b import synthetic\n@pytest.mark.parametrize('role', ['development', 'acceptance'])\ndef test_x(role): synthetic(role)",
    "from scripts import select_batch5b as s\na, b = ('development', 'acceptance')\ns.synthetic(b)",
    "import select_batch5b as s\ns.synthetic({'role': 'acceptance'}['role'])",
    "import select_batch5b as s",  # unused imports are also forbidden
    "selection.synthetic('development')",
    "from select_batch5b import choose",  # any selector access, not just synthetic
], ids=['for_roles', 'comprehension', 'parametrize', 'tuple', 'dict', 'import_only',
        'development', 'other_function'])
def test_cli_rejects_any_selector_access_outside_allowed_paths(custody_cli, source):
    root, _, run = custody_cli
    (root/'consumer.py').write_text(source)
    assert run(1)['violating_surfaces'] > 0


@pytest.mark.parametrize('surface', ['content', 'filename', 'index', 'history'])
def test_cli_numeric_id_digit_boundaries(custody_cli, surface):
    root, visible, run = custody_cli
    if surface == 'content':
        visible.write_text('obj987654321987654321suffix')
    else:
        path = root/'obj987654321987654321.txt'
        path.write_text('safe')
        if surface == 'index':
            path.unlink()
            path = root/'sample.txt'
            path.write_text('obj987654321987654321suffix')
            leaks.git(root, 'add', path.name)
            path.write_text('safe')
        elif surface == 'history':
            commit(root)
            path.unlink()
            commit(root)
    assert run(1)['violating_surfaces'] > 0


def test_selector_import_is_independent_of_mutable_detector():
    code = '''import builtins, runpy, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == "check_batch5b_leaks": raise ImportError("mutable detector forbidden")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
module = runpy.run_path(sys.argv[1])
assert module["TOKEN"].findall("obj-123_456") == ["obj-123", "456"]
'''
    result = subprocess.run([sys.executable, '-c', code, str(SCRIPTS/'select_batch5b.py')],
                            capture_output=True, timeout=15)
    assert result.returncode == 0


@pytest.mark.parametrize('source',[
    "import subprocess\nsubprocess.run(['python', 'scripts/select_batch5b.py'])",
    "from subprocess import Popen\nPopen('python scripts/select_batch5b.py', shell=True)",
    "import subprocess as sp\ncommand=['python', 'scripts/select_batch5b.py']\nsp.check_call(command)",
    "from subprocess import run as launch\nscript='scripts/select_batch5b.py'\nlaunch(['python',script])",
    "exec(open('scripts/select_batch5b.py').read())",
    "from pathlib import Path\npath=Path('scripts/select_batch5b.py')\nsource=path.read_text()\nexec(source)",
    "import os\nos.system('python scripts/select_batch5b.py')",
],ids=['run','popen','command_variable','function_alias','exec_open','exec_path','system'])
def test_cli_rejects_selector_execution_outside_allowed_paths(custody_cli,source):
    root,_,run=custody_cli
    (root/'consumer.py').write_text(source)
    assert run(1)['violating_surfaces']>0
