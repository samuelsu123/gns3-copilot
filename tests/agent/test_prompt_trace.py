"""
Tests for prompt trace writer.
"""

from pathlib import Path

import pytest

from gns3_copilot.agent import prompt_trace


@pytest.fixture(autouse=True)
def _reset_request_state() -> None:
    prompt_trace._REQUEST_STATE.clear()
    yield
    prompt_trace._REQUEST_STATE.clear()


def _sample_input_payload() -> list[dict]:
    return [
        {"type": "system", "content": "System line 1\nSystem line 2"},
        {"type": "human", "content": "请生成拓扑"},
    ]


def _sample_output_payload() -> dict:
    return {
        "type": "ai",
        "content": "好的，我先调用工具读取模板。",
        "tool_calls": [{"name": "get_gns3_templates", "args": {}, "id": "call_001"}],
    }


def test_start_trace_request_creates_directory_and_file(tmp_path: Path) -> None:
    """Start request should auto-create prompt_trace directory and session file."""
    prompt_trace.start_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        user_prompt="hello",
        trace_root=tmp_path,
    )

    trace_dir = tmp_path / "prompt_trace"
    trace_file = trace_dir / "session_thread-001.md"

    assert trace_dir.is_dir()
    assert trace_file.is_file()


def test_round_number_increments_within_same_request(tmp_path: Path) -> None:
    """LLM rounds in a request should increment from 1."""
    prompt_trace.start_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        user_prompt="hello",
        trace_root=tmp_path,
    )

    first_round = prompt_trace.append_llm_trace_round(
        thread_id="thread-001",
        request_id="req-001",
        model_tag="base_model",
        input_payload=_sample_input_payload(),
        output_payload=_sample_output_payload(),
        trace_root=tmp_path,
    )
    second_round = prompt_trace.append_llm_trace_round(
        thread_id="thread-001",
        request_id="req-001",
        model_tag="title_model",
        input_payload=_sample_input_payload(),
        output_payload=_sample_output_payload(),
        trace_root=tmp_path,
    )

    assert first_round["round_number"] == 1
    assert second_round["round_number"] == 2


def test_request_number_increments_across_session_requests(tmp_path: Path) -> None:
    """Requests should use increasing numbers in the same session file."""
    first_request = prompt_trace.start_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        user_prompt="first",
        trace_root=tmp_path,
    )
    prompt_trace.end_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        status="completed",
        trace_root=tmp_path,
    )

    second_request = prompt_trace.start_trace_request(
        thread_id="thread-001",
        request_id="req-002",
        user_prompt="second",
        trace_root=tmp_path,
    )

    assert first_request["request_number"] == 1
    assert second_request["request_number"] == 2


def test_markdown_contains_required_sections(tmp_path: Path) -> None:
    """Trace content should include the expected readable sections."""
    prompt_trace.start_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        user_prompt="please create topology",
        trace_root=tmp_path,
    )
    prompt_trace.append_llm_trace_round(
        thread_id="thread-001",
        request_id="req-001",
        model_tag="base_model",
        input_payload=_sample_input_payload(),
        output_payload=_sample_output_payload(),
        trace_root=tmp_path,
    )
    prompt_trace.end_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        status="completed",
        trace_root=tmp_path,
    )

    trace_file = tmp_path / "prompt_trace" / "session_thread-001.md"
    content = trace_file.read_text(encoding="utf-8")

    assert "## Request #1" in content
    assert "### Round 1 - base_model" in content
    assert "#### System Prompt" in content
    assert "#### User Prompt" in content
    assert "#### Output" in content
    assert "### Request Result" in content


def test_multiline_content_is_readable_not_json_escaped(tmp_path: Path) -> None:
    """Multiline prompts should be written as readable new lines, not '\\n' escapes."""
    prompt_trace.start_trace_request(
        thread_id="thread-001",
        request_id="req-001",
        user_prompt="line_a\nline_b",
        trace_root=tmp_path,
    )

    prompt_trace.append_llm_trace_round(
        thread_id="thread-001",
        request_id="req-001",
        model_tag="base_model",
        input_payload=[
            {"type": "system", "content": "system_a\nsystem_b"},
            {"type": "human", "content": "line_a\nline_b"},
        ],
        output_payload={"type": "ai", "content": "ok"},
        trace_root=tmp_path,
    )

    trace_file = tmp_path / "prompt_trace" / "session_thread-001.md"
    content = trace_file.read_text(encoding="utf-8")

    assert "line_a\nline_b" in content
    assert "\\nline_b" not in content
