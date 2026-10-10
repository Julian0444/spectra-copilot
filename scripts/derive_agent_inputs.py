"""Derive opaque scientific NPZ inputs. Keep the source map with the evaluator."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from desi_fm.inputs import read_npz


def derive(sources, destination, provenance):
    destination,provenance=Path(destination),Path(provenance)
    resolved_destination = destination.resolve()
    resolved_provenance = provenance.resolve()
    if resolved_provenance == resolved_destination or resolved_destination in resolved_provenance.parents:
        raise ValueError('Provenance must be outside the opaque input destination')
    if destination.exists() or provenance.exists():
        raise ValueError('Use new destination and provenance paths; originals are never overwritten')
    rows=[]
    # Validate all scientific inputs before creating an output directory.
    parsed=[(Path(source),read_npz(source).single()) for source in sources]
    if not parsed:raise ValueError('At least one input is required')
    destination.mkdir(parents=True)
    for i,(source,(f,w,v,m)) in enumerate(parsed,1):
        target=destination/f'spectrum_{i:04d}.npz'
        np.savez(target,flux=f,wavelength=w,ivar=v,mask=m,wavelength_unit='angstrom')
        rows.append({'input_id':target.stem,'source':str(source.resolve()),
                     'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                     'derived_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    provenance.parent.mkdir(parents=True,exist_ok=True)
    provenance.write_text(json.dumps({'protocol':'opaque-scientific-input-v2','inputs':rows},indent=2)+'\n')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--provenance',type=Path,required=True)
    p.add_argument('sources',nargs='+',type=Path)
    a=p.parse_args();derive(a.sources,a.destination,a.provenance)

if __name__=='__main__':main()
