"""Mini-RAG over the line catalog and DESI reference notes (plan 12).

The corpus contains short local reference documents committed under refs/:
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
from importlib.resources import files
import hashlib

from rank_bm25 import BM25Okapi
from desi_fm.inputs import positive_int, SpectrumInputError

REFS_DIR = files("copilot").joinpath("refs")

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
            "source": "local:refs/lines.json (editorial catalog; no external bibliography)",
            "resource": "refs/lines.json",
            "text": f"{e['name']} at rest {e['rest_angstrom']} A. {e['text']}",
        })
    for path in sorted((p for p in REFS_DIR.iterdir() if p.name.endswith(".md")), key=lambda p: p.name):
        lines = path.read_text().strip().splitlines()
        docs.append({
            "id": path.name[:-3],
            "source": lines[0].removeprefix("source:").strip(),
            "resource": "refs/"+path.name,
            "text": "\n".join(lines[1:]).strip(),
        })
    hashes = corpus_hashes()
    for doc in docs:
        doc['resource_sha256'] = hashes[doc['resource']]
        doc['text_sha256'] = hashlib.sha256(doc['text'].encode()).hexdigest()
    if len({d['id'] for d in docs}) != len(docs):
        raise RuntimeError('Duplicate corpus IDs')
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
    if not isinstance(query, str) or not query.strip():
        raise SpectrumInputError("query: expected a nonempty string")
    k = positive_int(k, "k", 30)
    docs, bm25 = _corpus()
    scores = bm25.get_scores(_tokenize(query))
    k = min(k, len(docs))
    top = sorted(range(len(docs)), key=lambda i: -scores[i])[:k]
    hashes = corpus_hashes()
    if any(d['resource_sha256'] != hashes[d['resource']] for d in docs):
        raise RuntimeError('Corpus changed after loading')
    return {
        'corpus_revision': corpus_revision(),
        'retrieval': 'BM25 over local editorial notes; score is not claim support',
        'results': [dict(docs[i], snippet=docs[i]['text'][:400],
                         fragment_start=0, fragment_end=len(docs[i]['text']),
                         fragment_sha256=docs[i]['text_sha256'])
                    for i in top if scores[i] > 0],
    }


def validate_retrieval(retrieved):
    """Validate exact local fragments and provenance, not their scientific truth."""
    if retrieved.get('corpus_revision') != corpus_revision():
        raise ValueError('Corpus identity mismatch')
    docs = {d['id']: d for d in _corpus()[0]}
    seen = set()
    for item in retrieved['results']:
        reference = item['id']
        if reference not in valid_ids() or reference in seen:
            raise ValueError('Invalid or duplicate reference ID')
        seen.add(reference)
        doc = docs.get(reference)
        if doc is None or any(item.get(k) != v for k, v in doc.items()):
            raise ValueError('Retrieved content or source mismatch')
        if (item.get('snippet') != doc['text'][:400] or item.get('fragment_start') != 0
                or item.get('fragment_end') != len(doc['text'])
                or item.get('fragment_sha256') != doc['text_sha256']
                or doc['resource_sha256'] != corpus_hashes()[doc['resource']]):
            raise ValueError('Fragment provenance mismatch')
    return True



def corpus_hashes():
    """Content identity works with installed wheel resources, without checkout paths."""
    return {f"refs/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(REFS_DIR.iterdir(), key=lambda p:p.name) if p.is_file()}


def corpus_revision():
    return hashlib.sha256(json.dumps(corpus_hashes(), sort_keys=True).encode()).hexdigest()
