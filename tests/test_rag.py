"""Offline tests for the mini-RAG (plan 12): corpus, retrieval, integration.

The corpus is committed under refs/, so everything here runs with no model,
no network and no API key.
"""

import json
from pathlib import Path

from copilot import agent, rag
from copilot.report import SYSTEM

REFS = Path(__file__).resolve().parent.parent / "refs"


def test_corpus_is_committed_and_well_formed():
    lines = json.loads((REFS / "lines.json").read_text())
    assert len(lines) >= 15
    for e in lines:
        assert e["name"] and e["rest_angstrom"] > 0 and len(e["text"]) > 50
    # The DoD asks for >= 10 reference notes, each carrying its source URL
    # on the first line so every retrieved snippet is attributable.
    notes = sorted(REFS.glob("*.md"))
    assert len(notes) >= 10
    for p in notes:
        first = p.read_text().strip().splitlines()[0]
        assert first.startswith("source:"), p.name
        assert first.removeprefix("source:").strip().startswith("https://"), p.name


def test_dod_query_returns_the_degeneracy_docs():
    # DoD unit test: the Halpha/[OII] confusion query must surface the
    # single-line degeneracy note and both line-catalog entries involved.
    ids3 = [r["id"] for r in rag.lookup_reference_impl("Halpha OII confusion")["results"]]
    assert "line-degeneracy-single-line" in ids3
    assert "Halpha_6563" in ids3
    ids5 = [r["id"] for r in rag.lookup_reference_impl("Halpha OII confusion", k=5)["results"]]
    assert "OII_3727" in ids5


def test_target_type_priors_are_retrievable():
    # The reason the corpus exists: target-type z ranges as priors.
    r = rag.lookup_reference_impl("ELG redshift range")["results"]
    assert r[0]["id"] == "desi-targets-elg"
    assert "0.6" in r[0]["snippet"]
    assert r[0]["source"].startswith("https://arxiv.org/")


def test_results_are_typed_and_ids_valid():
    r = rag.lookup_reference_impl("quasar broad lines", k=4)["results"]
    assert 0 < len(r) <= 4
    for item in r:
        assert item["id"] in rag.valid_ids()
        assert item["source"] and len(item["snippet"]) <= 400


def test_off_corpus_query_returns_empty_not_noise():
    assert rag.lookup_reference_impl("zzz qqq xyzzy")["results"] == []


def test_k_is_clamped():
    docs = len(rag.valid_ids())
    assert len(rag.lookup_reference_impl("DESI", k=999)["results"]) <= docs
    assert len(rag.lookup_reference_impl("DESI", k=0)["results"]) == 1


def test_wrapped_agent_tool_matches_impl():
    out = agent.lookup_reference.call({"query": "Halpha OII confusion"})
    assert json.loads(out) == rag.lookup_reference_impl("Halpha OII confusion")


def test_system_prompt_has_citation_contract():
    # The agent must be told to cite retrieved ids and forbidden from
    # inventing sources — that rule is the whole point of the mini-RAG.
    assert "lookup_reference" in SYSTEM
    assert "[line-catalog]" in SYSTEM
    assert "never invent" in SYSTEM
