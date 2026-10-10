from pathlib import Path
from copilot import tools

REVISION = '40ff2ed09e5e1584303052e1a5dfe218a4a396b3'


def test_remote_downloads_pin_one_revision(monkeypatch, tmp_path):
    import huggingface_hub
    import hashlib
    from desi_fm import assets
    paths = {}
    for filename in assets.ASSETS:
        path = tmp_path/Path(filename).name
        path.write_bytes(filename.encode())
        paths[filename] = path
        monkeypatch.setitem(assets.ASSETS, filename, (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()))
    calls = []
    def download(repo, filename, **kwargs):
        calls.append(kwargs)
        assert kwargs.get('revision') == REVISION
        return str(paths[filename])
    monkeypatch.setattr(huggingface_hub, 'hf_hub_download', download)
    monkeypatch.setenv('DESI_FM_INDEX_DIR', str(tmp_path/'absent'))
    tools._hub_checkpoint()
    tools._index_paths()
    assert len(calls) == 3


def test_corrupt_remote_asset_rejected(monkeypatch, tmp_path):
    import huggingface_hub
    import pytest
    bad = tmp_path/'bad.pt'
    bad.write_bytes(b'wrong checkpoint')
    monkeypatch.setattr(huggingface_hub, 'hf_hub_download', lambda *a, **k: str(bad))
    with pytest.raises(ValueError, match='identity'):
        tools._hub_checkpoint()
