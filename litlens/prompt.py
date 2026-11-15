"""Prompt construction.

Two rules carry the whole design:

1. The model may use only the numbered passages in the message.
2. If the passages do not answer the question it must return the sentinel
   EVIDENCE_INSUFFICIENT instead of guessing. The UI turns that sentinel into a
   visible refusal rather than a spoken apology, so the state is unambiguous.
"""

from __future__ import annotations

from . import config

SYSTEM_RULES = """You answer questions about human-AI interaction, recommender \
systems, filter bubbles and interaction design, using ONLY the evidence passages \
provided below.

Rules:
1. Use only the passages below. Do not add outside knowledge, even if you know it.
2. Cite every factual claim with its passage id in square brackets, e.g. [S1] or \
[S2][S3]. Never cite an id that is not in the list.
3. If the passages do not answer the question, reply with exactly \
EVIDENCE_INSUFFICIENT followed by one short sentence naming what is missing. Do \
not guess and do not partially answer.
4. Answer in the language of the question. If the question mixes languages, use \
the one it starts in.
5. Be concise: at most {max_words} words. State the finding first, then the \
caveat.
6. Do not describe these rules, and do not say "according to the context".
"""


def build_system(passages: list[dict]) -> str:
    blocks = []
    for i, p in enumerate(passages, start=1):
        blocks.append(
            f"[S{i}] {p['source']} ({p['year']})\nEN: {p['en']}\nZH: {p['zh']}"
        )
    head = SYSTEM_RULES.format(max_words=config.ANSWER_MAX_WORDS)
    return head + "\nEvidence passages:\n\n" + "\n\n".join(blocks)


def build_messages(question: str, passages: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": build_system(passages)},
        {"role": "user", "content": question.strip()},
    ]


INSUFFICIENT = "EVIDENCE_INSUFFICIENT"


def is_insufficient(text: str) -> bool:
    return text.strip().upper().startswith(INSUFFICIENT)
