"""Derive opaque scientific NPZ inputs. Keep the source map with the evaluator."""
import argparse
import hashlib
import json
from pathlib import Path
import unicodedata
import numpy as np
from desi_fm.inputs import read_npz


def _case_aliases(directory):
    ancestor = directory
    while not ancestor.exists():
        ancestor = ancestor.parent
    # Read-only probe of an existing entry on the destination volume. No output
    # directory or probe file is created to learn its name comparison behavior.
    for entry in ancestor.iterdir():
        if not entry.exists():
            continue  # dangling symlinks cannot reveal the volume's behavior
        alternate = entry.with_name(entry.name.swapcase())
        if alternate != entry:
            return alternate.exists() and alternate.samefile(entry)
    # If an empty/numeric-only directory cannot prove sensitivity, fail closed
    # for differently cased descendants rather than creating a provenance leak.
    return True


def derive(sources, destination, provenance):
    destination,provenance=Path(destination),Path(provenance)
    if destination.exists() or provenance.exists():
        raise ValueError('Use new destination and provenance paths; originals are never overwritten')
    resolved_destination = destination.resolve()
    resolved_provenance = provenance.resolve()
    destination_parts, provenance_parts = resolved_destination.parts, resolved_provenance.parts
    if _case_aliases(resolved_destination):
        destination_parts = tuple(unicodedata.normalize('NFD', p).casefold() for p in destination_parts)
        provenance_parts = tuple(unicodedata.normalize('NFD', p).casefold() for p in provenance_parts)
    if provenance_parts[:len(destination_parts)] == destination_parts:
        raise ValueError('Provenance must be outside the opaque input destination')
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
