"""Input/server error boundary: no real weights and no network, including stdio."""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys

import numpy as np
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from copilot import mcp_server, tools


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    from huggingface_hub import constants
    attempts = []
    def blocked(*args, **kwargs):
        attempts.append(1)
        raise AssertionError('Network forbidden in asset regressions')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    monkeypatch.setattr(constants, 'HF_HUB_OFFLINE', True)
    monkeypatch.setattr(constants, 'HF_HUB_CACHE', str(tmp_path / 'empty-hub'))
    model_cache, index_cache = tools._model, tools._index
    model_cache.cache_clear()
    index_cache.cache_clear()
    yield
    model_cache.cache_clear()
    index_cache.cache_clear()
    assert attempts == []


@pytest.fixture
def spectrum(tmp_path):
    path = tmp_path / 'input.npz'
    np.savez(path, flux=np.ones(64), wavelength=np.geomspace(3600, 9800, 64))
    return str(path)


def assert_error(result, code):
    assert result.is_error
    assert result.structured_content['error']['code'] == code
    assert json.loads(result.content[0].text) == result.structured_content
    payload = json.dumps(result.model_dump(mode='json'))
    assert '/Users/' not in payload and 'Traceback' not in payload
    assert 'sensitive-marker' not in payload


@pytest.mark.parametrize('name', ['predict_redshift', 'reconstruct_spectrum', 'find_similar_spectra'])
def test_missing_input_is_input_error(name, tmp_path):
    assert_error(getattr(mcp_server, name)(str(tmp_path / 'missing.npz')), 'invalid_input')


@pytest.mark.parametrize('name', ['predict_redshift', 'reconstruct_spectrum'])
def test_missing_checkpoint_is_server_error(name, spectrum, monkeypatch, tmp_path):
    monkeypatch.setenv('DESI_FM_CKPT', str(tmp_path / 'sensitive-marker-missing.pt'))
    assert_error(getattr(mcp_server, name)(spectrum), 'internal_error')


def test_missing_index_offline_is_server_error(spectrum, monkeypatch, tmp_path):
    monkeypatch.setenv('DESI_FM_INDEX_DIR', str(tmp_path / 'absent-index'))
    monkeypatch.setattr(tools, '_model', lambda: object())
    monkeypatch.setattr(tools, 'embed_spectrum', lambda **kw: np.array([1., 0.]))
    assert_error(mcp_server.find_similar_spectra(spectrum), 'internal_error')


def test_no_checkpoint_empty_offline_cache_is_server_error(spectrum, monkeypatch):
    monkeypatch.delenv('DESI_FM_CKPT', raising=False)
    assert_error(mcp_server.predict_redshift(spectrum), 'internal_error')


@pytest.mark.parametrize('failure', [PermissionError, ValueError, RuntimeError, KeyError])
def test_internal_failures_are_safe_and_recover(failure, spectrum, monkeypatch):
    def fail(*args):
        raise failure('/Users/private/sensitive-marker token=secret')
    with monkeypatch.context() as patch:
        patch.setattr(tools, 'load_model_from_checkpoint', fail)
        patch.setenv('DESI_FM_CKPT', 'stub')
        assert_error(mcp_server.predict_redshift(spectrum), 'internal_error')
    monkeypatch.setenv('DESI_FM_CKPT', 'stub')
    monkeypatch.setattr(tools, 'load_model_from_checkpoint', lambda *a: object())
    monkeypatch.setattr(tools, 'predict_spectrum', lambda **kw: {
        'z_pred': .25, 'coverage': {'n_valid_model_pixels': 64}, 'model_identity': {}})
    assert mcp_server.predict_redshift(spectrum)['z_pred'] == .25


def test_asset_failure_and_recovery_over_real_stdio(spectrum, tmp_path):
    # Child uses the real MCP server and real path resolution. Only computation
    # and the weight decoder are stubbed; opening the missing asset is real I/O.
    launcher = tmp_path / 'server.py'
    launcher.write_text('''import socket
import os
from pathlib import Path
import numpy as np
from copilot import tools
from copilot.mcp_server import mcp
def blocked(*a, **k):
    Path(os.environ["NETWORK_ATTEMPTS"]).write_text("attempt")
    raise AssertionError("Network forbidden")
socket.socket.connect = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
def load(path, device):
    with open(path, "rb") as stream: assert stream.read() == b"stub"
    return object()
tools.load_model_from_checkpoint = load
tools.predict_spectrum = lambda **kw: {"z_pred": .25, "coverage": {}, "model_identity": {}}
mcp.run()
''')
    checkpoint = tmp_path / 'sensitive-marker.pt'
    env = {k: v for k, v in os.environ.items() if 'KEY' not in k and 'TOKEN' not in k}
    env.update(DESI_FM_CKPT=str(checkpoint), HF_HUB_OFFLINE='1',
               HF_HOME=str(tmp_path / 'empty-cache'), NETWORK_ATTEMPTS=str(tmp_path / 'network-attempts'))
    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(launcher)], env=env)
        with (tmp_path / 'server-stderr.log').open('w') as stderr:
            async with stdio_client(params, errlog=stderr) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=10) as session:
                    await session.initialize()
                    assert_error(await session.call_tool('predict_redshift', {'npz_path': spectrum}), 'internal_error')
                    assert_error(await session.call_tool('predict_redshift', {'npz_path': str(tmp_path / 'missing.npz')}), 'invalid_input')
                    checkpoint.write_bytes(b'stub')
                    recovered = await session.call_tool('predict_redshift', {'npz_path': spectrum})
                    assert not recovered.is_error
                    assert json.loads(recovered.content[0].text)['z_pred'] == .25
                    # MCP/Pydantic still rejects schema errors before the tool.
                    invalid = await session.call_tool('find_similar_spectra', {'npz_path': spectrum, 'k': 'two'})
                    assert invalid.is_error
    asyncio.run(asyncio.wait_for(run(), timeout=25))
    assert not (tmp_path / 'network-attempts').exists()
    diagnostics = [json.loads(line) for line in (tmp_path/'server-stderr.log').read_text().splitlines()
                   if line.startswith('{"event": "internal_error"')]
    assert diagnostics == [{'event': 'internal_error', 'exception_type': 'FileNotFoundError'}]



def test_internal_diagnostic_is_exception_type_only_on_stderr(capsys):
    def fail():
        raise RuntimeError('/Users/private/sensitive-marker token=secret')
    assert_error(mcp_server._invoke(fail), 'internal_error')
    captured = capsys.readouterr()
    assert captured.out == ''
    assert json.loads(captured.err) == {'event': 'internal_error', 'exception_type': 'RuntimeError'}
    assert '/Users/' not in captured.err and 'sensitive-marker' not in captured.err
    assert 'token=secret' not in captured.err and 'Traceback' not in captured.err
    assert mcp_server._invoke(lambda: {'ok': True}) == {'ok': True}
    assert capsys.readouterr().err == ''
