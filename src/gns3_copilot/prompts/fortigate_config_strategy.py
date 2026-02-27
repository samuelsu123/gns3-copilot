"""
FortiGate dry-run strategy prompt builder.
"""

from __future__ import annotations

from typing import Any, Callable

from gns3_copilot.utils import get_config

from .fortigate_config_prompt import (
    build_fortigate_dry_run_prompt,
    collect_incomplete_fortigate_requirements,
)

FORTIGATE_CONFIG_STRATEGY_KEY = "FORTIGATE_CONFIG_STRATEGY"
FORTIGATE_NON_BASELINE_POST_VALIDATION_KEY = (
    "FORTIGATE_NON_BASELINE_POST_VALIDATION"
)

FORTIGATE_STRATEGY_PREDEFINED_RULES = "predefined_rules"
FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS = "hybrid_min_constraints"
FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS = "hybrid_no_core_blocks"
FORTIGATE_STRATEGY_PERSONA_ONLY = "persona_only"

FORTIGATE_CONFIG_STRATEGIES = (
    FORTIGATE_STRATEGY_PREDEFINED_RULES,
    FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS,
    FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS,
    FORTIGATE_STRATEGY_PERSONA_ONLY,
)

DEFAULT_FORTIGATE_CONFIG_STRATEGY = FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS

TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSY_VALUES = {"0", "false", "no", "off"}

FORTIGATE_STRATEGY_TO_SOURCE = {
    FORTIGATE_STRATEGY_PREDEFINED_RULES: "fortigate_predefined_rules",
    FORTIGATE_STRATEGY_HYBRID_MIN_CONSTRAINTS: "fortigate_hybrid_min_constraints",
    FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS: "fortigate_hybrid_no_core_blocks",
    FORTIGATE_STRATEGY_PERSONA_ONLY: "fortigate_persona_only",
}


def normalize_fortigate_config_strategy(value: str | None) -> str:
    """Normalize strategy text to a supported value."""
    text = str(value or "").strip().lower()
    if text in FORTIGATE_CONFIG_STRATEGIES:
        return text
    return DEFAULT_FORTIGATE_CONFIG_STRATEGY


def get_fortigate_config_strategy(
    config_getter: Callable[[str, str | None], str] = get_config,
) -> str:
    """Read active FortiGate dry-run strategy from config."""
    raw_value = config_getter(
        FORTIGATE_CONFIG_STRATEGY_KEY,
        DEFAULT_FORTIGATE_CONFIG_STRATEGY,
    )
    return normalize_fortigate_config_strategy(raw_value)


def strategy_to_preview_source(strategy: str) -> str:
    """Map strategy name to preview source field."""
    normalized = normalize_fortigate_config_strategy(strategy)
    return FORTIGATE_STRATEGY_TO_SOURCE.get(
        normalized,
        FORTIGATE_STRATEGY_TO_SOURCE[DEFAULT_FORTIGATE_CONFIG_STRATEGY],
    )


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    text = str(value).strip().lower()
    if text in TRUTHY_VALUES:
        return True
    if text in FALSY_VALUES:
        return False
    return default


def is_non_baseline_post_validation_enabled(
    config_getter: Callable[[str, str | None], str] = get_config,
) -> bool:
    """Read non-baseline post-validation switch from app config."""
    raw_value = config_getter(FORTIGATE_NON_BASELINE_POST_VALIDATION_KEY, "False")
    return _parse_bool(raw_value, default=False)


def _build_missing_requirements_text(simulated_topology: dict[str, Any] | None) -> str:
    missing_requirements = collect_incomplete_fortigate_requirements(simulated_topology)
    return ", ".join(missing_requirements) if missing_requirements else "none"


def _build_hybrid_prompt(
    simulated_topology: dict[str, Any] | None,
    require_core_blocks: bool,
    post_validation_enabled: bool,
) -> str:
    missing_text = _build_missing_requirements_text(simulated_topology)

    core_constraints = ""
    if require_core_blocks:
        core_constraints = """
6. The preview must include all core blocks: ip/route/policy.
   - `config system interface` (business IPs)
   - `config router static` (interface static routes with both `set dst` and `set device`)
   - `config firewall policy` (allow policy for traffic between the two PC networks)
"""

    post_validation_instruction = (
        "8. If tool output reports `validation_status=incomplete`, do not finalize. "
        "Ask user for missing items and regenerate."
        if post_validation_enabled
        else "8. Hard post-validation is disabled for non-baseline strategies in current settings. "
        "You MUST self-validate configuration completeness before finalizing."
    )

    prompt = f"""
### FortiGate Dry-Run Hybrid Strategy

You are a senior network engineer and Fortinet/FortiGate expert.
You are handling a FortiGate scenario in TOPOLOGY_DRY_RUN mode.
Your response and generated preview MUST be directly usable for automation.

Workflow rules:
1. Build topology and links first.
2. You MUST call `execute_multiple_device_config_commands` in dry-run mode to generate FortiGate config preview.
3. `config_commands` MUST only contain native FortiGate CLI lines. No explanation text in config list.
4. Reserve `port1` for management only. Never use `port1` in business IP, static route device, or firewall policy interfaces.
5. Use business interfaces from `port2`/`port3` (and above if needed).
{core_constraints}7. If required info is missing, ask concise follow-up questions before claiming completion.
{post_validation_instruction}

Latest missing requirements reported by validator: {missing_text}
"""
    return prompt.strip()


def _build_persona_only_prompt(
    simulated_topology: dict[str, Any] | None,
    post_validation_enabled: bool,
) -> str:
    _ = simulated_topology
    _ = post_validation_enabled

    prompt = f"""
### FortiGate Dry-Run Persona-Only Strategy

You are a senior network engineer and Fortinet/FortiGate expert.
You are handling a FortiGate scenario in TOPOLOGY_DRY_RUN mode.

Workflow rules:
1. Build topology and links first.
2. You MUST call `execute_multiple_device_config_commands` in dry-run mode to generate FortiGate config preview.
3. `config_commands` MUST only contain native FortiGate CLI lines. No explanation text in config list.
4. Reserve `port1` for management only. Never use `port1` in business IP, static route device, or firewall policy interfaces.
5. Use business interfaces from `port2`/`port3` (and above if needed).
6. Before finalizing or asking for execution, self-validate the draft for completeness.
7. If required info or required config intent is missing, ask concise follow-up questions first.
8. In persona-only mode, backend validator signals are audit-only. LLM self-validation decides follow-up questions and regeneration.
"""
    return prompt.strip()


def build_fortigate_strategy_prompt(
    topology_info: dict[str, Any] | None = None,
    simulated_topology: dict[str, Any] | None = None,
    strategy: str | None = None,
    non_baseline_post_validation: bool | None = None,
) -> str:
    """Build FortiGate prompt according to active strategy."""
    resolved_strategy = (
        get_fortigate_config_strategy()
        if strategy is None
        else normalize_fortigate_config_strategy(strategy)
    )
    resolved_non_baseline_post_validation = (
        is_non_baseline_post_validation_enabled()
        if non_baseline_post_validation is None
        else bool(non_baseline_post_validation)
    )

    if resolved_strategy == FORTIGATE_STRATEGY_PREDEFINED_RULES:
        return build_fortigate_dry_run_prompt(
            topology_info=topology_info,
            simulated_topology=simulated_topology,
        )
    if resolved_strategy == FORTIGATE_STRATEGY_HYBRID_NO_CORE_BLOCKS:
        return _build_hybrid_prompt(
            simulated_topology=simulated_topology,
            require_core_blocks=False,
            post_validation_enabled=resolved_non_baseline_post_validation,
        )
    if resolved_strategy == FORTIGATE_STRATEGY_PERSONA_ONLY:
        return _build_persona_only_prompt(
            simulated_topology=simulated_topology,
            post_validation_enabled=resolved_non_baseline_post_validation,
        )
    return _build_hybrid_prompt(
        simulated_topology=simulated_topology,
        require_core_blocks=True,
        post_validation_enabled=resolved_non_baseline_post_validation,
    )
