"""Calibration harness for MIN_SCORE (and a quick sanity check on ranking).

Run from the project root:  python scripts/calibrate.py

It prints the best retrieval score for questions the corpus can answer and for
questions it cannot. MIN_SCORE has to sit between the two groups; the gap is
what the report cites when it explains the abstention threshold. It also shows
whether the top hit belongs to the source the question is about.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from litlens import config, corpus  # noqa: E402

ANSWERABLE = [
    ("What do users adjust in TasteWeights?", "bostandjiev2012"),
    ("TasteWeights 让用户调整什么？", "bostandjiev2012"),
    ("什么是信息茧房", "pariser2011"),
    ("用户的信任应该如何校准", "leessee2004"),
    ("为什么用户分辨不出不同推荐算法", "ekstrand2014"),
    ("How many guidelines does Amershi propose for human-AI interaction?", "amershi2019"),
    ("解释有哪些目标", "tintarev2015"),
    ("direct manipulation 有哪些特征", "shneiderman1983"),
    ("混合主动原则要求权衡什么", "horvitz1999"),
    ("检索增强生成有什么局限", "lewis2020"),
]

UNANSWERABLE = [
    "How do I bake sourdough bread?",
    "今天北京天气怎么样",
    "Recommend a good laptop for gaming",
    "Who won the 2026 World Cup?",
    "写一段 Python 快排代码",
]


def main() -> int:
    index = corpus.get_index()
    print(f"passages: {len(index.docs)}   MIN_SCORE currently {config.MIN_SCORE}\n")
    print(f"{'kind':<11}{'best':>6}  {'top-3 ids':<12} {'top source':<18} question")
    print("-" * 100)
    answered, refused = [], []
    misses = []
    for question, expected in ANSWERABLE:
        hits = index.search(question, k=config.TOP_K)
        best = hits[0]["score"]
        source = hits[0]["doc"]["raw"].get("source_key", "?")
        answered.append((best, question))
        ok = source == expected
        if not ok:
            misses.append((question, expected, source))
        ids = " ".join(h["id"] for h in hits)
        print(
            f"{'answerable':<11}{best:>6.3f}  {ids:<12} {source:<18} {question}"
            + ("" if ok else f"   <-- expected {expected}")
        )
    for question in UNANSWERABLE:
        best = index.best_score(question)
        refused.append((best, question))
        print(f"{'off-topic':<11}{best:>6.3f}  {'-':<12} {'-':<18} {question}")
    print("-" * 100)
    lowest_ok = min(answered)
    highest_bad = max(refused)
    print(f"lowest answerable score : {lowest_ok[0]:.3f}  ({lowest_ok[1]})")
    print(f"highest off-topic score : {highest_bad[0]:.3f}  ({highest_bad[1]})")
    print(f"gap                      : {lowest_ok[0] - highest_bad[0]:+.3f}")
    print(f"suggested MIN_SCORE     : {(lowest_ok[0] + highest_bad[0]) / 2:.3f}")
    print(f"source match             : {len(ANSWERABLE) - len(misses)}/{len(ANSWERABLE)}")
    for question, expected, got in misses:
        print(f"  MISS  {question}  -> {got} (expected {expected})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
