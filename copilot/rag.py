"""Mini-RAG over the line catalog and DESI reference notes (plan 12).

The corpus is ~30 short, technical documents committed under refs/:
`refs/lines.json` (the extended spectral-line catalog) plus one markdown
note per DESI topic, each carrying its public source URL on a `source:`
first line. Retrieval is BM25 — for a corpus this small with controlled
vocabulary, embeddings add a dependency without adding recall, and BM25
keeps the whole pipeline deterministic and offline.

The agent cites documents by their `id`; `valid_ids()` exists so callers
(and evals) can check that no cited source was hallucinated.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

REFS_DIR = Path(__file__).resolve().parent.parent / "refs"

# Alphanumeric tokens only, so "[OII]" matches a query for "OII" and
# "z=3.5" matches "3.5".
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@lru_cache(maxsize=1)
def _corpus() -> tuple[list[dict], BM25Okapi]:
    docs = []
    for e in json.loads((REFS_DIR / "lines.json").read_text()):
        docs.append({
            "id": e["name"],
            "source": "line-catalog",
            "text": f"{e['name']} at rest {e['rest_angstrom']} A. {e['text']}",
        })
    for path in sorted(REFS_DIR.glob("*.md")):
        lines = path.read_text().strip().splitlines()
        docs.append({
            "id": path.stem,
            "source": lines[0].removeprefix("source:").strip(),
            "text": "\n".join(lines[1:]).strip(),
        })
    bm25 = BM25Okapi([_tokenize(d["id"] + " " + d["text"]) for d in docs])
    return docs, bm25


def valid_ids() -> set[str]:
    """Every citable document id — the ground truth for citation checks."""
    return {d["id"] for d in _corpus()[0]}


def lookup_reference_impl(query: str, k: int = 3) -> dict:
    """Retrieve the k reference documents most relevant to `query`.

    Returns {"results": [{"id", "source", "snippet"}, ...]} strongest first;
    documents with zero term overlap are never returned, so an off-corpus
    query yields an empty list rather than noise.
    """
    docs, bm25 = _corpus()
    scores = bm25.get_scores(_tokenize(query))
    k = max(1, min(int(k), len(docs)))
    top = sorted(range(len(docs)), key=lambda i: -scores[i])[:k]
    return {
        "results": [
            {
                "id": docs[i]["id"],
                "source": docs[i]["source"],
                "snippet": docs[i]["text"][:400],
            }
            for i in top
            if scores[i] > 0
        ]
    }
