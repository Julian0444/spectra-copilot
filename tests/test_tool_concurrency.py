"""Cold cache and mutable-model serialization across distinct caller threads."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock, get_ident
import time
import numpy as np
from copilot import tools


def test_concurrent_cold_model_load_occurs_once(monkeypatch):
    tools._model.cache_clear()
    barrier=Barrier(4);calls=[]; model=object()
    def load(*a):
        calls.append(get_ident());time.sleep(.02);return model
    monkeypatch.setattr(tools,'load_model_from_checkpoint',load)
    monkeypatch.setenv('DESI_FM_CKPT','synthetic')
    def request(_): barrier.wait(timeout=3);return tools._model()
    try:
        with ThreadPoolExecutor(4) as pool: results=list(pool.map(request,range(4)))
        assert all(r is model for r in results) and len(calls)==1
    finally:tools._model.cache_clear()


def test_model_requests_do_not_overlap_or_mix_results(monkeypatch):
    barrier=Barrier(4);active=0;peak=0;lock=Lock();threads=set()
    monkeypatch.setattr(tools,'_load',lambda p:(np.array([float(p)]),None,None,None))
    monkeypatch.setattr(tools,'_model',lambda:object())
    def predict(**kw):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active);threads.add(get_ident())
        time.sleep(.02)
        value=float(kw['flux'][0])
        with lock:active-=1
        return {'z_pred':value,'coverage':{'request':value},'model_identity':{}}
    monkeypatch.setattr(tools,'predict_spectrum',predict)
    def request(i):barrier.wait(timeout=3);return tools.predict_redshift_impl(str(i))
    with ThreadPoolExecutor(4) as pool:results=list(pool.map(request,range(4)))
    assert len(threads)==4 and peak==1
    assert [r['z_pred'] for r in results]==[0,1,2,3]
    assert [r['coverage']['request'] for r in results]==[0,1,2,3]


def test_faiss_configured_on_every_search_thread(monkeypatch):
    from threading import local
    state=local();barrier=Barrier(3);threads=set()
    class Index:
        ntotal=2
        def search(self,emb,k):
            assert state.threads==1
            threads.add(get_ident())
            return np.ones((1,k)),np.arange(k)[None,:]
    monkeypatch.setattr(tools,'_index',lambda:(Index(),np.array([.2,.8])))
    monkeypatch.setattr(tools,'_load',lambda p:(None,None,None,None))
    monkeypatch.setattr(tools,'_model',lambda:None)
    monkeypatch.setattr(tools,'embed_spectrum',lambda **k:np.array([1.,0.]))
    monkeypatch.setattr(tools,'_faiss',lambda:setattr(state,'threads',1))
    def request(i):barrier.wait(timeout=3);return tools.find_similar_spectra_impl('synthetic',k=1+i%2)
    with ThreadPoolExecutor(3) as pool:results=list(pool.map(request,range(3)))
    assert len(threads)==3 and [r['k'] for r in results]==[1,2,1]


# O-1: observe shared state and per-request results, without requiring a
# decorator, a particular lock, or any real weights/index.
import pytest
from types import SimpleNamespace


@pytest.mark.parametrize('operations', [
    ('predict',) * 4, ('reconstruct',) * 4, ('similar',) * 4,
    ('predict', 'reconstruct', 'similar') * 2,
])
def test_all_shared_operations_serialize_without_response_mixing(monkeypatch, operations):
    barrier = Barrier(len(operations))
    guard = Lock()
    state = SimpleNamespace(active=0, peak=0, value=None)
    threads = set()

    def shared(value):
        with guard:
            state.active += 1
            state.peak = max(state.peak, state.active)
            state.value = value
            threads.add(get_ident())
        time.sleep(.04)  # release the GIL while shared mutable state is live
        observed = state.value
        with guard:
            state.active -= 1
        return observed

    monkeypatch.setattr(tools, '_load', lambda p: (np.array([float(p)]), None, None, None))
    monkeypatch.setattr(tools, '_model', lambda: state)
    def predict(**kw):
        value = shared(float(kw['flux'][0]))
        return {'z_pred': value, 'coverage': {'request': value},
                'model_identity': {}, 'spectrum_mask': np.array([True, False])}
    def embed(**kw):
        value = shared(float(kw['flux'][0]))
        return np.eye(len(operations), dtype=np.float32)[int(value)]
    class Index:
        ntotal = len(operations)
        def search(self, embedding, k):
            value = int(shared(float(np.argmax(embedding))))
            return np.ones((1, k)), np.full((1, k), value)
    monkeypatch.setattr(tools, 'predict_spectrum', predict)
    monkeypatch.setattr(tools, 'embed_spectrum', embed)
    monkeypatch.setattr(tools, '_index', lambda: (Index(), np.arange(len(operations))))
    monkeypatch.setattr(tools, '_faiss', lambda: None)
    def request(pair):
        i, operation = pair
        barrier.wait(timeout=5)
        if operation == 'predict':
            result = tools.predict_redshift_impl(str(i))
            return result['z_pred'], result['coverage']['request']
        if operation == 'reconstruct':
            result = tools.reconstruct_spectrum_impl(str(i), .4)
            assert result['mask_ratio'] == .4 and result['n_tokens_masked'] == 1
            return result['z_pred_under_masking'], result['coverage']['request']
        result = tools.find_similar_spectra_impl(str(i), k=1)
        return result['neighbors'][0]['z'], result['neighbor_z_median']
    with ThreadPoolExecutor(len(operations)) as pool:
        results = list(pool.map(request, enumerate(operations)))
    assert len(threads) == len(operations)
    assert state.peak == 1, 'Shared operations overlapped'
    assert results == [(float(i), float(i)) for i in range(len(operations))]


@pytest.mark.parametrize('resource', ['model', 'index'])
def test_cached_resources_load_once_across_threads(monkeypatch, tmp_path, resource):
    cache = tools._model if resource == 'model' else tools._index
    cache.cache_clear()
    barrier = Barrier(4)
    calls = []
    callers = set()
    guard = Lock()
    def load(*args):
        with guard:
            calls.append(get_ident())
        time.sleep(.05)
        return object()
    if resource == 'model':
        monkeypatch.setenv('DESI_FM_CKPT', 'stub')
        monkeypatch.setattr(tools, 'load_model_from_checkpoint', load)
    else:
        metadata = tmp_path / 'metadata.npz'
        np.savez(metadata, z=np.array([.1, .2]))
        monkeypatch.setattr(tools, '_index_paths', lambda: ('stub', str(metadata)))
        monkeypatch.setattr(tools, '_faiss', lambda: SimpleNamespace(read_index=load))
    def request(_):
        with guard:
            callers.add(get_ident())
        barrier.wait(timeout=5)
        return cache()
    try:
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(request, range(4)))
        assert len(callers) == 4
        assert len(calls) == 1, 'Duplicate concurrent resource loads'
        assert all(result is results[0] for result in results)
        assert cache() is results[0] and len(calls) == 1
    finally:
        cache.cache_clear()
