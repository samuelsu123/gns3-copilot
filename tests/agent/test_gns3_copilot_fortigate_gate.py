"""
Tests for FortiGate execution confirmation gate in agent llm_call flow.
"""

import json

from langchain.messages import AIMessage, HumanMessage

from gns3_copilot.agent import gns3_copilot as agent_module


class _FakeModel:
    def __init__(self, response: AIMessage) -> None:
        self._response = response
        self.invoked = 0

    def invoke(self, _messages):
        self.invoked += 1
        return self._response


def _build_config_tool_call(device_name: str) -> dict:
    payload = {
        "project_id": "project-001",
        "device_configs": [
            {
                "device_name": device_name,
                "config_commands": [
                    "config system interface",
                    'edit "port2"',
                    "set ip 10.0.1.1 255.255.255.0",
                    "next",
                    "end",
                ],
            }
        ],
    }
    return {
        "name": "execute_multiple_device_config_commands",
        "args": {"tool_input": json.dumps(payload)},
        "id": "call_test_config_001",
        "type": "tool_call",
    }


def test_fortigate_tool_call_is_intercepted_and_requires_confirmation(monkeypatch) -> None:
    """FortiGate config tool call should be converted into a user confirmation turn."""
    monkeypatch.setattr(
        agent_module, "get_fortigate_config_strategy", lambda: "hybrid_min_constraints"
    )
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    fake_model = _FakeModel(
        AIMessage(content="", tool_calls=[_build_config_tool_call("FGT-1")])
    )
    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        lambda _tools: fake_model,
    )

    state = {
        "messages": [HumanMessage(content="请配置 fortigate 拓扑")],
        "llm_calls": 0,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert not message.tool_calls
    assert "确认执行" in str(message.content)
    assert "config system interface" in str(message.content)
    assert result["pending_fortigate_config_call"]["name"] == "execute_multiple_device_config_commands"
    assert "config system interface" in result["pending_fortigate_config_preview"]
    assert fake_model.invoked == 1


def test_persona_only_tool_call_is_intercepted_for_quality_review(monkeypatch) -> None:
    """Persona-only strategy should ask quality review before execution confirmation."""
    monkeypatch.setattr(agent_module, "get_fortigate_config_strategy", lambda: "persona_only")
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    fake_model = _FakeModel(
        AIMessage(content="", tool_calls=[_build_config_tool_call("FGT-1")])
    )
    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        lambda _tools: fake_model,
    )

    state = {
        "messages": [HumanMessage(content="请配置 fortigate 拓扑")],
        "llm_calls": 0,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert not message.tool_calls
    assert "质量确认" in str(message.content)
    assert "配置无问题" in str(message.content)
    assert result["pending_fortigate_quality_call"]["name"] == "execute_multiple_device_config_commands"
    assert "config system interface" in result["pending_fortigate_quality_preview"]
    assert result["pending_fortigate_config_call"] is None
    assert result["pending_fortigate_config_preview"] is None
    assert fake_model.invoked == 1


def test_persona_quality_pass_transitions_to_execution_confirmation(monkeypatch) -> None:
    """Quality pass response should move pending call into execution confirmation gate."""

    def _should_not_invoke(_tools):
        raise AssertionError("Model invocation is not expected while resolving quality gate")

    monkeypatch.setattr(agent_module, "create_base_model_with_tools", _should_not_invoke)
    pending_call = _build_config_tool_call("FGT-1")

    state = {
        "messages": [HumanMessage(content="没问题")],
        "llm_calls": 2,
        "selected_project": None,
        "simulated_topology": None,
        "pending_fortigate_quality_call": pending_call,
        "pending_fortigate_quality_preview": "config system interface\nend",
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert not message.tool_calls
    assert "确认执行" in str(message.content)
    assert result["pending_fortigate_quality_call"] is None
    assert result["pending_fortigate_quality_preview"] is None
    assert result["pending_fortigate_config_call"]["name"] == "execute_multiple_device_config_commands"
    assert "config system interface" in result["pending_fortigate_config_preview"]


def test_persona_quality_feedback_clears_pending_and_regenerates(monkeypatch) -> None:
    """Non-pass quality response should be treated as revision feedback and re-run LLM."""
    fake_model = _FakeModel(AIMessage(content="已根据反馈重新生成配置草案。"))
    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        lambda _tools: fake_model,
    )

    state = {
        "messages": [HumanMessage(content="把 port2 改成 192.168.10.1/24")],
        "llm_calls": 2,
        "selected_project": None,
        "simulated_topology": None,
        "pending_fortigate_quality_call": _build_config_tool_call("FGT-1"),
        "pending_fortigate_quality_preview": "config system interface\nend",
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "已根据反馈重新生成配置草案" in str(message.content)
    assert result["pending_fortigate_quality_call"] is None
    assert result["pending_fortigate_quality_preview"] is None
    assert fake_model.invoked == 1


def test_confirmation_executes_pending_fortigate_tool_call_without_new_llm_invoke(
    monkeypatch,
) -> None:
    """Explicit confirmation should execute pending tool call directly."""

    def _should_not_invoke(_tools):
        raise AssertionError("Model invocation is not expected for confirmed pending call")

    monkeypatch.setattr(agent_module, "create_base_model_with_tools", _should_not_invoke)
    pending_call = _build_config_tool_call("FGT-1")

    state = {
        "messages": [HumanMessage(content="确认执行")],
        "llm_calls": 3,
        "selected_project": None,
        "simulated_topology": None,
        "pending_fortigate_config_call": pending_call,
        "pending_fortigate_config_preview": "config system interface\nend",
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert message.tool_calls
    assert message.tool_calls[0]["name"] == "execute_multiple_device_config_commands"
    assert result["pending_fortigate_config_call"] is None
    assert result["pending_fortigate_config_preview"] is None


def test_cancel_clears_pending_fortigate_call(monkeypatch) -> None:
    """Cancel input should clear pending FortiGate config call."""

    def _should_not_invoke(_tools):
        raise AssertionError("Model invocation is not expected for canceled pending call")

    monkeypatch.setattr(agent_module, "create_base_model_with_tools", _should_not_invoke)
    pending_call = _build_config_tool_call("FGT-1")

    state = {
        "messages": [HumanMessage(content="取消执行")],
        "llm_calls": 3,
        "selected_project": None,
        "simulated_topology": None,
        "pending_fortigate_config_call": pending_call,
        "pending_fortigate_config_preview": "config system interface\nend",
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert not message.tool_calls
    assert "已取消" in str(message.content)
    assert result["pending_fortigate_config_call"] is None
    assert result["pending_fortigate_config_preview"] is None


def test_non_confirmation_keeps_pending_state_and_reminds_user(monkeypatch) -> None:
    """Non-confirmation input should keep pending call and request explicit decision."""

    def _should_not_invoke(_tools):
        raise AssertionError("Model invocation is not expected while waiting for confirmation")

    monkeypatch.setattr(agent_module, "create_base_model_with_tools", _should_not_invoke)
    pending_call = _build_config_tool_call("FGT-1")

    state = {
        "messages": [HumanMessage(content="继续")],
        "llm_calls": 3,
        "selected_project": None,
        "simulated_topology": None,
        "pending_fortigate_config_call": pending_call,
        "pending_fortigate_config_preview": "config system interface\nend",
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "待确认" in str(message.content)
    assert "确认执行" in str(message.content)
    assert "pending_fortigate_config_call" not in result
    assert "pending_fortigate_config_preview" not in result


def test_non_fortigate_config_call_is_not_intercepted(monkeypatch) -> None:
    """Non-FortiGate config call should keep normal tool execution path."""
    fake_model = _FakeModel(
        AIMessage(content="", tool_calls=[_build_config_tool_call("R-1")])
    )
    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        lambda _tools: fake_model,
    )

    state = {
        "messages": [HumanMessage(content="请配置路由器接口")],
        "llm_calls": 0,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert message.tool_calls
    assert message.tool_calls[0]["name"] == "execute_multiple_device_config_commands"
    assert "pending_fortigate_config_call" not in result
    assert "pending_fortigate_config_preview" not in result
    assert fake_model.invoked == 1
