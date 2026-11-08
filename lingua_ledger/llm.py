from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from typing import Any

import anthropic
from PIL import Image

from .ingest import to_jpeg_base64


@lru_cache(maxsize=1)
def client() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=4, timeout=180)


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def image_blocks(images: list[Image.Image], max_side: int = 1800) -> list[dict[str, Any]]:
    blocks = []
    for i, img in enumerate(images):
        blocks.append({"type": "text", "text": f"Page {i + 1}:"})
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": to_jpeg_base64(img, max_side)},
        })
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


def call_structured(model: str, system: str, content: list[dict[str, Any]] | str, schema: dict[str, Any],
                    max_tokens: int = 8192, effort: str = "medium") -> tuple[dict[str, Any], dict[str, Any]]:
    t0 = time.perf_counter()
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": strict_schema(schema)}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}
    meta = {
        "latency_s": round(time.perf_counter() - t0, 3),
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "model": model,
        "stop_reason": resp.stop_reason,
    }
    return data, meta
