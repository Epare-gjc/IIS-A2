"""DeepSeek access over plain HTTPS.

The API is OpenAI-compatible (base_url https://api.deepseek.com, model
deepseek-flash), but this module speaks the wire format directly with the
standard library. The project then needs exactly one third-party package
(Streamlit) to run, and a reviewer can inspect the request body -- including
the citation rules -- without an SDK in the middle. Two details matter and are
set explicitly:

* thinking mode is disabled: it is ON by default, adds latency, and makes
  `temperature` a no-op (checked against the API docs, Nov 2026);
* max_tokens is small, because an answer is meant to be one short paragraph.

Streaming responses arrive as server-sent events, so the reader below yields
text as it lands instead of waiting for the whole answer.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

from . import config

ENDPOINT = f"{config.BASE_URL}/chat/completions"


class LlmError(RuntimeError):
    """A failure already phrased for the interface."""


def _friendly_status(status: int, detail: str) -> str:
    if status == 401:
        return "API key is invalid or expired. Check DEEPSEEK_API_KEY in .env."
    if status == 402:
        return "DeepSeek account balance is too low. Top up at platform.deepseek.com."
    if status == 429:
        return "DeepSeek rate limit reached. Try again in a moment."
    if status >= 500:
        return f"DeepSeek server error ({status}). Try again shortly."
    return f"DeepSeek request failed ({status}). {detail[:200]}"


def _payload(messages: list[dict], stream: bool) -> dict:
    return {
        "model": config.MODEL,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_TOKENS,
        "stream": stream,
        "thinking": {"type": "disabled"},
    }


def _open(payload: dict, api_key: str):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if payload.get("stream") else "application/json",
        },
    )
    try:
        return urllib.request.urlopen(request, timeout=config.REQUEST_TIMEOUT)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise LlmError(_friendly_status(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise LlmError(f"Cannot reach DeepSeek (network or proxy): {exc.reason}") from exc
    except TimeoutError as exc:
        raise LlmError("DeepSeek timed out; no answer was generated.") from exc


def _deltas(response) -> Iterator[str]:
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        chunk = line[len("data:") :].strip()
        if chunk == "[DONE]":
            return
        try:
            event = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        for choice in event.get("choices") or []:
            text = (choice.get("delta") or {}).get("content")
            if text:
                yield text


def stream_answer(messages: list[dict], api_key: str | None = None) -> Iterator[str]:
    """Yield answer text as it streams. Raises LlmError on a visible failure."""
    key = api_key or config.api_key()
    if not key:
        raise LlmError(
            "No DEEPSEEK_API_KEY configured. Use evidence-only mode to inspect retrieval without the model."
        )
    with _open(_payload(messages, stream=True), key) as response:
        yield from _deltas(response)


def check_connection(api_key: str | None = None) -> tuple[bool, str]:
    """One tiny non-streaming call, used by the sidebar status line."""
    key = api_key or config.api_key()
    if not key:
        return False, "no API key configured"
    payload = _payload([{"role": "user", "content": "ping"}], stream=False)
    payload["max_tokens"] = 1
    try:
        with _open(payload, key) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        model = data.get("model", config.MODEL)
        return True, f"connection ok ({model})"
    except LlmError as exc:
        return False, str(exc)
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"unparseable response: {exc}"
