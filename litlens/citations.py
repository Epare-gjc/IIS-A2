"""Citation checking.

The model is told to cite only the passages it was given. It still sometimes
invents an id, so the answer is verified before it is shown: any [Sn] outside
the allowed set is removed and reported to the user. This is the one check the
system performs on generated text, and it is testable without an API key.
"""

from __future__ import annotations

import re

_CITE = re.compile(r"\[S\s*(\d+)\s*\]")
_GROUP = re.compile(r"\[\s*S\s*\d+(?:\s*[,;]\s*S?\s*\d+)+\s*\]")


def normalise(text: str) -> str:
    """Turn [S1, S2] into [S1][S2] so one regex can check every citation."""

    def repl(match: re.Match) -> str:
        nums = re.findall(r"\d+", match.group(0))
        return "".join(f"[S{n}]" for n in nums)

    return _GROUP.sub(repl, text)


def validate(text: str, allowed: set[int] | range) -> tuple[str, list[int]]:
    """Return (cleaned_text, removed_ids)."""
    allowed = set(allowed)
    removed: list[int] = []

    def repl(match: re.Match) -> str:
        n = int(match.group(1))
        if n in allowed:
            return f"[S{n}]"
        removed.append(n)
        return ""

    cleaned = _CITE.sub(repl, normalise(text))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    return cleaned.strip(), removed


def cited(text: str) -> list[int]:
    """Ids actually cited in a checked answer, in order of appearance."""
    out: list[int] = []
    for n in (int(m.group(1)) for m in _CITE.finditer(normalise(text))):
        if n not in out:
            out.append(n)
    return out
