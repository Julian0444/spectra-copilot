"""Frozen development inputs only. No selector imports or private custody access."""
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np

DEVELOPMENT_SHA = '60b2b4584e5a57030a4ff82a1b13d23065505a4d8bb878a20f5d4caecbe3f7c4'
EMISSION = (1215.7, 1549.1, 1908.7, 2798.8, 3727.1, 4861.3, 4958.9, 5006.8, 6562.8)
ABSORPTION = (3933.7, 3968.5)
SINGLE = (1215.7, 3727.1, 5006.8, 6562.8)


def read_development(path):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != DEVELOPMENT_SHA:
        raise ValueError('Only the frozen development manifest is authorized')
    cases = json.loads(data)['cases']
    if len(cases) != 96 or sum(c['kind'] == 'real' for c in cases) != 48:
        raise ValueError('Unexpected development population')
    return cases


def render_recipe(case):
    """Implement §3 of the frozen protocol, never derive recipes from roles."""
    recipe, family = case['recipe'], case['family']
    wave = np.linspace(3600., 9800., 2048)
    rng = np.random.Generator(np.random.PCG64(recipe['seed']))
    flux = 1 + .05*np.sin(wave/700) + rng.normal(0, 1, len(wave))
    ivar, mask = np.ones(len(wave)), np.zeros(len(wave), dtype=bool)
    injected = []
    if family == 'single_line':
        injected = [recipe['peak_angstrom']]
    elif family not in {'noise', 'invalid_support'}:
        rests = ABSORPTION if family == 'absorption' else EMISSION
        injected = [rest*(1+recipe['z']) for rest in rests if 3600 <= rest*(1+recipe['z']) <= 9800]
    sign = -1 if family == 'absorption' else 1
    for center in injected:
        flux += sign*recipe['snr']*np.exp(-.5*((wave-center)/5)**2)
    replica = [0, 2, 5, 10, 20, 50].index(recipe['snr'])
    if family == 'coverage_gap':
        gap = ((wave >= 5000) & (wave <= 6000)) | ((wave >= 7000) & (wave <= 7500))
        if replica % 3 == 0:
            mask[gap] = True
        elif replica % 3 == 1:
            ivar[gap] = 0
        else:
            flux, wave, ivar, mask = (x[~gap] for x in (flux, wave, ivar, mask))
    elif family == 'invalid_support':
        if replica % 3 == 0:
            mask[:] = True
        elif replica % 3 == 1:
            ivar[:] = 0
        else:
            flux[:] = np.nan
    elif family == 'reversed_grid':
        flux, wave, ivar, mask = (x[::-1] for x in (flux, wave, ivar, mask))
    elif family == 'permuted_grid':
        order = np.random.Generator(np.random.PCG64(recipe['seed']+1)).permutation(len(wave))
        flux, wave, ivar, mask = (x[order] for x in (flux, wave, ivar, mask))
    return {'flux': flux, 'wavelength': wave, 'ivar': ivar, 'mask': mask}, injected if recipe['snr'] > 0 else []


def materialize(cases, output, raw_root, index):
    """Write scientific arrays only; labels/provenance remain in the harness."""
    from desi_fm.local_data import LocalDESIStore
    from desi_fm.data import extract_mmu_desi_example
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = LocalDESIStore(raw_root, index)  # verifies local raw and index hashes
    results = []
    for position, case in enumerate(cases):
        if case['kind'] == 'real':
            f, v, w, m, _ = extract_mmu_desi_example(store.raw(case['object_id']))
            arrays, injected = dict(flux=f, wavelength=w, ivar=v, mask=m), []
        else:
            arrays, injected = render_recipe(case)
        path = output/f'input_{position:04d}.npz'
        np.savez(path, **arrays, wavelength_unit='angstrom')
        results.append((case, path, arrays, injected))
    return results


def select_pilot(cases):
    """SHA-256 of literal UTF-8 case_id; zero-based alternating pair order."""
    key=lambda c:(hashlib.sha256(c['case_id'].encode('utf-8')).hexdigest(),c['case_id'])
    selected=[]
    for exposure in ('train','validation'):
        group=[c for c in cases if c['kind']=='real' and c['cnn_exposure']==exposure]
        selected.extend(sorted(group,key=key)[:2])
    families=sorted({c['family'] for c in cases if c['kind']=='synthetic'})
    for family in families:
        group=[c for c in cases if c.get('family')==family]
        selected.append(min([c for c in group if c['recipe']['snr']==10] or group,key=key))
    if len(selected)!=12 or len(families)!=8:raise ValueError('Frozen pilot selection must contain 12 cases')
    return selected


def canonical_arrays_sha256(payload):
    """Scientific arrays and unit, independent of ZIP metadata; no labels."""
    # Registration must include the deliberately invalid support case. Contract
    # validation belongs to the worker and must reject it with zero paid calls.
    digest=hashlib.sha256(b'spectra-scientific-arrays-v1\0')
    with np.load(BytesIO(payload),allow_pickle=False) as data:
        if not {'flux','wavelength'}<=set(data.files):raise ValueError('Scientific arrays required')
        for name in ('flux','wavelength','ivar','mask','wavelength_unit'):
            value=np.ascontiguousarray(data[name]) if name in data.files else None
            header=json.dumps([name,value.dtype.str,list(value.shape)] if value is not None else [name,None],separators=(',',':')).encode()
            digest.update(len(header).to_bytes(8,'big'));digest.update(header)
            if value is not None:digest.update(value.tobytes())
    return digest.hexdigest()


def sequence(registry,phase,effort='low'):
    from copilot.budget import request_configuration
    request_configuration(effort)
    if phase not in {'pilot','confirmation'}:raise ValueError('Development phase required')
    return [(entry,variant) for i,entry in enumerate(registry['inputs'])
            for variant in ((('low','medium') if i%2==0 else ('medium','low')) if phase=='pilot' else (effort,))]


def validate_plan(plan,registry_path,expected_hash,effort='low'):
    from copilot.acceptance_io import sha256
    if sha256(registry_path)!=expected_hash or plan['registry_sha256']!=expected_hash:
        raise ValueError('Development registry identity mismatch')
    registry=json.loads(Path(registry_path).read_text())
    if (registry.get('schema')!='batch5c-development-registry-v1' or registry.get('development_sha256')!=DEVELOPMENT_SHA
            or len(registry.get('inputs',[]))!=12 or [r['slot'] for r in registry['inputs']]!=list(range(12))):
        raise ValueError('Frozen development registry required')
    expected=sequence(registry,plan['phase'],effort)
    if len(plan['inputs'])!=len(expected):raise ValueError('Frozen development sequence required')
    payloads=[]
    for item,(entry,variant) in zip(plan['inputs'],expected):
        if item['effort']!=variant or item['input_sha256']!=entry['input_sha256']:
            raise ValueError('Frozen development sequence required')
        payload=Path(item['input_path']).read_bytes()
        if hashlib.sha256(payload).hexdigest()!=entry['input_sha256'] or canonical_arrays_sha256(payload)!=entry['arrays_sha256']:
            raise ValueError('Scientific input identity mismatch')
        payloads.append(payload)
    return payloads


def prepare(manifest,output,raw_root,index):
    """Re-derive public development, saving execution and scoring views apart."""
    from copilot.acceptance_io import sha256,write_json
    import secrets
    output=Path(output);output.mkdir(mode=0o700,parents=True,exist_ok=False)
    selected=select_pilot(read_development(manifest))
    materialized=materialize(selected,output/'inputs',raw_root,index)
    ids=[c['case_id'] for c in selected]
    registry={'schema':'batch5c-development-registry-v1','development_sha256':DEVELOPMENT_SHA,
              'selection_sha256':hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),
              'inputs':[{'slot':i,'input_sha256':sha256(path),'arrays_sha256':canonical_arrays_sha256(path.read_bytes())}
                        for i,(_,path,_,_) in enumerate(materialized)]}
    write_json(output/'registry.json',registry)
    items=[];labels=[]
    for entry,effort in sequence(registry,'pilot'):
        case,path,_,_=materialized[entry['slot']];alias=secrets.token_hex(12)
        items.append({'alias':alias,'effort':effort,'input_path':str(path.resolve()),'input_sha256':entry['input_sha256']})
        labels.append({**case,'alias':alias,'effort':effort,'slot':entry['slot']})
    write_json(output/'pilot-inputs.json',{'schema':'batch5c-inputs-v1','mode':'development','phase':'pilot',
               'registry_sha256':sha256(output/'registry.json'),'inputs':items})
    write_json(output/'development-scoring.json',{'schema':'batch5c-development-scoring-v1','cases':labels})
    write_json(output/'selection.json',{'case_ids':ids,'selection_sha256':registry['selection_sha256']})
    return registry


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','output','raw-root','index'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=prepare(a.manifest,a.output,a.raw_root,a.index)
    print(json.dumps({'inputs':len(result['inputs']),'selection_sha256':result['selection_sha256']}))


if __name__=='__main__':main()
