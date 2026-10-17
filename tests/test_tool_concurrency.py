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
