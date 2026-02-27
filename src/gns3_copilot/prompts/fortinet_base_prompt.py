"""
Fortinet baseline prompt injected for FortiGate scenarios.
"""

from __future__ import annotations


def build_fortinet_baseline_prompt(include_completeness_intent: bool = True) -> str:
    """Build Fortinet baseline prompt with optional completeness-intent sentence."""
    completeness_line = (
        "   - Ensure the proposal includes interface IP intent, routing intent, and policy intent.\n"
        if include_completeness_intent
        else ""
    )
    prompt = f"""
### Fortinet / FortiGate Baseline Rules

Apply these rules whenever the request involves FortiGate devices:

1. Keep `port1` reserved for management only.
   - Do not use `port1` for business IP interfaces.
   - Do not use `port1` in static route `set device`.
   - Do not use `port1` in firewall policy interfaces.

2. Before finalizing a FortiGate configuration, self-check completeness.
{completeness_line}   - If any required information is missing, ask concise follow-up questions first.

3. For every FortiGate configuration execution request, require explicit user confirmation.
   - Show the exact FortiGate CLI draft first.
   - Wait for user approval before executing `execute_multiple_device_config_commands`.
"""
    return prompt.strip()


# Backward-compatible default export for existing call sites.
FORTINET_BASELINE_PROMPT = build_fortinet_baseline_prompt()
