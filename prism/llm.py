"""Thin wrapper around Anthropic messages API for structured JSON output.

We request JSON via the system prompt and parse with Pydantic. This avoids
coupling to SDK-specific structured-output helpers that change between versions.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from prism.client import get_client


T = TypeVar("T", bound=BaseModel)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """Pull the first JSON object/array out of a model response.

    Tries code fences first, then falls back to finding a complete JSON object
    by counting braces.
    """
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1)

    # Fall back: find the first { and scan forward until braces balance.
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model response:\n{text[:500]}")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        c = text[i]

        if escape_next:
            escape_next = False
            continue

        if c == "\\" and in_string:
            escape_next = True
            continue

        if c == '"':
            in_string = not in_string
            continue

        if not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

    raise ValueError(f"No complete JSON object found in model response:\n{text[:500]}")


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in response.content:
        # Skip thinking blocks — they are not the final answer.
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def call_structured(
    *,
    model: str,
    system: str,
    user_content: str | list[dict],
    response_model: type[T],
    max_tokens: int = 8000,
    thinking: bool = False,
    effort: str | None = None,
    extra_system_blocks: list[dict] | None = None,
) -> T:
    """Call Claude and parse the JSON response into `response_model`.

    `user_content` may be a plain string or a list of content blocks
    (supports vision — pass image blocks alongside text).
    `extra_system_blocks` lets callers add cacheable system blocks.

    `thinking` and `effort` default to off; Haiku 4.5 does not support them.
    Only set them on Opus or Sonnet 4.6 calls.
    """
    client = get_client()

    schema = response_model.model_json_schema()
    json_instruction = (
        "\n\nReturn ONLY a single JSON object matching this schema. "
        "No prose, no fences.\n\n"
        f"Schema:\n```json\n{json.dumps(schema, indent=2)}\n```"
    )

    # Build system as list[blocks] so callers can attach cacheable blocks.
    system_blocks: list[dict] = [{"type": "text", "text": system + json_instruction}]
    if extra_system_blocks:
        system_blocks.extend(extra_system_blocks)

    if isinstance(user_content, str):
        messages = [{"role": "user", "content": user_content}]
    else:
        messages = [{"role": "user", "content": user_content}]

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_blocks,
        "messages": messages,
    }
    if effort is not None:
        kwargs["output_config"] = {"effort": effort}
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}

    # Stream to avoid request timeouts on long responses.
    with client.messages.stream(**kwargs) as stream:
        response = stream.get_final_message()

    text = _response_text(response)
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        raise RuntimeError(
            f"Response was truncated at max_tokens={max_tokens} (stop_reason=max_tokens). "
            f"Increase max_tokens for this agent.\nPartial text:\n{text[:1000]}"
        )

    # Parse, with one retry on malformed JSON (asks the model to fix its output).
    parse_err: Exception | None = None
    try:
        payload = json.loads(_extract_json(text))
    except (ValueError, json.JSONDecodeError) as e:
        parse_err = e

    if parse_err is not None:
        repair_messages = list(messages) + [
            {"role": "assistant", "content": text},
            {
                "role": "user",
                "content": (
                    f"Your previous JSON was malformed ({parse_err}). "
                    "Return the same payload but fix the JSON — no prose, no code fences, "
                    "valid JSON only."
                ),
            },
        ]
        repair_kwargs = dict(kwargs)
        repair_kwargs["messages"] = repair_messages
        with client.messages.stream(**repair_kwargs) as stream:
            response = stream.get_final_message()
        text = _response_text(response)
        try:
            payload = json.loads(_extract_json(text))
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(
                f"Failed to parse JSON after 1 retry (stop_reason={getattr(response, 'stop_reason', None)}).\n"
                f"Error: {e}\nFull response text ({len(text)} chars):\n{text}"
            ) from e

    # Pydantic validation also retries once if the first shape is slightly off
    # (e.g. missing optional field the model forgot — also a common Haiku quirk).
    try:
        return response_model.model_validate(payload)
    except Exception as validation_err:  # noqa: BLE001
        repair_messages = list(messages) + [
            {"role": "assistant", "content": json.dumps(payload)},
            {
                "role": "user",
                "content": (
                    f"Your JSON didn't match the schema: {validation_err}. "
                    "Fix the missing/invalid fields and return the corrected JSON only."
                ),
            },
        ]
        repair_kwargs = dict(kwargs)
        repair_kwargs["messages"] = repair_messages
        with client.messages.stream(**repair_kwargs) as stream:
            response = stream.get_final_message()
        text = _response_text(response)
        payload = json.loads(_extract_json(text))
        return response_model.model_validate(payload)
