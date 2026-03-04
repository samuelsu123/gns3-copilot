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
   - Ask exactly one question per turn and use a `clarify_options` fenced JSON block with 2-5 options.

3. For every FortiGate configuration execution request, require explicit user confirmation.
   - Show the exact FortiGate CLI draft first.
   - Wait for user approval before executing `execute_multiple_device_config_commands`.

4. For Fortinet knowledge grounding, always search docs first with `fortinet_doc_search`.
   - Retrieve evidence before giving configuration guidance.
   - Cite source references (file + page) in your answer whenever evidence is found.
   - If no evidence is found, clearly say so and ask one concise clarification question.
"""
    return prompt.strip()


# Backward-compatible default export for existing call sites.
FORTINET_BASELINE_PROMPT = build_fortinet_baseline_prompt()
