from __future__ import annotations

import base64
import json
import os
import time
from functools import lru_cache
from typing import Any

from PIL import Image
from pydantic import BaseModel

from .config import FALLBACK_MODELS, PROVIDER
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
        from google.genai import errors

        candidates = [model, *[m for m in FALLBACK_MODELS if m != model]]
        for i, m in enumerate(candidates):
            try:
                data, usage = _gemini(m, system, content, schema, max_tokens, effort)
                model = m
                break
            except errors.ServerError:
                if i == len(candidates) - 1:
                    raise
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


@lru_cache(maxsize=1)
def _gemini_client():
    from google import genai
    from google.genai import types

    return genai.Client(
        http_options=types.HttpOptions(
            timeout=180_000,
            retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2.0, max_delay=30.0),
        )
    )


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


def _gemini(model, system, content, schema, max_tokens, effort):
    from google.genai import types

    level = {"low": "low", "medium": "medium", "high": "high"}.get(effort, "medium")
    thinking = types.ThinkingConfig(thinking_level=level) if model.startswith("gemini-3") else None
    resp = _gemini_client().models.generate_content(
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
