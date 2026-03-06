"""Tests for topology-intent confirmation and skill-session flow in llm_call."""

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
    monkeypatch.setattr(
        agent_module, "_detect_topology_prompt_intent_via_llm", lambda **_kwargs: True
    )
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module, "should_inject_fortigate_prompt", lambda **_kwargs: False
    )

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
    assert result["pending_topology_prompt_request"]["user_request"].startswith(
        "请帮我设计并部署"
    )


def test_pending_topology_confirmation_yes_enters_skill_clarification(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "_extract_topology_prompt_spec_with_llm",
        lambda user_request, config=None: {
            "uses_fortigate": True,
            "lan_count": 2,
            "use_switch": None,
            "use_nat": None,
            "include_license": None,
        },
    )
    monkeypatch.setattr(
        agent_module,
        "_invoke_topology_skill_session_llm",
        lambda session, conversation_messages, config=None: {
            "status": "need_clarification",
            "output_text": (
                "请先确认。\n```clarify_options\n"
                '{"kind":"clarification_choice","question_id":"q1","question":"x?",'
                '"options":[{"id":"A","label":"a","value":"a"},{"id":"B","label":"b","value":"b"}],'
                '"allow_free_text":true}\n```'
            ),
            "missing_requirements": [],
            "session": session,
        },
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
    assert "clarify_options" in str(message.content)
    assert result["pending_topology_prompt_request"] is None
    assert isinstance(result["pending_topology_skill_session"], dict)
    assert result["pending_clarification_question"] is not None


def test_pending_topology_skill_session_with_complete_spec_generates_prompt(
    monkeypatch,
) -> None:
    def _should_not_invoke(_tools, **_kwargs):
        raise AssertionError("Tool model should not be invoked for active skill session")

    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        _should_not_invoke,
    )
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "_invoke_topology_skill_session_llm",
        lambda session, conversation_messages, config=None: {
            "status": "completed",
            "output_text": (
                "## 节点清单\n1. HQ-FGT\n## 链路清单\n1. x\n"
                "## 执行步骤\nstep\n## 执行规则\nrule\n## CRITICAL: 部署完成检查清单\ncheck"
            ),
            "missing_requirements": [],
            "session": session,
        },
    )

    state = {
        "messages": [HumanMessage(content="继续")],
        "llm_calls": 1,
        "selected_project": None,
        "simulated_topology": None,
        "pending_topology_skill_session": {
            "user_request": "请设计一个 FortiGate 小型网络",
            "active_skill_names": ["topology-prompt-orchestrator", "fortigate-topology"],
            "draft_spec": {"uses_fortigate": True},
            "round": 1,
        },
        "pending_clarification_question": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "## 节点清单" in str(message.content)
    assert "## 链路清单" in str(message.content)
    assert "## CRITICAL: 部署完成检查清单" in str(message.content)
    assert result["pending_topology_skill_session"] is None
    assert result["pending_clarification_question"] is None


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
    assert result["pending_topology_skill_session"] is None
    assert result["pending_clarification_question"] is None


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
