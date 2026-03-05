"""Tests for topology-intent confirmation flow in llm_call."""

from __future__ import annotations

from langchain.messages import AIMessage, HumanMessage

from gns3_copilot.agent import gns3_copilot as agent_module


def test_topology_intent_triggers_confirmation_question(monkeypatch) -> None:
    def _should_not_invoke(_tools, **_kwargs):
        raise AssertionError("Tool model should not be invoked before confirmation")

    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        _should_not_invoke,
    )
    monkeypatch.setattr(agent_module, "_detect_topology_prompt_intent_via_llm", lambda **_kwargs: True)
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(agent_module, "should_inject_fortigate_prompt", lambda **_kwargs: False)

    state = {
        "messages": [HumanMessage(content="请帮我设计并部署一个包含两个内网和一个外网的拓扑")],
        "llm_calls": 0,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert not message.tool_calls
    assert "是否现在生成这份完整 prompt" in str(message.content)
    assert result["pending_topology_prompt_request"]["user_request"].startswith("请帮我设计并部署")


def test_pending_topology_confirmation_yes_generates_prompt(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "_generate_native_topology_prompt_with_llm",
        lambda user_request, config=None: (
            "## 节点清单\n## 链路清单\n## 执行步骤\n## 执行规则\n## CRITICAL: 部署完成检查清单",
            [],
        ),
    )

    state = {
        "messages": [HumanMessage(content="是")],
        "llm_calls": 1,
        "selected_project": None,
        "simulated_topology": None,
        "pending_topology_prompt_request": {
            "user_request": "请设计一个 FortiGate 小型网络",
        },
        "pending_topology_prompt_context": {},
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "## 节点清单" in str(message.content)
    assert result["pending_topology_prompt_request"] is None
    assert result["pending_topology_prompt_context"] is None


def test_pending_topology_confirmation_yes_with_missing_requirements_keeps_pending(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "_generate_native_topology_prompt_with_llm",
        lambda user_request, config=None: (
            "bad prompt",
            ["缺少 FortiGate 配置关键项：`config system interface`"],
        ),
    )

    state = {
        "messages": [HumanMessage(content="是")],
        "llm_calls": 1,
        "selected_project": None,
        "simulated_topology": None,
        "pending_topology_prompt_request": {
            "user_request": "请设计一个 FortiGate 小型网络",
        },
        "pending_topology_prompt_context": {},
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "自动校验仍提示关键信息不完整" in str(message.content)
    assert result["pending_topology_prompt_request"]["user_request"] == "请设计一个 FortiGate 小型网络"


def test_pending_topology_confirmation_no_clears_pending(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)

    state = {
        "messages": [HumanMessage(content="否")],
        "llm_calls": 1,
        "selected_project": None,
        "simulated_topology": None,
        "pending_topology_prompt_request": {"user_request": "请设计拓扑"},
        "pending_topology_prompt_context": {},
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "先不生成完整拓扑 prompt" in str(message.content)
    assert result["pending_topology_prompt_request"] is None
    assert result["pending_topology_prompt_context"] is None


def test_pending_topology_confirmation_unknown_keeps_pending(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)

    state = {
        "messages": [HumanMessage(content="继续")],
        "llm_calls": 1,
        "selected_project": None,
        "simulated_topology": None,
        "pending_topology_prompt_request": {"user_request": "请设计拓扑"},
        "pending_topology_prompt_context": {"x": 1},
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "我还在等待你的确认" in str(message.content)
    assert result["pending_topology_prompt_request"]["user_request"] == "请设计拓扑"
    assert result["pending_topology_prompt_context"] == {"x": 1}
