"""The whole interaction as one generator.

Both interfaces (Streamlit app.py and the CLI scripts/ask.py) drive the same
pipeline, so what the report says about behaviour is what both do:

    question -> retrieve top-3 -> below MIN_SCORE? -> refuse and stop
             -> otherwise generate with those passages only
             -> strip invented citations -> log one row

`ask()` yields events instead of returning a value so the interface can show
evidence before the first token arrives. That order is a design choice: the user
sees what the answer will be built from while it is being written.
"""

from __future__ import annotations

import time
from typing import Iterator

from . import citations, config, corpus, llm, prompt
from .runlog import RunLog


def retrieve(question: str) -> tuple[list[dict], float]:
    hits = corpus.get_index().search(question, k=config.TOP_K)
    best = hits[0]["score"] if hits else 0.0
    return hits, best


def ask(
    question: str,
    api_key: str | None = None,
    evidence_only: bool = False,
    log: RunLog | None = None,
) -> Iterator[dict]:
    """Yield evidence / delta / final / abstain / evidence_only / error events.

    Only passages at or above MIN_SCORE are sent to the model and shown as
    evidence. A 0.00 passage is not evidence, and letting the model cite one
    would make the citation meaningless.
    """
    question = (question or "").strip()
    started = time.perf_counter()
    hits, best = retrieve(question)
    abstained = best < config.MIN_SCORE
    evidence = [h for h in hits if h["score"] >= config.MIN_SCORE]
    allowed = set(range(1, len(evidence) + 1))
    base = {
        "mode": "evidence-only" if evidence_only else "grounded",
        "question": question,
        "top_ids": [h["id"] for h in hits],
        "top_scores": [h["score"] for h in hits],
        "abstained": abstained,
        "model": config.MODEL,
    }

    yield {"type": "evidence", "hits": evidence, "best": best, "abstained": abstained}

    if abstained:
        if log is not None:
            log.write(**base, latency_ms=int((time.perf_counter() - started) * 1000))
        yield {"type": "abstain", "best": best, "hits": hits}
        return

    if evidence_only:
        if log is not None:
            log.write(**base, latency_ms=int((time.perf_counter() - started) * 1000))
        yield {"type": "evidence_only", "hits": evidence}
        return

    messages = prompt.build_messages(question, [h["doc"]["raw"] for h in evidence])
    chunks: list[str] = []
    try:
        for delta in llm.stream_answer(messages, api_key=api_key):
            chunks.append(delta)
            yield {"type": "delta", "text": delta}
    except llm.LlmError as exc:
        if log is not None:
            log.write(
                **base,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )
        yield {"type": "error", "message": str(exc)}
        return

    raw = "".join(chunks).strip()
    latency_ms = int((time.perf_counter() - started) * 1000)
    if prompt.is_insufficient(raw):
        if log is not None:
            log.write(**base, latency_ms=latency_ms, answer_chars=len(raw))
        yield {"type": "insufficient", "text": raw}
        return

    answer, removed = citations.validate(raw, allowed)
    if log is not None:
        log.write(
            **base,
            latency_ms=latency_ms,
            answer_chars=len(answer),
            citations_removed=removed,
        )
    yield {
        "type": "final",
        "text": answer,
        "removed": removed,
        "cited": citations.cited(answer),
        "hits": evidence,
        "latency_ms": latency_ms,
    }
