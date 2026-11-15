"""Pure-python TF-IDF retrieval.

Deliberately dependency-free: the ranking a reader sees is the ranking they can
reproduce with `python -m unittest`, and there is no second API to fail during
the demo.

Three choices are worth knowing about:

* Chinese text is indexed as character bigrams, not single characters. Without
  a segmenter, single characters are too common to discriminate (用, 户, 么
  appear in almost every note) and they made off-topic Chinese questions score
  as high as answerable ones.
* Question words (什么, 怎么, 是否 ...) are stopworded in both languages.
* If the question names a paper or author, that source's notes are boosted. The
  corpus is small enough to register aliases by hand in data/corpus.json, and a
  named source is the strongest signal a reader can give.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]+")

EN_STOPWORDS = frozenset(
    """a an the and or of to in on for with by as at from is are was were be been
    being this that these those it its their they we you your i not no do does did
    can could should would will may might must if then than so such about into over
    under between among what which who whom how why when where whose there here all
    any both each few more most other some only own same too very just also using
    use used""".split()
)

# Question words only. Content words such as 用户 stay, because they are what a
# question is about even when they are frequent.
ZH_STOPWORDS = frozenset(
    """什么 怎么 如何 哪些 哪个 哪里 是否 可以 需要 请问 为什 么样 一下 这个 那个
    有哪 有什 是什 么是""".split()
)

STOPWORDS = EN_STOPWORDS | ZH_STOPWORDS

SOURCE_BOOST = 0.20


def _stem(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []
    for w in _WORD.findall(text):
        if w in STOPWORDS or len(w) < 2:
            continue
        tokens.append(_stem(w))
    for run in _CJK.findall(text):
        grams = [run] if len(run) == 1 else [run[i : i + 2] for i in range(len(run) - 1)]
        tokens.extend(g for g in grams if g not in STOPWORDS)
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
