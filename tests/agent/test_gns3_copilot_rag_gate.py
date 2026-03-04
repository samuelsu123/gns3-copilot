"""Tests for retrieval-first gate in agent llm_call flow."""

from __future__ import annotations

from langchain.messages import AIMessage, HumanMessage, ToolMessage

from gns3_copilot.agent import gns3_copilot as agent_module


class _FakeModel:
    def __init__(self, response: AIMessage) -> None:
        self._response = response
        self.invoked = 0

    def invoke(self, _messages):
        self.invoked += 1
        return self._response


def test_fortinet_query_auto_triggers_retrieval_tool(monkeypatch) -> None:
    def _should_not_invoke(_tools, **_kwargs):
        raise AssertionError("Model invocation is not expected before retrieval")

    monkeypatch.setattr(agent_module, "create_base_model_with_tools", _should_not_invoke)
    monkeypatch.setattr(agent_module, "_is_rag_enabled", lambda: True)
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "should_inject_fortigate_prompt",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        agent_module,
        "get_config",
        lambda key, default="": {
            "RAG_DEFAULT_PRODUCT": "fortigate",
            "RAG_DEFAULT_VERSION": "7.6.6",
            "RAG_TOP_K": "6",
        }.get(key, default),
    )

    state = {
        "messages": [HumanMessage(content="请给我 FortiGate policy 配置建议")],
        "llm_calls": 0,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert message.tool_calls
    assert message.tool_calls[0]["name"] == "fortinet_doc_search"
    assert message.tool_calls[0]["args"]["query"] == "请给我 FortiGate policy 配置建议"


def test_no_evidence_result_short_circuits_with_clarification(monkeypatch) -> None:
    def _should_not_invoke(_tools, **_kwargs):
        raise AssertionError("Model invocation is not expected when no evidence is returned")

    monkeypatch.setattr(agent_module, "create_base_model_with_tools", _should_not_invoke)
    monkeypatch.setattr(agent_module, "_is_rag_enabled", lambda: True)
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "should_inject_fortigate_prompt",
        lambda **_kwargs: True,
    )

    state = {
        "messages": [
            HumanMessage(content="fortigate route"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "fortinet_doc_search",
                        "args": {"query": "fortigate route"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content={
                    "query": "fortigate route",
                    "product": "fortigate",
                    "version": "7.6.6",
                    "no_evidence": True,
                    "hits": [],
                },
                tool_call_id="call_1",
                name="fortinet_doc_search",
            ),
        ],
        "llm_calls": 1,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert "没有在 `fortigate 7.6.6` 文档中检索到足够证据" in str(message.content)
    assert "clarify_options" in str(message.content)
    assert not message.tool_calls


def test_non_fortinet_query_falls_back_to_model(monkeypatch) -> None:
    fake_model = _FakeModel(AIMessage(content="normal answer"))

    monkeypatch.setattr(
        agent_module,
        "create_base_model_with_tools",
        lambda _tools, **_kwargs: fake_model,
    )
    monkeypatch.setattr(agent_module, "_is_rag_enabled", lambda: True)
    monkeypatch.setattr(agent_module, "is_topology_dry_run_enabled", lambda: True)
    monkeypatch.setattr(
        agent_module,
        "should_inject_fortigate_prompt",
        lambda **_kwargs: False,
    )

    state = {
        "messages": [HumanMessage(content="请检查 cisco ospf 邻居")],
        "llm_calls": 0,
        "selected_project": None,
        "simulated_topology": None,
    }

    result = agent_module.llm_call(state)
    message = result["messages"][0]

    assert isinstance(message, AIMessage)
    assert str(message.content) == "normal answer"
    assert fake_model.invoked == 1
