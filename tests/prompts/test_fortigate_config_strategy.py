"""
Tests for FortiGate dry-run strategy prompt builder.
"""

from gns3_copilot.prompts.fortigate_config_strategy import (
    build_fortigate_strategy_prompt,
)


def test_build_persona_only_prompt_has_persona_workflow_only() -> None:
    """Persona-only strategy should include FortiGate safety and completeness rules."""
    prompt = build_fortigate_strategy_prompt()
    assert "Persona-Only Strategy" in prompt
    assert "execute_multiple_device_config_commands" in prompt
    assert "Reserve `port1` for management only" in prompt
    assert "`clarify_options` fenced JSON block" in prompt
    assert "self-validate the draft for completeness" in prompt
    assert "validator signals are audit-only" in prompt
