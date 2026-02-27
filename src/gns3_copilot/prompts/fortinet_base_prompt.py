"""
Fortinet baseline prompt injected for FortiGate scenarios.
"""

FORTINET_BASELINE_PROMPT = """
### Fortinet / FortiGate Baseline Rules

Apply these rules whenever the request involves FortiGate devices:

1. Keep `port1` reserved for management only.
   - Do not use `port1` for business IP interfaces.
   - Do not use `port1` in static route `set device`.
   - Do not use `port1` in firewall policy interfaces.

2. Before finalizing a FortiGate configuration, self-check completeness.
   - Ensure the proposal includes interface IP intent, routing intent, and policy intent.
   - If any required information is missing, ask concise follow-up questions first.

3. For every FortiGate configuration execution request, require explicit user confirmation.
   - Show the exact FortiGate CLI draft first.
   - Wait for user approval before executing `execute_multiple_device_config_commands`.
"""
