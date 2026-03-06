"""Unit tests for topology skill runtime."""

from __future__ import annotations

import re

from gns3_copilot.topology_skills import (
    advance_skill_session,
    create_default_skill_registry,
    initialize_skill_session,
    normalize_prompt_spec,
)


def test_skill_selection_for_non_fortigate_request() -> None:
    registry = create_default_skill_registry()
    spec = normalize_prompt_spec(
        user_request="请设计一个双内网拓扑，不需要防火墙",
        draft_spec={"uses_fortigate": False, "use_switch": True, "use_nat": False},
    )
    selected = registry.select(spec)
    assert [skill.skill_id for skill in selected] == ["native-topology-prompt-skill"]


def test_skill_selection_for_fortigate_request() -> None:
    registry = create_default_skill_registry()
    spec = normalize_prompt_spec(
        user_request="请设计一个 FortiGate 小型网络",
        draft_spec={"uses_fortigate": True, "use_switch": True, "use_nat": True},
    )
    selected = registry.select(spec)
    assert [skill.skill_id for skill in selected] == [
        "native-topology-prompt-skill",
        "fortigate-topology-skill",
    ]


def test_clarification_flow_switch_nat_license_then_complete() -> None:
    registry = create_default_skill_registry()
    session = initialize_skill_session(
        user_request="请设计一个 FortiGate 小型网络",
        draft_spec={"uses_fortigate": True, "lan_count": 2},
        registry=registry,
    )

    first = advance_skill_session(session=session, registry=registry)
    assert first["status"] == "need_clarification"
    assert first["question"]["question_id"] == "topology_use_switch"

    second = advance_skill_session(
        session=first["session"],
        user_answer="需要交换机",
        registry=registry,
    )
    assert second["status"] == "need_clarification"
    assert second["question"]["question_id"] == "topology_use_nat"

    third = advance_skill_session(
        session=second["session"],
        user_answer="需要 NAT",
        registry=registry,
    )
    assert third["status"] == "need_clarification"
    assert third["question"]["question_id"] == "fortigate_include_license"

    final = advance_skill_session(
        session=third["session"],
        user_answer="跳过 license 导入",
        registry=registry,
    )
    assert final["status"] == "completed"
    rendered = final["rendered_prompt"]
    assert "config system interface" in rendered
    assert "config router static" in rendered
    assert "config firewall policy" in rendered
    assert "execute restore vmlicense" not in rendered


def test_fortigate_render_keeps_port1_for_management_only() -> None:
    registry = create_default_skill_registry()
    session = initialize_skill_session(
        user_request="请生成 fortigate 拓扑",
        draft_spec={
            "uses_fortigate": True,
            "lan_count": 2,
            "use_switch": True,
            "use_nat": True,
            "include_license": False,
        },
        registry=registry,
    )
    result = advance_skill_session(session=session, registry=registry)
    assert result["status"] == "completed"
    rendered = result["rendered_prompt"].lower()
    assert "set device port1" in rendered
    assert "edit port1\nset mode static\nset ip 192.168.1.1" not in rendered


def test_renderer_step_count_is_consistent() -> None:
    registry = create_default_skill_registry()
    session = initialize_skill_session(
        user_request="请生成 fortigate 拓扑",
        draft_spec={
            "uses_fortigate": True,
            "lan_count": 2,
            "use_switch": True,
            "use_nat": True,
            "include_license": True,
        },
        registry=registry,
    )
    result = advance_skill_session(session=session, registry=registry)
    assert result["status"] == "completed"
    rendered = result["rendered_prompt"]

    step_count = len(re.findall(r"^### 步骤\d+：", rendered, flags=re.MULTILINE))
    assert step_count > 0

    match = re.search(
        r"所有\s+(\d+)\s+个步骤都完成后才算部署成功。",
        rendered,
    )
    assert match is not None
    assert int(match.group(1)) == step_count

    checklist_match = re.search(
        r"- \[ \] 全部\s+(\d+)\s+个执行步骤已完成且验证通过。",
        rendered,
    )
    assert checklist_match is not None
    assert int(checklist_match.group(1)) == step_count
