"""
FortiGate dry-run configuration prompt helpers.
"""

from __future__ import annotations

from typing import Any

FORTIGATE_KEYWORDS = (
    "fortigate",
    "forti",
    "fgt",
    "防火墙",
)

REQUIRED_FORTIGATE_BLOCKS = ("ip", "route", "policy")
FORTIGATE_PREVIEW_SOURCES = {
    "fortigate_prompt_driven",
    "fortigate_predefined_rules",
    "fortigate_hybrid_min_constraints",
    "fortigate_hybrid_no_core_blocks",
    "fortigate_persona_only",
}
FORTIGATE_PREVIEW_STRATEGIES = {
    "predefined_rules",
    "hybrid_min_constraints",
    "hybrid_no_core_blocks",
    "persona_only",
}


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or str(item)
                parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _messages_mention_fortigate(messages: list[Any] | None) -> bool:
    if not isinstance(messages, list):
        return False

    for message in reversed(messages):
        msg_type = str(getattr(message, "type", "")).lower()
        cls_name = message.__class__.__name__.lower()
        if msg_type and msg_type != "human" and "human" not in cls_name:
            continue

        text = _stringify_message_content(getattr(message, "content", ""))
        lowered = text.lower()
        if any(token in lowered for token in FORTIGATE_KEYWORDS):
            return True
    return False


def _topology_nodes_from_payload(topology_info: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(topology_info, dict):
        return []
    nodes = topology_info.get("nodes", {})
    if isinstance(nodes, dict):
        return [item for item in nodes.values() if isinstance(item, dict)]
    if isinstance(nodes, list):
        return [item for item in nodes if isinstance(item, dict)]
    return []


def _topology_has_fortigate(
    topology_info: dict[str, Any] | None,
    simulated_topology: dict[str, Any] | None = None,
) -> bool:
    candidate_nodes = _topology_nodes_from_payload(topology_info)
    if isinstance(simulated_topology, dict):
        nodes = simulated_topology.get("nodes", [])
        if isinstance(nodes, list):
            candidate_nodes.extend([item for item in nodes if isinstance(item, dict)])

    for node in candidate_nodes:
        data = " ".join(
            str(node.get(key, "")).lower()
            for key in ("name", "template_name", "template_type")
        )
        if any(token in data for token in ("forti", "fgt")):
            return True
    return False


def should_inject_fortigate_prompt(
    messages: list[Any] | None,
    topology_info: dict[str, Any] | None,
    simulated_topology: dict[str, Any] | None = None,
) -> bool:
    """Inject prompt if request text or topology indicates FortiGate usage."""
    return _messages_mention_fortigate(messages) or _topology_has_fortigate(
        topology_info, simulated_topology
    )


def collect_incomplete_fortigate_requirements(
    simulated_topology: dict[str, Any] | None,
) -> list[str]:
    """Collect missing requirements from latest FortiGate dry-run previews."""
    if not isinstance(simulated_topology, dict):
        return []

    previews = simulated_topology.get("config_previews", [])
    if not isinstance(previews, list):
        return []

    missing: list[str] = []
    for item in previews:
        if not isinstance(item, dict):
            continue

        device_name = str(item.get("device_name", "")).lower()
        source = str(item.get("source", "")).lower()
        strategy = str(item.get("fortigate_strategy", "")).lower()
        status = str(item.get("validation_status", "")).lower()

        is_fortigate_preview = (
            "forti" in device_name
            or "fgt" in device_name
            or source in FORTIGATE_PREVIEW_SOURCES
            or strategy in FORTIGATE_PREVIEW_STRATEGIES
        )
        if not is_fortigate_preview:
            continue
        if status != "incomplete":
            continue

        requirements = item.get("missing_requirements", [])
        if isinstance(requirements, list):
            for requirement in requirements:
                token = str(requirement).strip()
                if token and token not in missing:
                    missing.append(token)

    return missing


def build_fortigate_dry_run_prompt(
    topology_info: dict[str, Any] | None = None,
    simulated_topology: dict[str, Any] | None = None,
) -> str:
    """Build FortiGate-specific system prompt for dry-run configuration generation."""
    missing_requirements = collect_incomplete_fortigate_requirements(simulated_topology)
    missing_text = ", ".join(missing_requirements) if missing_requirements else "none"

    prompt = f""" 
### FortiGate Dry-Run Configuration Requirements

You are handling a FortiGate scenario in TOPOLOGY_DRY_RUN mode.
The generated preview MUST be directly usable as FortiGate CLI commands.

Strict workflow:
1. Build topology and links first.
2. You MUST call `execute_multiple_device_config_commands` in dry-run mode to generate FortiGate config preview.
3. `config_commands` MUST only contain native FortiGate CLI lines. No explanation text.
4. Reserve `port1` for management only. Never use `port1` in business IP, static route device, or firewall policy interfaces.
5. Use business interfaces from `port2`/`port3` (and above if needed).
6. Preview must include all blocks:
   - `config system interface` (business IPs)
   - `config router static` (interface static routes with both `set dst` and `set device`)
   - `config firewall policy` (allow policy for traffic between the two PC networks)
7. If required info is missing, ask concise follow-up questions before claiming completion.
8. If tool output reports `validation_status=incomplete`, do not finalize. Ask user for missing items and regenerate.

Latest missing requirements reported by validator: {missing_text}
Required blocks: {", ".join(REQUIRED_FORTIGATE_BLOCKS)}
"""
    return prompt.strip()



#静态路由 缺少 reserve
#你是xxx专家
