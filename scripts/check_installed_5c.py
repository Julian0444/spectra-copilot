"""Verify installed 5C wheels using development only, without paid inference.

Run with the clean venv's python -I, from a directory outside both checkouts.
All paths are explicit; no downloads or training occur.
"""
import argparse
import asyncio
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import copilot
import desi_fm
from copilot import tools,rag,explanation
from copilot.acceptance_io import sha256,write_json,sanitize
from copilot.candidate_identity import installed_evidence,capture
from desi_fm.inputs import read_npz,SpectrumInputError


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('development','build-manifest','protocol-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    assert not os.environ.get('PYTHONPATH') and not os.environ.get('ANTHROPIC_API_KEY')
    imports={name:module.__file__ for name,module in [('copilot',copilot),('desi_fm',desi_fm),('tools',tools),('rag',rag)]}
    assert all('site-packages' in path for path in imports.values())
    build=installed_evidence(a.build_manifest)
    selection=json.loads((a.development/'development-scoring.json').read_text())['cases']
    inputs=json.loads((a.development/'pilot-inputs.json').read_text())['inputs']
    valid=Path(inputs[0]['input_path'])
    invalid=Path(next(i['input_path'] for i,c in zip(inputs,selection) if c['expected_answer']['must_reject_input']))
    single=Path(next(i['input_path'] for i,c in zip(inputs,selection) if c.get('family')=='single_line'))
    resources=rag.corpus_hashes();assert len(resources)==16
    prediction=tools.predict_redshift_impl(str(valid));z=tools.official_z(prediction)
    lines=tools.identify_spectral_lines_impl(str(valid),z)
    ambiguous=tools.identify_spectral_lines_impl(str(single),z)
    assert prediction['model_identity']['checkpoint']['sha256']=='40247cbe0e706a66084d001b36424081554c26d3eb75c1f8b0ebec89cf5afe5a'
    try:tools.predict_redshift_impl(str(invalid));raise AssertionError('Invalid support accepted')
    except SpectrumInputError:pass
    env={k:v for k,v in os.environ.items() if not k.startswith('PYTHON') and not k.endswith(('API_KEY','AUTH_TOKEN'))}
    cli=[]
    for args in [['-m','copilot',str(valid)],['-m','desi_fm.predict','--checkpoint',os.environ['DESI_FM_CKPT'],
                 '--input',str(valid),'--output',str(a.output/'fm-cli.npz')]]:
        result=subprocess.run([sys.executable,'-I','-B',*args],cwd=a.output,env=env,capture_output=True,text=True,timeout=60)
        cli.append({'args':args,'returncode':result.returncode});assert result.returncode==0,result.stderr
        write_json(a.output/('copilot-cli.json' if args[1]=='copilot' else 'fm-cli.json'),json.loads(result.stdout))
    from fastapi.testclient import TestClient
    from desi_fm.api import app
    with TestClient(app) as client:
        assert client.get('/healthz').status_code==200
        r=client.post('/predict',files={'file':('spectrum.npz',valid.read_bytes(),'application/octet-stream')})
        assert r.status_code==200,r.text
        api=r.json();assert abs(api['z_pred_map'][0]-z)<.000051
        assert client.post('/predict',files={'file':('invalid.npz',invalid.read_bytes())}).status_code==422
        f,w,v,m=read_npz(valid).single()
        j=client.post('/predict_json',json={k:value.tolist() for k,value in zip(('flux','wavelength','ivar','mask'),(f,w,v,m))})
        assert j.status_code==200 and abs(j.json()['z_pred_map']-z)<.000051
        assert client.get('/openapi.json').json()['info']['version']==metadata.version('desi-fm')
    transcript=[]
    async def stdio():
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        server=StdioServerParameters(command=sys.executable,args=['-I','-B','-m','copilot.mcp_server'],env=env,cwd=a.output)
        async with stdio_client(server) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=60) as session:
                await session.initialize();listing=await session.list_tools();assert len(listing.tools)==5
                calls=[('predict_redshift',{'npz_path':str(valid)}),('identify_spectral_lines',{'npz_path':str(single),'z':z}),
                       ('reconstruct_spectrum',{'npz_path':str(valid),'mask_ratio':0}),('find_similar_spectra',{'npz_path':str(valid),'k':1}),
                       ('lookup_reference',{'query':'Halpha OII confusion'})]
                for name,args in calls:
                    r=await session.call_tool(name,args);assert not r.is_error,r.content
                    transcript.append({'tool':name,'valid':True,'result':r.model_dump(mode='json')})
                for name,args,code in [('predict_redshift',{'npz_path':str(invalid)},'invalid_input'),
                    ('find_similar_spectra',{'npz_path':str(invalid)},'invalid_input')]:
                    r=await session.call_tool(name,args);assert r.is_error
                    assert r.structured_content['error']['code']==code
                    transcript.append({'tool':name,'valid':False,'error':r.structured_content})
                r=await session.call_tool('reconstruct_spectrum',{'npz_path':str(valid),'mask_ratio':2})
                assert r.is_error
                assert not (await session.call_tool('lookup_reference',{'query':'DESI'})).is_error
    asyncio.run(stdio())
    from desi_fm.demo import analyze,build_demo
    text,figure=analyze(str(valid),0);assert f'model_z = {z:.4f}' in text
    figure.savefig(a.output/'development-demo.png',dpi=140)
    interface=build_demo();assert interface.config['components']
    write_json(a.output/'gradio-config.json',sanitize(interface.config))
    for effort in ('low','medium'):
        start=time.monotonic();value=capture(a.protocol_dir,effort,kind='installed-5c',build_manifest=a.build_manifest)
        write_json(a.output/f'identity-{effort}.json',value)
        write_json(a.output/f'identity-{effort}.timing.json',{'seconds':time.monotonic()-start})
    report={'imports':imports,'cwd':str(Path.cwd()),'build':build,'versions':{d.metadata['Name']:d.version for d in metadata.distributions()},
            'resources':resources,'input_sha256':sha256(valid),'invalid_sha256':sha256(invalid),'model_z':z,
            'cli':cli,'api':'upload+JSON+422+metadata passed','mcp':'five valid tools, typed invalid inputs, schema failure, recovery',
            'gradio':'installed callback and interface construction passed; browser/server flow separate',
            'paid_calls':0,'acceptance_read':False}
    write_json(a.output/'verification.json',report);write_json(a.output/'stdio.json',sanitize(transcript))
    write_json(a.output/'development-results.json',sanitize({'prediction':prediction,'lines':lines,'single_line':ambiguous}))
    print(json.dumps({'imports':imports,'model_z':z,'checks':'passed','output':str(a.output)}))


if __name__=='__main__':main()
