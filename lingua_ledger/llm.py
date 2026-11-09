from __future__ import annotations

import base64
import collections
import json
import os
import re
import threading
import time
from functools import lru_cache
from typing import Any

from PIL import Image
from pydantic import BaseModel

from .config import FALLBACK_MODELS, GEMINI_RPM, PROVIDER
from .ingest import to_jpeg_base64


def has_api_key() -> bool:
    if PROVIDER == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def image_blocks(images: list[Image.Image], max_side: int = 1800) -> list[dict[str, Any]]:
    blocks = []
    for i, img in enumerate(images):
        blocks.append({"type": "text", "text": f"Page {i + 1}:"})
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": to_jpeg_base64(img, max_side),
                },
            }
        )
    return blocks


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a JSON schema acceptable for structured outputs: closed objects, every property required."""

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            node = {k: walk(v) for k, v in node.items() if k not in ("default", "title")}
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            return node
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


def call_structured(
    model: str,
    system: str,
    content: list[dict[str, Any]] | str,
    schema: type[BaseModel],
    max_tokens: int = 8192,
    effort: str = "medium",
) -> tuple[dict[str, Any], dict[str, Any]]:
    t0 = time.perf_counter()
    if PROVIDER == "gemini":
        data, usage, model = _gemini_with_fallback(model, system, content, schema, max_tokens, effort)
    else:
        data, usage = _anthropic(model, system, content, schema, max_tokens, effort)
    usage.update({"latency_s": round(time.perf_counter() - t0, 3), "model": model, "provider": PROVIDER})
    return data, usage


def _loads(text: str) -> dict[str, Any]:
    try:
        out = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return out if isinstance(out, dict) else {}


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic(max_retries=4, timeout=180)


def _anthropic(model, system, content, schema, max_tokens, effort):
    resp = _anthropic_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": strict_schema(schema.model_json_schema())},
        },
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return _loads(text), {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "stop_reason": resp.stop_reason,
    }


_local = threading.local()


class _RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.lock = threading.Lock()
        self.sent: collections.deque[float] = collections.deque()

    def wait(self) -> None:
        if self.per_minute <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                while self.sent and now - self.sent[0] > 60:
                    self.sent.popleft()
                if len(self.sent) < self.per_minute:
                    self.sent.append(now)
                    return
                delay = 60 - (now - self.sent[0]) + 0.2
            time.sleep(max(delay, 0.2))


_limiter = _RateLimiter(GEMINI_RPM)
_retry_in = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)


def _gemini_client(fresh: bool = False):
    client = None if fresh else getattr(_local, "gemini", None)
    if client is None:
        from google import genai
        from google.genai import types

        client = genai.Client(
            http_options=types.HttpOptions(
                timeout=120_000,
                retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2.0, max_delay=20.0),
            )
        )
        _local.gemini = client
    return client


def _gemini_parts(content):
    from google.genai import types

    if isinstance(content, str):
        return [types.Part.from_text(text=content)]
    parts = []
    for block in content:
        if block["type"] == "text":
            parts.append(types.Part.from_text(text=block["text"]))
        elif block["type"] == "image":
            src = block["source"]
            parts.append(
                types.Part.from_bytes(data=base64.b64decode(src["data"]), mime_type=src["media_type"])
            )
    return parts


def _gemini_with_fallback(model, system, content, schema, max_tokens, effort):
    from google.genai import errors

    candidates = [model, *[m for m in FALLBACK_MODELS if m != model]]
    for i, m in enumerate(candidates):
        for attempt in range(6):
            _limiter.wait()
            try:
                data, usage = _gemini(m, system, content, schema, max_tokens, effort, fresh=attempt > 0)
                return data, usage, m
            except errors.ClientError as e:
                if getattr(e, "code", None) != 429 or attempt == 5:
                    raise
                found = _retry_in.search(str(e))
                time.sleep(min(float(found.group(1)) if found else 10.0, 65.0) + 1.0)
            except RuntimeError as e:
                if "closed" not in str(e) or attempt == 5:
                    raise
            except errors.ServerError:
                if i == len(candidates) - 1:
                    raise
                break
    raise RuntimeError("no model candidates")


def _gemini(model, system, content, schema, max_tokens, effort, fresh: bool = False):
    from google.genai import types

    level = {"low": "low", "medium": "medium", "high": "high"}.get(effort, "medium")
    thinking = types.ThinkingConfig(thinking_level=level) if model.startswith("gemini-3") else None
    resp = _gemini_client(fresh).models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=_gemini_parts(content))],
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
            temperature=0,
            thinking_config=thinking,
        ),
    )
    u = resp.usage_metadata
    cand = resp.candidates[0] if resp.candidates else None
    return _loads(resp.text), {
        "input_tokens": (u.prompt_token_count or 0) if u else 0,
        "output_tokens": ((u.candidates_token_count or 0) + (u.thoughts_token_count or 0)) if u else 0,
        "stop_reason": str(cand.finish_reason) if cand else None,
    }
