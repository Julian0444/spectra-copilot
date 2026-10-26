"""Exercise the installed local Gradio server via its real upload/predict API."""
import argparse
import json
from pathlib import Path
import socket

import desi_fm
from desi_fm.demo import build_demo
from gradio_client import Client,handle_file
from gradio_client.exceptions import AppError


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--valid',required=True);p.add_argument('--invalid',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--build-manifest',type=Path,required=True);a=p.parse_args()
    from copilot.candidate_identity import installed_evidence
    installation=installed_evidence(a.build_manifest)
    assert 'site-packages' in desi_fm.__file__
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    demo=build_demo()
    try:
        _,url,_=demo.launch(server_name='127.0.0.1',server_port=port,share=False,prevent_thread_lock=True,quiet=True)
        client=Client(url,verbose=False)
        info=client.view_api(return_format='dict',print_info=False)
        endpoint=next(k for k in info['named_endpoints'] if 'callback' in k)
        text,plot=client.predict(handle_file(a.valid),0.,api_name=endpoint)
        assert 'model_z' in text and plot
        masked_text,masked_plot=client.predict(handle_file(a.valid),.35,api_name=endpoint)
        assert 'model_z' in masked_text and masked_plot
        try:client.predict(handle_file(a.invalid),0.,api_name=endpoint);raise AssertionError('Invalid accepted')
        except AppError:pass
        a.output.write_text(json.dumps({'module_file':desi_fm.__file__,'api_name':endpoint,'installation':installation,
            'upload_and_predict':True,'masked_reconstruction':True,'invalid_rejected':True,
            'local_only':True,'share':False,'text':text},indent=2)+'\n')
        print(json.dumps({'passed':True,'module_file':desi_fm.__file__,'api_name':endpoint}))
    finally:demo.close()


if __name__=='__main__':main()
