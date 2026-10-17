"""Actual subprocess, MCP initialization, discovery and all five tools over stdio."""
import asyncio
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest
import torch
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from desi_fm.model import DESIFoundationModel, DESIFoundationModelConfig
from desi_fm.predict import embed_spectrum,predict_spectrum
from copilot import tools


def test_stdio_valid_invalid_and_recovery(tmp_path):
    torch.manual_seed(17)
    model=DESIFoundationModel(DESIFoundationModelConfig(n_pixels=64,n_tokens=8,d_model=16,n_layers=1,n_heads=2,n_z_bins=16,dropout=.4)).eval()
    ckpt=tmp_path/'checkpoint.pt';torch.save(dict(model=model.state_dict(),config=model.config.to_dict()),ckpt)
    w=np.geomspace(3600,9800,64).astype(np.float32);f=np.sin(w/500).astype(np.float32)
    path=tmp_path/'input.npz';np.savez(path,flux=f,wavelength=w)
    bad=tmp_path/'invalid.npz';np.savez(bad,flux=f,wavelength=w,mask=np.ones(64,bool))
    gap=tmp_path/'gap.npz';m=np.zeros(64,bool);m[20:28]=True;np.savez(gap,flux=f,wavelength=w,mask=m)
    nonfinite=tmp_path/'nonfinite.npz';nf=f.copy();nf[20:24]=np.nan;nf[24:28]=np.inf;np.savez(nonfinite,flux=nf,wavelength=w)
    outside=tmp_path/'outside.npz';np.savez(outside,flux=f,wavelength=w+20000)
    emb=embed_spectrum(f,w,model=model);emb/=np.linalg.norm(emb)
    faiss=tools._faiss();index=faiss.IndexFlatIP(emb.size);index.add(np.stack([emb,-emb]).astype(np.float32))
    faiss.write_index(index,str(tmp_path/'spectra.faiss'));np.savez(tmp_path/'spectra_meta.npz',z=np.array([.42,1.]))
    env={k:v for k,v in os.environ.items() if k != 'ANTHROPIC_API_KEY' and not k.startswith(('OMP_', 'KMP_', 'MKL_'))}
    env.update(DESI_FM_CKPT=str(ckpt),DESI_FM_INDEX_DIR=str(tmp_path),HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1')
    transcript=[]
    async def check():
        server=StdioServerParameters(command=sys.executable,args=['-m','copilot.mcp_server'],env=env,cwd=Path(tools.__file__).resolve().parent.parent)
        async with stdio_client(server) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=20) as session:
                initial=await session.initialize();transcript.append({'initialize':initial.model_dump(mode='json')})
                listing=await session.list_tools();transcript.append({'tools':listing.model_dump(mode='json')})
                assert {t.name for t in listing.tools}=={'predict_redshift','reconstruct_spectrum','identify_spectral_lines','find_similar_spectra','lookup_reference'}
                async def call(name,args,valid=True):
                    r=await session.call_tool(name,args)
                    transcript.append({'tool':name,'arguments':args,'result':r.model_dump(mode='json')})
                    assert r.is_error != valid, r.content
                    if valid:return json.loads(r.content[0].text)
                    assert r.content and any(b.text for b in r.content if b.type=='text')
                # Cold concurrent cache loading; distinct inputs/k expose response mixing.
                cold = await asyncio.gather(
                    call('find_similar_spectra', {'npz_path':str(path),'k':1}),
                    call('find_similar_spectra', {'npz_path':str(gap),'k':2}),
                    call('predict_redshift', {'npz_path':str(path)}),
                    call('reconstruct_spectrum', {'npz_path':str(gap),'mask_ratio':0}))
                assert cold[0]['k']==1 and cold[1]['k']==2
                assert cold[0]['neighbors'][0]['similarity'] > .999
                a=await call('predict_redshift',{'npz_path':str(path)})
                assert cold[2]==a
                expected=predict_spectrum(f,w,model=model)
                assert a['z_pred']==pytest.approx(expected['z_pred'],abs=5.1e-5)
                b=await call('predict_redshift',{'npz_path':str(gap)})
                c=await call('predict_redshift',{'npz_path':str(nonfinite)})
                assert b==c
                assert cold[3]['z_pred_under_masking']==b['z_pred_map']
                for _ in range(3):
                    mixed = await asyncio.gather(
                        call('identify_spectral_lines',{'npz_path':str(path),'z':.42}),
                        call('find_similar_spectra',{'npz_path':str(path),'k':1}),
                        call('predict_redshift',{'npz_path':str(gap)}),
                        call('reconstruct_spectrum',{'npz_path':str(path),'mask_ratio':0}),
                        call('lookup_reference',{'query':'Halpha','k':1}))
                    assert mixed[0]['z_tested']==.42
                    assert mixed[1]==cold[0] and mixed[2]==b
                    assert mixed[3]['z_pred_under_masking']==a['z_pred_map']
                    # A sequential search after workers have overlapped.
                    assert await call('find_similar_spectra',{'npz_path':str(path),'k':1})==cold[0]
                    assert await call('predict_redshift',{'npz_path':str(path)})==a
                assert b['coverage']['n_valid_model_pixels']==56
                assert (await call('reconstruct_spectrum',{'npz_path':str(path),'mask_ratio':0}))['z_pred_under_masking']==a['z_pred_map']
                await call('identify_spectral_lines',{'npz_path':str(path),'z':.42})
                neighbor=await call('find_similar_spectra',{'npz_path':str(path),'k':1})
                assert neighbor['neighbors'][0]['similarity']>.999
                assert (await call('lookup_reference',{'query':'Halpha OII confusion','k':3}))['results']
                for name,args in [('predict_redshift',{'npz_path':str(bad)}),
                                  ('predict_redshift',{'npz_path':str(outside)}),
                                  ('find_similar_spectra',{'npz_path':str(bad)}),
                                  ('predict_redshift',{'npz_path':str(tmp_path/'absent.npz')}),
                                  ('identify_spectral_lines',{'npz_path':str(path),'z':-10}),
                                  ('reconstruct_spectrum',{'npz_path':str(path),'mask_ratio':1.5}),
                                  ('reconstruct_spectrum',{'npz_path':str(path),'mask_ratio':True}),
                                  ('find_similar_spectra',{'npz_path':str(path),'k':0}),
                                  ('find_similar_spectra',{'npz_path':str(path),'k':'2'}),
                                  ('lookup_reference',{'query':'DESI','k':1.5})]:
                    await call(name,args,False)
                await call('lookup_reference',{'query':'ELG redshift range'})
                assert await call('predict_redshift',{'npz_path':str(path)})==a
                assert await call('find_similar_spectra',{'npz_path':str(path),'k':1})==cold[0]
                invalid=await session.call_tool('predict_redshift',{'npz_path':str(bad)})
                assert invalid.is_error
                assert invalid.structured_content['error']['code']=='invalid_input'
                assert invalid.structured_content['error']['type']=='SpectrumInputError'
    try:
        asyncio.run(asyncio.wait_for(check(), timeout=60))
    finally:
        (tmp_path/'stdio-transcript.json').write_text(json.dumps(transcript,indent=2,default=str))
    target=os.environ.get('SPECTRA_MCP_TRANSCRIPT')
    if target:Path(target).write_text(json.dumps(transcript,indent=2,allow_nan=False)+'\n')
