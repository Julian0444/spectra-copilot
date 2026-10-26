"""Installed identity rejects a source checkout and tampered wheel records."""
import json
from pathlib import Path

import pytest

from copilot import candidate_identity as identity


def test_installed_identity_requires_build_provenance_and_noneditable_packages(tmp_path):
    manifest=tmp_path/'build.json'
    manifest.write_text(json.dumps({'schema':'spectra-installed-build-v1','packages':{}}))
    with pytest.raises(ValueError,match='package|installed|distribution'):
        identity.installed_evidence(manifest)


def test_installed_identity_rejects_candidate_before_recapture(tmp_path,monkeypatch):
    path=tmp_path/'candidate.json';path.write_text(json.dumps({'kind':'candidate-5b22'}))
    monkeypatch.setattr(identity,'capture',lambda *a,**k:pytest.fail('Candidate reached runtime capture'))
    with pytest.raises(ValueError,match='installed-5c'):
        identity.verify(path,tmp_path,require_installed=True)
