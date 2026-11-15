"""Command-line interface: same pipeline as the app, no Streamlit needed.

    python scripts/ask.py "什么是信息茧房"
    python scripts/ask.py "TasteWeights 让用户调整什么？" --evidence-only
    python scripts/ask.py --demo          # runs the labelled demo set

Useful for inspecting retrieval and refusal behaviour without starting the UI,
and for checking the API key from a terminal.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from litlens import config, service  # noqa: E402

DEMO = [
    "什么是信息茧房？",
    "TasteWeights 让用户调整什么？",
    "用户的信任应该如何校准？",
    "今天北京天气怎么样？",
    "How many guidelines does Amershi propose for human-AI interaction?",
]


def show(question: str, evidence_only: bool) -> None:
    print(f"\nQ: {question}")
    answer = ""
    for event in service.ask(question, evidence_only=evidence_only):
        kind = event["type"]
        if kind == "evidence":
            ids = " ".join(f"{h['id']}({h['score']:.3f})" for h in event["hits"])
            verdict = "ABSTAIN" if event["abstained"] else "answer"
            print(f"  retrieve: {ids}  best={event['best']:.3f}  -> {verdict}")
        elif kind == "delta":
            answer += event["text"]
            print(event["text"], end="", flush=True)
        elif kind == "final":
            print(f"\n  cited: {event['cited']}  removed: {event['removed'] or 'none'}"
                  f"  {event['latency_ms']} ms")
        elif kind == "abstain":
            print(f"  拒绝作答：最高相似度 {event['best']:.3f} < 阈值 {config.MIN_SCORE}")
        elif kind == "insufficient":
            print(f"  模型判定证据不足：{event['text'][:80]}")
        elif kind == "evidence_only":
            print("  只给证据模式：未调用模型")
        elif kind == "error":
            print(f"  错误：{event['message']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="LitLens evidence-first Q&A")
    ap.add_argument("question", nargs="*", help="the question to ask")
    ap.add_argument("--evidence-only", action="store_true", help="skip the model")
    ap.add_argument("--demo", action="store_true", help="run the labelled demo set")
    args = ap.parse_args()
    if args.demo:
        for q in DEMO:
            show(q, args.evidence_only)
        return 0
    if not args.question:
        ap.error("give a question, or --demo")
    show(" ".join(args.question), args.evidence_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
