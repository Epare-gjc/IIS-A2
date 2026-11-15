"""Corpus loading.

The corpus is data/corpus.json: 17 paraphrase notes drawn from the
Assignment 1 reading list plus the design-guideline sources used in the report.
Every passage is a paraphrase, never a verbatim quotation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import config
from .retrieval import Index, tokenize

REQUIRED_FIELDS = ("id", "source", "year", "en")


def passage_text(p: dict) -> str:
    """Text used for retrieval: the note plus its tags, never the citation."""
    return " ".join([p.get("en", ""), " ".join(p.get("tags", []))]).strip()


def load_passages(path: Path | None = None) -> list[dict]:
    path = Path(path or config.CORPUS_PATH)
    data = json.loads(path.read_text(encoding="utf-8"))
    passages = data["passages"]
    seen = set()
    for p in passages:
        missing = [f for f in REQUIRED_FIELDS if not p.get(f)]
        if missing:
            raise ValueError(f"passage {p.get('id', '?')} missing fields: {missing}")
        if p["id"] in seen:
            raise ValueError(f"duplicate passage id: {p['id']}")
        seen.add(p["id"])
        if not tokenize(passage_text(p)):
            raise ValueError(f"passage {p['id']} produces no searchable tokens")
    return passages


def load_aliases(path: Path | None = None) -> dict[str, list[str]]:
    """Source aliases registered in corpus.json, keyed by source_key."""
    path = Path(path or config.CORPUS_PATH)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("meta", {}).get("aliases", {})


@lru_cache(maxsize=1)
def get_index(path: str | None = None) -> Index:
    passages = load_passages(Path(path) if path else None)
    aliases = load_aliases(Path(path) if path else None)
    return Index(
        [
            {
                "id": p["id"],
                "text": passage_text(p),
                "aliases": aliases.get(p.get("source_key", ""), []),
                "raw": p,
            }
            for p in passages
        ]
    )


def by_id(passage_id: str) -> dict | None:
    for p in load_passages():
        if p["id"] == passage_id:
            return p
    return None
