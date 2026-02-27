"""
Tests for Fortinet baseline prompt builder.
"""

from gns3_copilot.prompts.fortinet_base_prompt import (
    FORTINET_BASELINE_PROMPT,
    build_fortinet_baseline_prompt,
)


def test_build_default_baseline_prompt_contains_completeness_intent() -> None:
    """Default baseline prompt should include interface/routing/policy intent sentence."""
    prompt = build_fortinet_baseline_prompt()
    assert "interface IP intent, routing intent, and policy intent" in prompt
    assert "Keep `port1` reserved for management only" in prompt
    assert "require explicit user confirmation" in prompt


def test_build_persona_baseline_prompt_omits_completeness_intent() -> None:
    """Persona-only baseline should remove intent sentence but keep safety/confirmation rules."""
    prompt = build_fortinet_baseline_prompt(include_completeness_intent=False)
    assert "interface IP intent, routing intent, and policy intent" not in prompt
    assert "Keep `port1` reserved for management only" in prompt
    assert "If any required information is missing, ask concise follow-up questions first." in prompt
    assert "require explicit user confirmation" in prompt


def test_backward_compatible_constant_keeps_default_prompt() -> None:
    """Legacy constant should map to default baseline behavior."""
    assert FORTINET_BASELINE_PROMPT == build_fortinet_baseline_prompt()
