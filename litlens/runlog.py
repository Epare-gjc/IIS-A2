"""Per-session interaction log.

Every question writes one row: what was retrieved, whether the system refused,
how long it took, and whether any invented citation had to be removed. The CSV
is the development record for the report -- it shows behaviour, not just claims.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from . import config

FIELDS = [
    "ts",
    "mode",
    "question",
    "top_ids",
    "top_scores",
    "abstained",
    "latency_ms",
    "answer_chars",
    "citations_removed",
    "model",
    "error",
]


class RunLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=FIELDS).writeheader()

    @classmethod
    def new(cls, log_dir: Path | None = None, model: str | None = None) -> "RunLog":
        log_dir = Path(log_dir or config.LOG_DIR)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls(log_dir / f"session_{stamp}.csv")

    def write(self, **row) -> None:
        record = {field: "" for field in FIELDS}
        record.update(row)
        record.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
        if isinstance(record.get("top_ids"), (list, tuple)):
            record["top_ids"] = " ".join(str(x) for x in record["top_ids"])
        if isinstance(record.get("top_scores"), (list, tuple)):
            record["top_scores"] = " ".join(f"{x:.3f}" for x in record["top_scores"])
        if isinstance(record.get("citations_removed"), (list, tuple)):
            record["citations_removed"] = " ".join(str(x) for x in record["citations_removed"])
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS).writerow(
                {field: record.get(field, "") for field in FIELDS}
            )

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
