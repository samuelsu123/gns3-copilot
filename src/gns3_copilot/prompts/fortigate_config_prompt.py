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

FORTIGATE_PREVIEW_SOURCE = "fortigate_persona_only"


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
