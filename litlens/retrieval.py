"""Pure-python TF-IDF retrieval.

Deliberately dependency-free: the ranking a reader sees is the ranking they can
reproduce with `python -m unittest`, and there is no second API to fail during
the demo.

Two choices are worth knowing about:

* Tokens are lower-cased word runs, lightly stemmed (a trailing "s" is dropped),
  with question words stopworded. Short tokens are dropped because one and two
  letter fragments carry no topic.
* If the question names a paper or author, that source's notes are boosted. The
  corpus is small enough to register aliases by hand in data/corpus.json, and a
  named source is the strongest signal a reader can give.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """a an the and or of to in on for with by as at from is are was were be been
    being this that these those it its their they we you your i not no do does did
    can could should would will may might must if then than so such about into over
    under between among what which who whom how why when where whose there here all
    any both each few more most other some only own same too very just also using
    use used""".split()
)

SOURCE_BOOST = 0.20


def _stem(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []
    for w in _WORD.findall(text):
        if len(w) < 2 or w in STOPWORDS:
            continue
        tokens.append(_stem(w))
    return tokens


def _alias_matches(query_tokens: set[str], aliases: list[str]) -> bool:
    """True when every token of one registered alias is in the question."""
    for alias in aliases:
        parts = tokenize(alias)
        if parts and all(p in query_tokens for p in parts):
            return True
    return False


class Index:
    """Cosine similarity over sublinear TF-IDF vectors, plus a source boost."""

    def __init__(self, docs: list[dict]):
        self.docs = docs
        self._tfs: list[Counter] = []
        df: Counter = Counter()
        for doc in docs:
            tf = Counter(tokenize(doc["text"]))
            self._tfs.append(tf)
            for term in tf:
                df[term] += 1
        n = len(docs)
        self._idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self._vectors = [self._weigh(tf) for tf in self._tfs]

    def _weigh(self, tf: Counter) -> dict[str, float]:
        vec = {
            term: (1.0 + math.log(count)) * self._idf.get(term, 1.0)
            for term, count in tf.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3) -> list[dict]:
        """Return up to k hits as {score, id, doc}, best first.

        score = cosine similarity + SOURCE_BOOST when the question names the
        source. It is clamped so a boosted weak match cannot pass the abstention
        threshold on the boost alone.
        """
        tokens = tokenize(query)
        if not tokens:
            return []
        qvec = self._weigh(Counter(tokens))
        qset = set(tokens)
        scored = []
        for i, dvec in enumerate(self._vectors):
            cosine = sum(w * dvec.get(term, 0.0) for term, w in qvec.items())
            doc = self.docs[i]
            if cosine and _alias_matches(qset, doc.get("aliases", [])):
                cosine = min(0.99, cosine + SOURCE_BOOST)
            scored.append((cosine, i))
        scored.sort(key=lambda pair: (-pair[0], self.docs[pair[1]]["id"]))
        return [
            {"score": round(score, 4), "id": self.docs[i]["id"], "doc": self.docs[i]}
            for score, i in scored[:k]
        ]

    def best_score(self, query: str) -> float:
        hits = self.search(query, k=1)
        return hits[0]["score"] if hits else 0.0
