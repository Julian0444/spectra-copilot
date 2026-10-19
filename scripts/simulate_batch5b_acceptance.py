"""Persist an invented 5C runner rehearsal, never the private acceptance list."""
import argparse
from pathlib import Path
import uuid

import numpy as np
from copilot import explanation
from copilot.acceptance import SCHEMA,execute_plan
from copilot.acceptance_score import score_sealed
from copilot.acceptance_io import sha256,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    items=[];labels=[]
    for i in range(4):
        source=a.output/f'fixture_{i}.npz';wave=np.linspace(3600.,9800.,64)
        np.savez(source,flux=np.sin(wave/500),wavelength=wave,ivar=np.ones(64),mask=np.zeros(64,bool))
        alias=uuid.uuid4().hex[:24]
        items.append({'alias':alias,'input_path':str(source),'input_sha256':sha256(source)})
        labels.append({'alias':alias,'kind':'synthetic','family':'invented-noise-control',
            'cnn_exposure':'none_synthetic','expected_answer':{'model_z_rule':'equal_to_predict_tool_if_available','must_abstain_unique_z':True,'must_reject_input':False}})
    write_json(a.output/'inputs.json',{'schema':SCHEMA,'mode':'simulation','inputs':items})
    write_json(a.output/'scoring.json',{'schema':'batch5c-scoring-v1','cases':labels})
    calls=[]
    def runner(path):
        calls.append(path)
        if len(calls)==3:raise KeyboardInterrupt
        pred={'z_pred_map':.42,'z_pred':.43,'model_identity':{'predictor':'invented-fixture'},'coverage':{'contract':'invented-fixture'}}
        obs={'id':'obs-1','tool':'predict_redshift','arguments':{'npz_path':'spectrum.npz'},'result':pred}
        report=explanation.result(pred,[obs],['obs-1'],assessment='insufficient_data')
        report['execution_budget']={'calls':1,'usd':.00002,'known_usd':.00002,'reserved_usd':0,'cost_certified':True}
        return report
    summary=execute_plan(a.output/'inputs.json',a.output/'execution',runner=runner)
    scored=score_sealed(a.output/'execution',a.output/'scoring.json')
    result={'mode':'invented offline simulation','remote_calls':0,'real_paid_usd':0,
            'requested':4,'completed':2,'interrupted':1,'pending':1,'preserved_model_z':scored['global']['model_z'],
            'labels_after_seal':scored['seal_verified_before_label_read'],'summary':summary,
            'scope':'Contract/persistence rehearsal only; no real LLM, actual acceptance cases or semantic acceptance.'}
    assert summary['attempted']==3 and summary['status_counts']['pending']==1
    write_json(a.output/'rehearsal.json',result)
    print('Offline rehearsal persisted: 4 requested, 2 completed, 1 interrupted, 1 pending; zero remote calls.')


if __name__=='__main__':main()
