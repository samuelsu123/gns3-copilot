"""
Core skill protocol and shared typed structures for topology prompt skills.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class PromptSpec(TypedDict, total=False):
    """Normalized topology intent draft used by skill runtime."""

    user_request: str
    uses_fortigate: bool
    lan_count: int
    use_switch: bool | None
    use_nat: bool | None
    include_license: bool | None
    fortigate_name: str
    fortigate_template: str
    dns_server: str
    license_restore_command: str


class ClarificationOption(TypedDict):
    """User-visible option rendered inside `clarify_options`."""

    id: str
    label: str
    value: str


class ClarificationQuestion(TypedDict, total=False):
    """
    Internal clarification question model.

    The fields `slot_name` / `slot_values` are runtime-only metadata and are
    intentionally excluded from user-facing payload.
    """

    kind: str
    question_id: str
    question: str
    options: list[ClarificationOption]
    allow_free_text: bool
    slot_name: str
    slot_values: dict[str, Any]


class StepDefinition(TypedDict):
    """One ordered execution step used by deterministic prompt renderer."""

    order: int
    title: str
    lines: list[str]
    code_block: str


class SectionContribution(TypedDict):
    """Skill contribution merged by runtime renderer."""

    nodes: list[str]
    links: list[str]
    steps: list[StepDefinition]
    rules: list[str]
    checklist: list[str]


class TopologySkill(Protocol):
    """
    Contract for topology prompt skills.

    约束说明（中文）:
    - `match` 决定技能是否激活
    - `next_question` 负责单轮补问
    - `contribute_sections` 只产出结构化片段，不直接拼最终 prompt
    """

    skill_id: str
    priority: int

    def match(self, spec: PromptSpec) -> bool:
        """Return True when this skill should be active for current spec."""

    def required_slots(self, spec: PromptSpec) -> tuple[str, ...]:
        """Return required slots this skill relies on."""

    def optional_slots(self, spec: PromptSpec) -> tuple[str, ...]:
        """Return optional slots this skill may ask user to confirm."""

    def next_question(
        self,
        spec: PromptSpec,
        asked_question_ids: set[str],
    ) -> ClarificationQuestion | None:
        """Return next single clarification question, or None when ready."""

    def contribute_sections(self, spec: PromptSpec) -> SectionContribution:
        """Return deterministic section contribution used for final rendering."""

    def validate(self, spec: PromptSpec, rendered_prompt: str) -> list[str]:
        """Return missing requirement list; empty list means valid."""
