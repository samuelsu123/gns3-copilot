"""Tests for topology skill prompt helpers."""

from gns3_copilot.prompts.native_topology_prompt import (
    build_topology_skill_generation_prompt,
    load_topology_skill_markdown,
)


def test_load_topology_orchestrator_skill_markdown() -> None:
    content = load_topology_skill_markdown("topology-prompt-orchestrator")
    assert isinstance(content, str)
    assert "Topolog" in content or "拓扑" in content
    assert "clarify_options" in content


def test_load_fortigate_skill_markdown() -> None:
    content = load_topology_skill_markdown("fortigate-topology")
    assert isinstance(content, str)
    assert "FortiGate" in content
    assert "port1" in content


def test_build_topology_skill_generation_prompt_contains_skill_docs() -> None:
    orchestrator_doc = load_topology_skill_markdown("topology-prompt-orchestrator")
    prompt = build_topology_skill_generation_prompt(
        user_request="请设计总部和分支 FortiGate 互联拓扑",
        active_skill_documents=[
            ("topology-prompt-orchestrator", orchestrator_doc),
            ("fortigate-topology", "FortiGate skill body"),
        ],
        reference_prompt="example",
    )
    assert "Skill: topology-prompt-orchestrator" in prompt
    assert "Skill: fortigate-topology" in prompt
    assert "## 节点清单" in prompt
