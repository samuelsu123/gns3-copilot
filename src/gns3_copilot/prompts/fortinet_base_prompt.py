"""
Fortinet baseline prompt injected for FortiGate scenarios.
"""

from __future__ import annotations

from gns3_copilot.utils.app_config import get_config


def _build_rag_rule() -> str:
    """Build optional RAG usage rule when RAG is enabled."""
    rag_enabled = get_config("RAG_ENABLED", "False").lower() == "true"
    if not rag_enabled:
        return ""
    return (
        "\n4. When you are unsure about FortiOS CLI syntax or best practices, "
        "call the `search_fortinet_knowledge_base` tool to look up official documentation first.\n"
    )


def build_fortinet_baseline_prompt(include_completeness_intent: bool = True) -> str:
    """Build Fortinet baseline prompt with optional completeness-intent sentence."""
    completeness_line = (
        "   - Ensure the proposal includes interface IP intent, routing intent, and policy intent.\n"
        if include_completeness_intent
        else ""
    )
    rag_rule = _build_rag_rule()
    prompt = f"""
### Fortinet / FortiGate Baseline Rules

Apply these rules whenever the request involves FortiGate devices:

1. Keep `port1` reserved for management only.
   - Do not use `port1` for business IP interfaces.
   - Do not use `port1` in static route `set device`.
   - Do not use `port1` in firewall policy interfaces.

2. Before finalizing a FortiGate configuration, self-check completeness.
{completeness_line}   - If any required information is missing, ask concise follow-up questions first.
   - Ask exactly one question per turn and use a `clarify_options` fenced JSON block with 2-5 options.

3. For every FortiGate configuration execution request, require explicit user confirmation.
   - Show the exact FortiGate CLI draft first.
   - Wait for user approval before executing `execute_multiple_device_config_commands`.
{rag_rule}"""
    return prompt.strip()


# Backward-compatible default export for existing call sites.
FORTINET_BASELINE_PROMPT = build_fortinet_baseline_prompt()
