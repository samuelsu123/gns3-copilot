"""
Prompt trace writer for LLM interaction observability.

This module persists readable Markdown traces under `prompt_trace/`,
organized by session thread id (one file per thread).
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

TRACE_DIR_NAME = "prompt_trace"
_REQUEST_HEADER_RE = re.compile(r"^## Request #(\d+)\s*$", re.MULTILINE)
_FILE_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")

_TRACE_LOCK = threading.RLock()
_REQUEST_STATE: dict[tuple[str, str], dict[str, Any]] = {}
_HTTP_TRACE_STATE: dict[tuple[str, str], dict[str, Any]] = {}


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_filename_fragment(raw: str) -> str:
    cleaned = _FILE_SAFE_RE.sub("_", raw).strip("._")
    return cleaned or "unknown"


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)


def _fenced_text(value: Any, fence_type: str = "text") -> str:
    text = _to_text(value).replace("```", "'''")
    return f"```{fence_type}\n{text}\n```"


def _resolve_trace_dir(trace_root: str | Path | None = None) -> Path:
    root = Path(trace_root) if trace_root is not None else Path.cwd()
    return root / TRACE_DIR_NAME


def _session_file_path(
    thread_id: str,
    trace_root: str | Path | None = None,
) -> Path:
    safe_thread_id = _safe_filename_fragment(thread_id)
    return _resolve_trace_dir(trace_root) / f"session_{safe_thread_id}.md"


def _http_trace_file_path(
    thread_id: str,
    request_id: str,
    trace_root: str | Path | None = None,
) -> Path:
    safe_thread_id = _safe_filename_fragment(thread_id)
    safe_request_id = _safe_filename_fragment(request_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"http_trace_{safe_thread_id}_{safe_request_id}_{timestamp}.md"
    return _resolve_trace_dir(trace_root) / filename


def _ensure_session_file(
    thread_id: str,
    trace_root: str | Path | None = None,
) -> Path:
    trace_dir = _resolve_trace_dir(trace_root)
    trace_dir.mkdir(parents=True, exist_ok=True)
    file_path = _session_file_path(thread_id=thread_id, trace_root=trace_root)
    if not file_path.exists():
        header = (
            "# Prompt Trace\n\n"
            f"- Thread ID: `{thread_id}`\n"
            f"- Created At: `{_now_str()}`\n\n"
        )
        file_path.write_text(header, encoding="utf-8")
    return file_path


def _next_request_number(file_path: Path) -> int:
    content = file_path.read_text(encoding="utf-8")
    matches = [int(match) for match in _REQUEST_HEADER_RE.findall(content)]
    if not matches:
        return 1
    return max(matches) + 1


def start_trace_request(
    thread_id: str,
    request_id: str,
    user_prompt: str,
    trace_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Start a request block in session trace file.
    """
    if not thread_id or not request_id:
        raise ValueError("thread_id and request_id are required")

    with _TRACE_LOCK:
        key = (thread_id, request_id)
        if key in _REQUEST_STATE:
            return _REQUEST_STATE[key]

        file_path = _ensure_session_file(thread_id=thread_id, trace_root=trace_root)
        request_number = _next_request_number(file_path)
        started_at = _now_str()

        block = [
            f"## Request #{request_number}",
            f"- Request ID: `{request_id}`",
            f"- Started At: `{started_at}`",
            "",
            "### User Prompt",
            _fenced_text(user_prompt),
            "",
        ]
        with file_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(block))

        state = {
            "request_number": request_number,
            "round_number": 0,
            "file_path": str(file_path),
        }
        _REQUEST_STATE[key] = state
        return state


def append_llm_trace_round(
    thread_id: str,
    request_id: str,
    model_tag: str,
    input_payload: list[dict[str, Any]],
    output_payload: dict[str, Any],
    trace_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Append one LLM interaction round inside an existing request block.
    """
    if not thread_id or not request_id:
        raise ValueError("thread_id and request_id are required")

    with _TRACE_LOCK:
        key = (thread_id, request_id)
        if key not in _REQUEST_STATE:
            start_trace_request(
                thread_id=thread_id,
                request_id=request_id,
                user_prompt="[implicit request]",
                trace_root=trace_root,
            )

        state = _REQUEST_STATE[key]
        state["round_number"] += 1
        round_number = state["round_number"]
        request_number = state["request_number"]
        file_path = Path(state["file_path"])

        system_messages = [
            payload for payload in input_payload if str(payload.get("type", "")).lower() == "system"
        ]
        non_system_messages = [
            payload for payload in input_payload if str(payload.get("type", "")).lower() != "system"
        ]
        latest_user_prompt = ""
        for payload in reversed(input_payload):
            role = str(payload.get("type", "")).lower()
            if role in {"human", "user"}:
                latest_user_prompt = _to_text(payload.get("content", ""))
                break

        output_role = str(output_payload.get("type", "unknown"))
        output_content = output_payload.get("content", "")
        output_tool_calls = output_payload.get("tool_calls")

        block: list[str] = [
            f"### Round {round_number} - {model_tag}",
            f"- Timestamp: `{_now_str()}`",
            f"- Model Tag: `{model_tag}`",
            "",
            "#### System Prompt",
        ]

        if system_messages:
            for idx, payload in enumerate(system_messages, start=1):
                block.extend(
                    [
                        f"##### System Message {idx}",
                        _fenced_text(payload.get("content", "")),
                        "",
                    ]
                )
        else:
            block.extend(
                [
                    "_No system prompt in this round._",
                    "",
                ]
            )

        block.extend(
            [
                "#### User Prompt",
                _fenced_text(latest_user_prompt),
                "",
                "#### Input Messages (Non-System)",
            ]
        )

        if non_system_messages:
            for idx, payload in enumerate(non_system_messages, start=1):
                role = str(payload.get("type", "unknown")).upper()
                block.extend(
                    [
                        f"##### Message {idx} - {role}",
                        _fenced_text(payload.get("content", "")),
                    ]
                )
                tool_calls = payload.get("tool_calls")
                if tool_calls:
                    block.extend(
                        [
                            "Tool Calls:",
                            _fenced_text(tool_calls, "json"),
                        ]
                    )
                block.append("")
        else:
            block.extend(
                [
                    "_No non-system input messages in this round._",
                    "",
                ]
            )

        block.extend(
            [
                "#### Output",
                f"- Role: `{output_role}`",
                _fenced_text(output_content),
                "",
            ]
        )

        if output_tool_calls:
            block.extend(
                [
                    "#### Output Tool Calls",
                    _fenced_text(output_tool_calls, "json"),
                    "",
                ]
            )

        with file_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(block))

        return {
            "request_number": request_number,
            "round_number": round_number,
            "file_path": str(file_path),
        }


def append_http_trace_round(
    thread_id: str,
    request_id: str,
    model_tag: str,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    trace_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Append one real HTTP API request/response round into a dedicated trace file.
    """
    if not thread_id or not request_id:
        raise ValueError("thread_id and request_id are required")

    with _TRACE_LOCK:
        key = (thread_id, request_id)
        state = _HTTP_TRACE_STATE.get(key)

        if state is None:
            trace_dir = _resolve_trace_dir(trace_root)
            trace_dir.mkdir(parents=True, exist_ok=True)
            file_path = _http_trace_file_path(
                thread_id=thread_id,
                request_id=request_id,
                trace_root=trace_root,
            )
            header = [
                "# HTTP API Trace",
                "",
                f"- Thread ID: `{thread_id}`",
                f"- Request ID: `{request_id}`",
                f"- Created At: `{_now_str()}`",
                "",
            ]
            file_path.write_text("\n".join(header), encoding="utf-8")
            state = {"round_number": 0, "file_path": str(file_path)}
            _HTTP_TRACE_STATE[key] = state

        state["round_number"] += 1
        round_number = state["round_number"]
        file_path = Path(state["file_path"])

        block = [
            f"## HTTP Round {round_number} - {model_tag}",
            f"- Timestamp: `{_now_str()}`",
            "",
            "### Request",
            _fenced_text(request_payload, "json"),
            "",
            "### Response",
            _fenced_text(response_payload, "json"),
            "",
        ]

        with file_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(block))

        return {
            "round_number": round_number,
            "file_path": str(file_path),
        }


def end_trace_request(
    thread_id: str,
    request_id: str,
    status: str,
    error_message: str | None = None,
    trace_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """
    End a request block and mark status.
    """
    if not thread_id or not request_id:
        return None

    normalized_status = status.strip().lower()
    if normalized_status not in {"completed", "failed"}:
        normalized_status = "completed"

    with _TRACE_LOCK:
        key = (thread_id, request_id)
        state = _REQUEST_STATE.pop(key, None)
        _HTTP_TRACE_STATE.pop(key, None)
        if state is None:
            return None

        file_path = Path(state["file_path"])
        block = [
            "### Request Result",
            f"- Status: `{normalized_status}`",
            f"- Ended At: `{_now_str()}`",
        ]
        if error_message:
            block.extend(
                [
                    "- Error:",
                    _fenced_text(error_message),
                ]
            )
        block.extend(["", "---", ""])

        with file_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(block))

        return {
            "request_number": state["request_number"],
            "round_number": state["round_number"],
            "file_path": str(file_path),
            "status": normalized_status,
        }


def append_fortigate_config_trace(
    thread_id: str,
    request_id: str,
    config_text: str,
    trace_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """
    Append pure FortiGate configuration text inside the current request block.
    """
    if not thread_id or not request_id:
        return None

    normalized = str(config_text).strip()
    if not normalized:
        return None

    with _TRACE_LOCK:
        key = (thread_id, request_id)
        state = _REQUEST_STATE.get(key)
        if state is None:
            return None

        file_path = Path(state["file_path"])
        if trace_root is not None:
            file_path = _session_file_path(thread_id=thread_id, trace_root=trace_root)

        block = [
            "### FortiGate Config",
            _fenced_text(normalized, "fortios"),
            "",
        ]
        with file_path.open("a", encoding="utf-8") as file:
            file.write("\n".join(block))

        return {
            "request_number": state["request_number"],
            "round_number": state["round_number"],
            "file_path": str(file_path),
        }
