"""
Tests for global clarification choice prompt builder.
"""

from gns3_copilot.prompts.clarification_choice_prompt import (
    CLARIFICATION_CHOICE_PROMPT,
    build_clarification_choice_prompt,
)


def test_build_clarification_choice_prompt_contains_protocol_keywords() -> None:
    prompt = build_clarification_choice_prompt()
    assert "Ask exactly ONE question per turn" in prompt
    assert "`clarify_options`" in prompt
    assert '"kind": "clarification_choice"' in prompt
    assert "2-5 choices" in prompt


def test_default_constant_uses_builder_output() -> None:
    assert CLARIFICATION_CHOICE_PROMPT == build_clarification_choice_prompt()
