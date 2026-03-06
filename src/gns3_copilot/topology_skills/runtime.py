"""
Topology skill runtime for deterministic native prompt generation.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, TypedDict

from gns3_copilot.prompts.native_topology_prompt import (
    validate_native_topology_prompt,
)

from .skills import (
    ClarificationQuestion,
    PromptSpec,
    SectionContribution,
    TopologySkill,
)
from .skills.fortigate_topology_skill import FortiGateTopologySkill
from .skills.native_topology_skill import NativeTopologyPromptSkill


FORTIGATE_KEYWORDS = ("fortigate", "forti", "fgt", "防火墙")
YES_TOKENS = {"是", "需要", "要", "yes", "y", "true", "1", "ok", "继续"}
NO_TOKENS = {"否", "不要", "不需要", "no", "n", "false", "0", "取消"}
CHINESE_NUMBER_MAP = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
}


class TopologySkillSession(TypedDict, total=False):
    """Serializable runtime session stored inside LangGraph state."""

    user_request: str
    prompt_spec: PromptSpec
    active_skill_ids: list[str]
    asked_question_ids: list[str]
    pending_clarification_question: ClarificationQuestion | None
    phase: str


class SkillAdvanceResult(TypedDict, total=False):
    """Unified runtime step result for llm_call integration."""

    status: str
    session: TopologySkillSession
    prompt_spec: PromptSpec
    question: ClarificationQuestion | None
    clarification_message: str | None
    rendered_prompt: str | None
    missing_requirements: list[str]


class SkillRegistry:
    """In-memory registry that selects and resolves topology skills by priority."""

    def __init__(self, skills: list[TopologySkill]) -> None:
        ordered_skills = sorted(skills, key=lambda item: item.priority)
        self._skills = ordered_skills
        self._by_id = {skill.skill_id: skill for skill in ordered_skills}

    def select(self, spec: PromptSpec) -> list[TopologySkill]:
        return [skill for skill in self._skills if skill.match(spec)]

    def get(self, skill_id: str) -> TopologySkill | None:
        return self._by_id.get(skill_id)


def create_default_skill_registry() -> SkillRegistry:
    """Build default registry with core native skill and FortiGate sub-skill."""
    return SkillRegistry(
        skills=[
            NativeTopologyPromptSkill(),
            FortiGateTopologySkill(),
        ]
    )


def normalize_prompt_spec(
    user_request: str,
    draft_spec: dict[str, Any] | None = None,
) -> PromptSpec:
    """Normalize partial spec into a stable structure used by all skills."""
    draft = draft_spec or {}
    text = str(user_request or "").strip()
    lowered = text.lower()
    fortigate_draft = draft.get("fortigate", {})

    uses_fortigate = _to_bool(draft.get("uses_fortigate"))
    if uses_fortigate is None and isinstance(fortigate_draft, dict):
        uses_fortigate = _to_bool(
            fortigate_draft.get("required", fortigate_draft.get("enabled"))
        )
    if uses_fortigate is None:
        uses_fortigate = any(token in lowered for token in FORTIGATE_KEYWORDS)

    lan_count = _to_int(draft.get("lan_count"))
    if lan_count is None and isinstance(fortigate_draft, dict):
        lan_count = _to_int(fortigate_draft.get("lan_count"))
    if lan_count is None:
        lan_count = _extract_lan_count_from_text(text)
    if lan_count is None:
        lan_count = 2
    lan_count = max(1, min(4, lan_count))

    use_switch = _to_bool(draft.get("use_switch"))
    if use_switch is None:
        use_switch = _infer_optional_value(
            text=text,
            positive_patterns=("交换机", "switch"),
            negative_patterns=("不需要交换机", "不要交换机", "不使用交换机", "无交换机"),
        )

    use_nat = _to_bool(draft.get("use_nat"))
    if use_nat is None:
        use_nat = _infer_optional_value(
            text=text,
            positive_patterns=("nat", "外网", "上网"),
            negative_patterns=("不需要nat", "不要nat", "不使用nat", "无nat"),
        )

    include_license = _to_bool(draft.get("include_license"))
    if include_license is None and isinstance(fortigate_draft, dict):
        include_license = _to_bool(fortigate_draft.get("include_license"))
    if include_license is None and "license" in lowered and "不" not in lowered:
        include_license = True
    if not uses_fortigate:
        include_license = False

    fortigate_name = str(
        draft.get("fortigate_name")
        or (
            fortigate_draft.get("name")
            if isinstance(fortigate_draft, dict)
            else "fortigate1"
        )
        or "fortigate1"
    )
    fortigate_template = str(
        draft.get("fortigate_template")
        or (
            fortigate_draft.get("template")
            if isinstance(fortigate_draft, dict)
            else "FortiGate7.6.6模板"
        )
        or "FortiGate7.6.6模板"
    )

    dns_server = str(draft.get("dns_server") or "1.1.1.1")
    license_restore_command = str(
        draft.get("license_restore_command")
        or (
            fortigate_draft.get("license_restore_command")
            if isinstance(fortigate_draft, dict)
            else ""
        )
        or (
            "execute restore vmlicense ftp /aiops/licenses/FGVMULTM26000146.lic "
            "10.65.10.243 test test"
        )
    )

    return {
        "user_request": text,
        "uses_fortigate": bool(uses_fortigate),
        "lan_count": lan_count,
        "use_switch": use_switch,
        "use_nat": use_nat,
        "include_license": include_license,
        "fortigate_name": fortigate_name,
        "fortigate_template": fortigate_template,
        "dns_server": dns_server,
        "license_restore_command": license_restore_command,
    }


def initialize_skill_session(
    user_request: str,
    draft_spec: dict[str, Any] | None = None,
    registry: SkillRegistry | None = None,
) -> TopologySkillSession:
    """Create a fresh topology skill session from user request and optional draft."""
    skill_registry = registry or create_default_skill_registry()
    prompt_spec = normalize_prompt_spec(user_request=user_request, draft_spec=draft_spec)
    active_skills = skill_registry.select(prompt_spec)
    return {
        "user_request": str(user_request or "").strip(),
        "prompt_spec": prompt_spec,
        "active_skill_ids": [skill.skill_id for skill in active_skills],
        "asked_question_ids": [],
        "pending_clarification_question": None,
        "phase": "collecting",
    }


def advance_skill_session(
    session: TopologySkillSession,
    *,
    user_answer: str | None = None,
    registry: SkillRegistry | None = None,
) -> SkillAdvanceResult:
    """
    Advance runtime by one turn.

    关键流程（中文）:
    - 若有待回答问题，先解析用户本轮回复并写回 slot
    - 仅输出一个下一题（single-question protocol）
    - 所有 slot 满足后再渲染最终 prompt
    """
    skill_registry = registry or create_default_skill_registry()
    next_session = copy.deepcopy(session)
    prompt_spec = copy.deepcopy(next_session.get("prompt_spec", {}))
    next_session["prompt_spec"] = prompt_spec
    asked_question_ids = set(next_session.get("asked_question_ids", []))
    pending_question = next_session.get("pending_clarification_question")

    if user_answer is not None and isinstance(pending_question, dict):
        resolved, slot_value = _resolve_question_answer(
            question=pending_question,
            user_answer=user_answer,
        )
        if not resolved:
            message = build_clarification_message(
                pending_question,
                prefix="我没有识别到有效选项，请从按钮中选择，或输入等价表达。",
            )
            return {
                "status": "need_clarification",
                "session": next_session,
                "prompt_spec": prompt_spec,
                "question": pending_question,
                "clarification_message": message,
                "missing_requirements": [],
            }

        slot_name = str(pending_question.get("slot_name", "")).strip()
        if slot_name:
            prompt_spec[slot_name] = slot_value
        asked_question_ids.add(str(pending_question.get("question_id", "")).strip())
        next_session["asked_question_ids"] = sorted(
            [item for item in asked_question_ids if item]
        )
        next_session["pending_clarification_question"] = None

    active_skills = _active_skill_instances(next_session, skill_registry)
    for skill in active_skills:
        question = skill.next_question(prompt_spec, asked_question_ids)
        if question is None:
            continue
        next_session["pending_clarification_question"] = question
        message = build_clarification_message(question)
        return {
            "status": "need_clarification",
            "session": next_session,
            "prompt_spec": prompt_spec,
            "question": question,
            "clarification_message": message,
            "missing_requirements": [],
        }

    rendered_prompt = render_prompt_from_skills(
        prompt_spec=prompt_spec,
        skills=active_skills,
    )
    missing_requirements = validate_rendered_prompt(
        prompt_spec=prompt_spec,
        rendered_prompt=rendered_prompt,
        skills=active_skills,
    )
    if missing_requirements:
        return {
            "status": "invalid",
            "session": next_session,
            "prompt_spec": prompt_spec,
            "question": None,
            "clarification_message": None,
            "rendered_prompt": rendered_prompt,
            "missing_requirements": missing_requirements,
        }

    next_session["phase"] = "completed"
    next_session["pending_clarification_question"] = None
    return {
        "status": "completed",
        "session": next_session,
        "prompt_spec": prompt_spec,
        "question": None,
        "clarification_message": None,
        "rendered_prompt": rendered_prompt,
        "missing_requirements": [],
    }


def build_clarification_message(
    question: ClarificationQuestion,
    prefix: str | None = None,
) -> str:
    """Build assistant text containing one structured `clarify_options` block."""
    payload = {
        "kind": str(question.get("kind", "clarification_choice")),
        "question_id": str(question.get("question_id", "")),
        "question": str(question.get("question", "")),
        "options": question.get("options", []),
        "allow_free_text": bool(question.get("allow_free_text", True)),
    }
    head = prefix or "为保证最终拓扑 prompt 可直接执行，我需要你先确认一个选项。"
    return (
        f"{head}\n\n"
        f"```clarify_options\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def validate_rendered_prompt(
    *,
    prompt_spec: PromptSpec,
    rendered_prompt: str,
    skills: list[TopologySkill],
) -> list[str]:
    """Run skill-level and global section validation, then return deduped errors."""
    missing: list[str] = []
    for skill in skills:
        missing.extend(skill.validate(prompt_spec, rendered_prompt))

    global_validation = validate_native_topology_prompt(
        text=rendered_prompt,
        user_request=str(prompt_spec.get("user_request", "")),
    )
    missing.extend(global_validation.get("missing_requirements", []))
    return _dedupe(missing)


def render_prompt_from_skills(
    *,
    prompt_spec: PromptSpec,
    skills: list[TopologySkill],
) -> str:
    """Deterministically merge skill contributions and render final prompt text."""
    merged_nodes: list[str] = []
    merged_links: list[str] = []
    merged_steps: list[dict[str, Any]] = []
    merged_rules: list[str] = []
    merged_checklist: list[str] = []

    for skill in skills:
        contribution: SectionContribution = skill.contribute_sections(prompt_spec)
        merged_nodes.extend(contribution.get("nodes", []))
        merged_links.extend(contribution.get("links", []))
        merged_steps.extend(contribution.get("steps", []))
        merged_rules.extend(contribution.get("rules", []))
        merged_checklist.extend(contribution.get("checklist", []))

    nodes = _dedupe([str(item).strip() for item in merged_nodes if str(item).strip()])
    links = _dedupe([str(item).strip() for item in merged_links if str(item).strip()])
    rules = _dedupe([str(item).strip() for item in merged_rules if str(item).strip()])
    checklist = _dedupe(
        [str(item).strip() for item in merged_checklist if str(item).strip()]
    )
    ordered_steps = sorted(merged_steps, key=lambda step: int(step.get("order", 0)))

    lines: list[str] = [
        "# GNS3拓扑部署指令",
        "",
        "请在GNS3中部署以下测试拓扑。",
        "",
        "## 节点清单",
    ]
    for index, node in enumerate(nodes, start=1):
        lines.append(f"{index}. {node}")

    lines.extend(["", "## 链路清单"])
    for index, link in enumerate(links, start=1):
        lines.append(f"{index}. {link}")

    lines.extend(
        [
            "",
            "## 执行步骤",
            "",
            "**重要：严格按照以下顺序执行，必须完成所有步骤，不能提前停止。**",
            "",
        ]
    )
    for step_index, step in enumerate(ordered_steps, start=1):
        title = str(step.get("title", f"步骤{step_index}"))
        lines.append(f"### 步骤{step_index}：{title}")
        step_lines = step.get("lines", [])
        if isinstance(step_lines, list):
            for raw_line in step_lines:
                line = str(raw_line).rstrip()
                if line:
                    lines.append(line)

        code_block = str(step.get("code_block", "")).strip()
        if code_block:
            lines.append("```")
            lines.extend(code_block.splitlines())
            lines.append("```")
        lines.append("")

    lines.extend(["## 执行规则", ""])
    final_rules = list(rules)
    final_rules.append("严格按顺序执行，未完成当前步骤前不得进入下一步。")
    final_rules.append(f"所有 {len(ordered_steps)} 个步骤都完成后才算部署成功。")
    for index, rule in enumerate(_dedupe(final_rules), start=1):
        lines.append(f"{index}. {rule}")

    lines.extend(["", "## CRITICAL: 部署完成检查清单", ""])
    for item in checklist:
        lines.append(f"- [ ] {item}")
    lines.append(f"- [ ] 全部 {len(ordered_steps)} 个执行步骤已完成且验证通过。")

    lines.extend(
        [
            "",
            "**WARNING: 不要在中间步骤停止，必须在所有步骤完成并验证通过后才能结束。**",
        ]
    )
    return "\n".join(lines).strip()


def _active_skill_instances(
    session: TopologySkillSession,
    registry: SkillRegistry,
) -> list[TopologySkill]:
    skill_ids = session.get("active_skill_ids", [])
    active_skills: list[TopologySkill] = []
    for skill_id in skill_ids:
        skill = registry.get(skill_id)
        if skill is not None:
            active_skills.append(skill)
    return active_skills


def _resolve_question_answer(
    *,
    question: ClarificationQuestion,
    user_answer: str,
) -> tuple[bool, Any]:
    token = _normalize_token(user_answer)
    options = question.get("options", [])
    slot_values = question.get("slot_values", {})

    for option in options:
        option_id = str(option.get("id", "")).strip()
        candidates = {
            _normalize_token(option_id),
            _normalize_token(str(option.get("label", ""))),
            _normalize_token(str(option.get("value", ""))),
        }
        if token and token in candidates:
            if isinstance(slot_values, dict) and option_id in slot_values:
                return True, slot_values[option_id]
            return True, option.get("value")

    if bool(question.get("allow_free_text", True)):
        bool_guess = _resolve_bool_from_text(token)
        if bool_guess is not None and _question_expects_boolean(question):
            return True, bool_guess

    return False, None


def _question_expects_boolean(question: ClarificationQuestion) -> bool:
    slot_values = question.get("slot_values", {})
    if not isinstance(slot_values, dict) or not slot_values:
        return False
    return all(isinstance(value, bool) for value in slot_values.values())


def _resolve_bool_from_text(token: str) -> bool | None:
    if not token:
        return None
    if token in {_normalize_token(item) for item in YES_TOKENS}:
        return True
    if token in {_normalize_token(item) for item in NO_TOKENS}:
        return False
    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    token = _normalize_token(str(value))
    if token in {_normalize_token(item) for item in YES_TOKENS}:
        return True
    if token in {_normalize_token(item) for item in NO_TOKENS}:
        return False
    return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _extract_lan_count_from_text(text: str) -> int | None:
    lowered = str(text or "").lower()
    m = re.search(r"(\d+)\s*(个)?\s*(内网|局域网|lan)", lowered)
    if m:
        return _to_int(m.group(1))

    m = re.search(r"([一二两三四五])\s*个?\s*(内网|局域网|lan)", lowered)
    if m:
        return CHINESE_NUMBER_MAP.get(m.group(1))
    return None


def _infer_optional_value(
    *,
    text: str,
    positive_patterns: tuple[str, ...],
    negative_patterns: tuple[str, ...],
) -> bool | None:
    lowered = str(text or "").lower()
    if any(pattern in lowered for pattern in negative_patterns):
        return False
    if any(pattern in lowered for pattern in positive_patterns):
        return True
    return None


def _normalize_token(value: str) -> str:
    return "".join(str(value or "").strip().lower().split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = str(value).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output
