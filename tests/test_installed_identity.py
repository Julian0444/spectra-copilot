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


def test_llm_path_tracks_execution_but_not_posthoc_scoring_or_protocol():
    from copy import deepcopy
    behavior={'code_sha256':{'copilot/agent.py':'a','copilot/budget.py':'b','copilot/review.py':'c','desi_fm/model.py':'d'},
              'source_content_sha256':'all','protocol':{'adenda':'a'},'installation':{'wheel':'a'},
              'auxiliary_code_sha256':{},'assets':{'checkpoint':'fixed'},'prompt_sha256':'fixed'}
    first=identity.llm_path_digest(behavior)
    later=deepcopy(behavior);later['code_sha256']['copilot/review.py']='new';later['protocol']['adenda']='new'
    later['installation']['wheel']='new';later['source_content_sha256']='new'
    assert identity.llm_path_digest(later)==first
    later['code_sha256']['copilot/budget.py']='new'
    assert identity.llm_path_digest(later)!=first
