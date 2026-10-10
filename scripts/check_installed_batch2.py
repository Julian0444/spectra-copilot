"""Wheel acceptance outside checkouts, without PYTHONPATH or editable installs."""
import argparse
import asyncio
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import sys
import zipfile
import copilot
import desi_fm
from copilot import rag
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fm-root',type=Path,required=True)
    p.add_argument('--copilot-root',type=Path,required=True)
    p.add_argument('--wheels',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert not os.environ.get('PYTHONPATH')
    imports={'desi_fm':desi_fm.__file__,'copilot':copilot.__file__,'rag':rag.__file__}
    assert all('site-packages' in v for v in imports.values())
    assert Path.cwd() not in (a.fm_root,a.copilot_root)
    for name in ('desi-fm','spectra-copilot'):
        assert metadata.version(name)=='0.2.0'
        direct=json.loads(metadata.distribution(name).read_text('direct_url.json'))
        assert not direct.get('dir_info',{}).get('editable')
    for source,installed in [(a.fm_root/'src/desi_fm',Path(desi_fm.__file__).parent),
                             (a.copilot_root/'copilot',Path(copilot.__file__).parent)]:
        for f in source.glob('*.py'):assert digest(f)==digest(installed/f.name)
    query=rag.lookup_reference_impl('Halpha OII confusion')
    assert any(r['id']=='line-degeneracy-single-line' for r in query['results'])
    with zipfile.ZipFile(a.wheels/'spectra_copilot-0.2.0-py3-none-any.whl') as z:
        resources=[n for n in z.namelist() if n.startswith('copilot/refs/')];assert len(resources)==16
    spec=importlib.util.spec_from_file_location('evaluator',a.copilot_root/'eval/run_evals.py')
    e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
    identity=e.run_identity(['case_000'],{'case_000':.2036},a.copilot_root/'eval/cases',False,'simulated')
    assert all(identity['assets_sha256'][k]==v for k,v in rag.corpus_hashes().items())
    transcript=[]
    async def stdio():
        env={k:v for k,v in os.environ.items() if k not in {'ANTHROPIC_API_KEY','PYTHONPATH'}}
        server=StdioServerParameters(command=sys.executable,args=['-m','copilot.mcp_server'],env=env,cwd=Path.cwd())
        async with stdio_client(server) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=30) as session:
                init=await session.initialize();listing=await session.list_tools()
                transcript.extend([{'initialize':init.model_dump(mode='json')},{'tools':listing.model_dump(mode='json')}])
                assert len(listing.tools)==5
                path=str(a.copilot_root/'eval/inputs-v2/spectrum_0001.npz')
                async def call(name,args,error=False):
                    r=await session.call_tool(name,args);assert r.is_error==error,r.content
                    transcript.append({'tool':name,'arguments':args,'result':r.model_dump(mode='json')})
                    return None if error else json.loads(r.content[0].text)
                prediction=await call('predict_redshift',{'npz_path':path})
                assert prediction['model_identity']['checkpoint']['sha256']=='40247cbe0e706a66084d001b36424081554c26d3eb75c1f8b0ebec89cf5afe5a'
                assert prediction['z_pred_map']==.2267
                await call('identify_spectral_lines',{'npz_path':path,'z':prediction['z_pred_map']})
                masked=await call('reconstruct_spectrum',{'npz_path':path,'mask_ratio':0})
                assert masked['z_pred_under_masking']==prediction['z_pred_map']
                await call('find_similar_spectra',{'npz_path':path,'k':1})
                await call('lookup_reference',{'query':'Halpha OII confusion'})
                await call('reconstruct_spectrum',{'npz_path':path,'mask_ratio':1.5},True)
                await call('predict_redshift',{'npz_path':'/nonexistent/spectrum.npz'},True)
                await call('lookup_reference',{'query':'ELG redshift range'})
    asyncio.run(stdio())
    report={'cwd':str(Path.cwd()),'python':sys.version,'imports':imports,'editable':False,'PYTHONPATH':None,
            'source_bytes_match_installed':True,'resource_count':len(resources),
            'corpus_revision':rag.corpus_revision(),'corpus_sha256':rag.corpus_hashes(),'query':query,
            'run_identity_resource_check':'passed','stdio':'all five valid tools, invalid arguments/file, recovery',
            'versions':{d.metadata['Name']:d.version for d in metadata.distributions()},
            'wheels':{w.name:digest(w) for w in a.wheels.glob('*.whl')}}
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    a.output.with_suffix('.stdio.json').write_text(json.dumps(transcript,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('imports','resource_count','corpus_revision','source_bytes_match_installed','stdio','wheels')},indent=2))

if __name__=='__main__':main()
