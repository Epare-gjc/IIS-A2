"""Runtime settings.

Values live here rather than in the UI so that the report can point at one
file when it explains the two thresholds that shape the interaction:

* MIN_SCORE -- below this retrieval similarity the system refuses to answer.
* TOP_K     -- how many evidence passages the model is allowed to cite.

Both were calibrated against a fixed set of answerable and off-topic
questions; the measurements are recorded beside MIN_SCORE.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = PROJECT_ROOT / "data" / "corpus.json"
LOG_DIR = PROJECT_ROOT / "logs"

# --- DeepSeek ---------------------------------------------------------------
BASE_URL = "https://api.deepseek.com"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

# Thinking mode is ON by default for this API and it ignores `temperature`.
# A grounded, short-answer service wants a stable answer and low latency, so the
# request disables thinking explicitly (see llm.py) instead of relying on the
# default.
TEMPERATURE = 0.2
MAX_TOKENS = 400
REQUEST_TIMEOUT = 60

# --- Retrieval --------------------------------------------------------------
TOP_K = 3
# Calibrated on 2026-11-15 against 15 questions: 10 answerable questions
# scored 0.374-0.757, 5 off-topic questions 0.000-0.190. 0.28 sits in that gap
# and leans towards refusing, because a refusal is the cheaper error here: the
# evidence panel still lets the user judge the retrieval.
MIN_SCORE = 0.28

# --- Interface --------------------------------------------------------------
ANSWER_MAX_WORDS = 120


def api_key() -> str:
    """Read the key from the environment, then from a local .env file.

    The key is never written to logs, and .env is git-ignored.
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "DEEPSEEK_API_KEY":
                return value.strip().strip('"').strip("'")
    return ""


def has_api_key() -> bool:
    return bool(api_key())
