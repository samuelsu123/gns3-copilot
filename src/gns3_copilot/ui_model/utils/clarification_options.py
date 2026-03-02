"""
Helpers for parsing structured clarification-choice blocks from assistant text.
"""

from __future__ import annotations

import json
import re
from typing import TypedDict


CLARIFY_OPTIONS_BLOCK_RE = re.compile(
    r"```clarify_options\s*(\{.*?\})\s*```",
    flags=re.IGNORECASE | re.DOTALL,
)
CLARIFY_OPTIONS_APOSTROPHE_BLOCK_RE = re.compile(
    r"'''clarify_options\s*(\{.*?\})\s*'''",
    flags=re.IGNORECASE | re.DOTALL,
)


class ClarificationOption(TypedDict):
    """One selectable option in a clarification question."""

    id: str
    label: str
    value: str


class ClarificationQuestion(TypedDict):
    """Structured clarification question payload."""

    kind: str
    question_id: str
    question: str
    options: list[ClarificationOption]
    allow_free_text: bool


def _text_or_empty(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _validate_question_payload(payload: object) -> ClarificationQuestion | None:
    if not isinstance(payload, dict):
        return None

    kind = _text_or_empty(payload.get("kind"))
    question_id = _text_or_empty(payload.get("question_id"))
    question = _text_or_empty(payload.get("question"))

    if kind != "clarification_choice":
        return None
    if not question_id or not question:
        return None

    raw_options = payload.get("options")
    if not isinstance(raw_options, list):
        return None
    if len(raw_options) < 2 or len(raw_options) > 5:
        return None

    options: list[ClarificationOption] = []
    seen_ids: set[str] = set()
    for item in raw_options:
        if not isinstance(item, dict):
            return None

        option_id = _text_or_empty(item.get("id"))
        label = _text_or_empty(item.get("label"))
        value = _text_or_empty(item.get("value"))
        if not option_id or not label or not value:
            return None
        if option_id in seen_ids:
            return None
        seen_ids.add(option_id)
        options.append(
            {
                "id": option_id,
                "label": label,
                "value": value,
            }
        )

    allow_free_text = payload.get("allow_free_text", True)
    if not isinstance(allow_free_text, bool):
        allow_free_text = True

    return {
        "kind": kind,
        "question_id": question_id,
        "question": question,
        "options": options,
        "allow_free_text": allow_free_text,
    }


def _iter_json_object_spans(text: str) -> list[tuple[int, int, object]]:
    spans: list[tuple[int, int, object]] = []
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        start = text.find("{", cursor)
        if start < 0:
            break
        try:
            payload, end_offset = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue

        end = start + end_offset
        spans.append((start, end, payload))
        cursor = end
    return spans


def parse_clarification_question_from_text(text: str) -> ClarificationQuestion | None:
    """
    Parse the first valid `clarify_options` fenced JSON block from assistant text.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    for regex in (CLARIFY_OPTIONS_BLOCK_RE, CLARIFY_OPTIONS_APOSTROPHE_BLOCK_RE):
        for match in regex.finditer(text):
            raw_json = match.group(1).strip()
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                continue

            parsed = _validate_question_payload(payload)
            if parsed is not None:
                return parsed

    # Fallback: try parsing bare JSON object in text.
    for _start, _end, payload in _iter_json_object_spans(text):
        parsed = _validate_question_payload(payload)
        if parsed is not None:
            return parsed

    return None


def strip_clarification_blocks_from_text(text: str) -> str:
    """
    Remove clarification protocol blocks from assistant text for user-facing display.
    """
    if not isinstance(text, str) or not text:
        return ""

    cleaned = CLARIFY_OPTIONS_BLOCK_RE.sub("", text)
    cleaned = CLARIFY_OPTIONS_APOSTROPHE_BLOCK_RE.sub("", cleaned)

    removable_spans: list[tuple[int, int]] = []
    for start, end, payload in _iter_json_object_spans(cleaned):
        if _validate_question_payload(payload) is not None:
            removable_spans.append((start, end))

    if removable_spans:
        chunks: list[str] = []
        last = 0
        for start, end in removable_spans:
            chunks.append(cleaned[last:start])
            last = end
        chunks.append(cleaned[last:])
        cleaned = "".join(chunks)

    return cleaned.strip()
