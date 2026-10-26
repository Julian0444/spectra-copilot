"""Small installed-wheel demo: development input, rejection, ambiguity and MCP."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from copilot import tools
from copilot.acceptance_io import sha256
from copilot.campaign import exclusive_json
from copilot.candidate_identity import installed_evidence
from desi_fm.inputs import SpectrumInputError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('valid','invalid','ambiguous','build-manifest','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if not sys.flags.isolated or os.environ.get('PYTHONPATH'):
        raise ValueError('Use the installed interpreter with -I and no PYTHONPATH')
    if args.output.exists():raise FileExistsError('Choose a new demo output')
    installation=installed_evidence(args.build_manifest)
    prediction=tools.predict_redshift_impl(str(args.valid));z=tools.official_z(prediction)
    try:tools.predict_redshift_impl(str(args.invalid))
    except SpectrumInputError:rejected=True
    else:raise AssertionError('Invalid input was accepted')
    lines=tools.identify_spectral_lines_impl(str(args.ambiguous),z)
    assert lines['ambiguous'] and lines['assessment']=='ambiguous'
    async def mcp_call():
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        env={k:v for k,v in os.environ.items() if not k.startswith('PYTHON') and not k.endswith(('API_KEY','AUTH_TOKEN'))}
        server=StdioServerParameters(command=sys.executable,args=['-I','-B','-m','copilot.mcp_server'],env=env)
        async with stdio_client(server) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=30) as session:
                await session.initialize()
                response=await session.call_tool('lookup_reference',{'query':'Halpha OII confusion'})
                assert not response.is_error
                return response.model_dump(mode='json')
    evidence={'schema':'batch5c-development-demo-v1','installation':installation,
        'script_sha256':sha256(__file__),'inputs':{k:sha256(getattr(args,k)) for k in ('valid','invalid','ambiguous')},
        'module_file':tools.__file__,'official_model_z':z,'invalid_rejected':rejected,
        'single_line_assessment':lines['assessment'],'candidate_count':len(lines['candidates']),
        'mcp':asyncio.run(mcp_call()),'paid_calls':0,'acceptance_opened':False}
    exclusive_json(args.output,evidence)
    print(json.dumps({k:evidence[k] for k in ('official_model_z','invalid_rejected','single_line_assessment','paid_calls')}))


if __name__=='__main__':main()
