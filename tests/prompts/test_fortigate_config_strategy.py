"""
Tests for FortiGate dry-run strategy prompt builder.
"""

from gns3_copilot.prompts.fortigate_config_strategy import (
    DEFAULT_FORTIGATE_CONFIG_STRATEGY,
    FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS,
    FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS,
    FORTIGATE_STRATEGY_PERSONA_ONLY,
    FORTIGATE_STRATEGY_PREDEFINED_RULES,
    build_fortigate_strategy_prompt,
    get_fortigate_config_strategy,
    is_non_baseline_post_validation_enabled,
    normalize_fortigate_config_strategy,
    strategy_to_preview_source,
)


def test_normalize_fortigate_strategy_fallback_to_default() -> None:
    """Unknown strategy should fall back to default strategy."""
    assert normalize_fortigate_config_strategy("unknown") == DEFAULT_FORTIGATE_CONFIG_STRATEGY


def test_get_fortigate_config_strategy_reads_from_config_getter() -> None:
    """Getter should normalize value from injected config source."""
    strategy = get_fortigate_config_strategy(
        config_getter=lambda _key, _default: FORTIGATE_STRATEGY_PERSONA_ONLY
    )
    assert strategy == FORTIGATE_STRATEGY_PERSONA_ONLY


def test_non_baseline_post_validation_enabled_reads_from_config_getter() -> None:
    """Switch getter should parse truthy/falsy values."""
    assert (
        is_non_baseline_post_validation_enabled(
            config_getter=lambda _key, _default: "true"
        )
        is True
    )
    assert (
        is_non_baseline_post_validation_enabled(
            config_getter=lambda _key, _default: "false"
        )
        is False
    )


def test_strategy_to_preview_source_mapping() -> None:
    """Each strategy should map to strategy-specific source tag."""
    assert strategy_to_preview_source(FORTIGATE_STRATEGY_PREDEFINED_RULES) == "fortigate_predefined_rules"
    assert strategy_to_preview_source(FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS) == "fortigate_hybrid_min_constraints"
    assert strategy_to_preview_source(FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS) == "fortigate_hybrid_no_core_blocks"
    assert strategy_to_preview_source(FORTIGATE_STRATEGY_PERSONA_ONLY) == "fortigate_persona_only"


def test_build_predefined_rules_prompt_uses_legacy_template() -> None:
    """Predefined strategy should reuse the legacy FortiGate prompt template."""
    prompt = build_fortigate_strategy_prompt(strategy=FORTIGATE_STRATEGY_PREDEFINED_RULES)
    assert "FortiGate Dry-Run Configuration Requirements" in prompt
    assert "Required blocks: ip, route, policy" in prompt


def test_build_hybrid_min_prompt_contains_core_block_constraint() -> None:
    """Hybrid min strategy must explicitly require ip/route/policy core blocks."""
    prompt = build_fortigate_strategy_prompt(
        strategy=FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS
    )
    assert "core blocks: ip/route/policy" in prompt
    assert "Reserve `port1` for management only" in prompt


def test_build_hybrid_without_core_blocks_prompt_excludes_constraint() -> None:
    """Hybrid no-core strategy should not enforce the core block sentence."""
    prompt = build_fortigate_strategy_prompt(
        strategy=FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS
    )
    assert "core blocks: ip/route/policy" not in prompt
    assert "Reserve `port1` for management only" in prompt


def test_build_persona_only_prompt_has_persona_workflow_only() -> None:
    """Persona-only strategy should keep workflow rules without core constraints."""
    prompt = build_fortigate_strategy_prompt(strategy=FORTIGATE_STRATEGY_PERSONA_ONLY)
    assert "Persona-Only Strategy" in prompt
    assert "execute_multiple_device_config_commands" in prompt
    assert "Reserve `port1` for management only" not in prompt


def test_hybrid_prompt_uses_self_validation_text_when_post_validation_disabled() -> None:
    """Hybrid prompt should ask LLM self-validation when hard post-validation is off."""
    prompt = build_fortigate_strategy_prompt(
        strategy=FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS,
        non_baseline_post_validation=False,
    )
    assert "Hard post-validation is disabled for non-baseline strategies" in prompt
    assert "validation_status=incomplete" not in prompt


def test_hybrid_prompt_uses_validation_status_hint_when_post_validation_enabled() -> None:
    """Hybrid prompt should mention validation_status signal when switch is on."""
    prompt = build_fortigate_strategy_prompt(
        strategy=FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS,
        non_baseline_post_validation=True,
    )
    assert "validation_status=incomplete" in prompt
