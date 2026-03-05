"""Tests for native topology prompt helper module."""

from gns3_copilot.prompts.native_topology_prompt import (
    build_topology_intent_detection_prompt,
    is_native_topology_prompt_format,
    load_simple_fgt_reference,
    parse_topology_intent_result,
    validate_native_topology_prompt,
)


def test_load_simple_fgt_reference_returns_text() -> None:
    reference = load_simple_fgt_reference()
    assert isinstance(reference, str)
    assert len(reference) > 0
    assert "GNS3拓扑部署指令" in reference


def test_build_topology_intent_detection_prompt_mentions_json_schema() -> None:
    prompt = build_topology_intent_detection_prompt()
    assert "JSON" in prompt
    assert "is_topology_design_intent" in prompt


def test_parse_topology_intent_result_valid_json() -> None:
    flag, confidence = parse_topology_intent_result(
        '{"is_topology_design_intent": true, "confidence": 0.88, "reason": "x"}'
    )
    assert flag is True
    assert confidence == 0.88


def test_parse_topology_intent_result_handles_text_wrapper() -> None:
    raw = "```json\n{\"is_topology_design_intent\": false, \"confidence\": 0.12}\n```"
    flag, confidence = parse_topology_intent_result(raw)
    assert flag is False
    assert confidence == 0.12


def test_parse_topology_intent_result_invalid_json_falls_back() -> None:
    flag, confidence = parse_topology_intent_result("not a json")
    assert flag is False
    assert confidence == 0.0


def test_is_native_topology_prompt_format_true() -> None:
    text = """
## 节点清单
1. n1
## 链路清单
1. l1
## 执行步骤
step
## 执行规则
rule
## CRITICAL: 部署完成检查清单
check
"""
    assert is_native_topology_prompt_format(text) is True


def test_is_native_topology_prompt_format_false_when_missing_section() -> None:
    text = """
## 节点清单
1. n1
## 链路清单
1. l1
## 执行步骤
step
"""
    assert is_native_topology_prompt_format(text) is False


def test_validate_native_topology_prompt_detects_missing_fortigate_blocks() -> None:
    result = validate_native_topology_prompt(
        text=(
            "## 节点清单\n1. fgt\n## 链路清单\n1. x\n## 执行步骤\n"
            "使用 configure_node 配置\n## 执行规则\nr\n## CRITICAL: 部署完成检查清单\nc"
        ),
        user_request="请设计一个 FortiGate 拓扑",
    )
    assert result["ok"] is False
    missing = "\n".join(result["missing_requirements"])
    assert "config system interface" in missing
    assert "config router static" in missing
    assert "config firewall policy" in missing
