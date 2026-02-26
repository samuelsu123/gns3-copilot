"""
Dry-run simulation utilities for topology generation tools.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Callable

from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils import get_config

logger = setup_logger("topology_dry_run")

TOPOLOGY_DRY_RUN_CONFIG_KEY = "TOPOLOGY_DRY_RUN"

DRY_RUN_TOOL_NAMES = {
    "get_gns3_templates",
    "gns3_topology_reader",
    "create_gns3_node",
    "create_gns3_link",
    "start_gns3_node",
    "create_gns3_area_drawing",
    "execute_multiple_device_config_commands",
    "execute_multiple_device_commands",
}

TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSY_VALUES = {"0", "false", "no", "off"}
FORTIGATE_MGMT_PORT = "port1"
FORTIGATE_BUSINESS_PORT_FALLBACK = "port2"
FORTIGATE_REQUIRED_BLOCKS = ("ip", "route", "policy")


DEFAULT_DRY_RUN_TEMPLATES: list[dict[str, str]] = [
    {
        "name": "vpcs",
        "template_id": "dry-template-vpcs",
        "template_type": "vpcs",
    },
    {
        "name": "FortiGate-VM64-KVM",
        "template_id": "dry-template-fortigate",
        "template_type": "qemu",
    },
    {
        "name": "Cisco IOSv",
        "template_id": "dry-template-iosv",
        "template_type": "dynamips",
    },
    {
        "name": "Cisco IOSvL2",
        "template_id": "dry-template-iosvl2",
        "template_type": "dynamips",
    },
    {
        "name": "Ubuntu-Server",
        "template_id": "dry-template-ubuntu",
        "template_type": "qemu",
    },
    {
        "name": "Alpine-Linux",
        "template_id": "dry-template-alpine",
        "template_type": "docker",
    },
]


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    """Parse a loosely-typed configuration value into bool."""
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


def is_topology_dry_run_enabled(
    config_getter: Callable[[str, str | None], str] = get_config,
) -> bool:
    """Read dry-run switch from app configuration."""
    raw_value = config_getter(TOPOLOGY_DRY_RUN_CONFIG_KEY, "True")
    return parse_bool(raw_value, default=True)


def initialize_simulated_topology(
    selected_project: tuple[str, str, int, int, str] | None = None,
    existing_topology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or normalize dry-run topology state."""
    project_name = selected_project[0] if selected_project else "Dry Run Project"
    project_id = selected_project[1] if selected_project else "dry-run-project-id"
    project_status = selected_project[4] if selected_project else "opened"

    if (
        isinstance(existing_topology, dict)
        and existing_topology.get("project_id") == project_id
    ):
        topology = copy.deepcopy(existing_topology)
    else:
        topology = {
            "mode": "dry_run",
            "project_id": project_id,
            "project_name": project_name,
            "project_status": project_status,
            "templates": copy.deepcopy(DEFAULT_DRY_RUN_TEMPLATES),
            "nodes": [],
            "links": [],
            "drawings": [],
            "config_previews": [],
            "operation_log": [],
        }

    topology.setdefault("mode", "dry_run")
    topology.setdefault("project_id", project_id)
    topology.setdefault("project_name", project_name)
    topology.setdefault("project_status", project_status)
    topology.setdefault("templates", copy.deepcopy(DEFAULT_DRY_RUN_TEMPLATES))
    topology.setdefault("nodes", [])
    topology.setdefault("links", [])
    topology.setdefault("drawings", [])
    topology.setdefault("config_previews", [])
    topology.setdefault("operation_log", [])
    return topology


def build_topology_reader_output(simulated_topology: dict[str, Any]) -> dict[str, Any]:
    """Build an output payload compatible with gns3_topology_reader."""
    nodes_data = simulated_topology.get("nodes", [])
    links_data = simulated_topology.get("links", [])

    nodes: dict[str, dict[str, Any]] = {}
    for node in nodes_data:
        name = str(node.get("name", node.get("node_id", "unknown-node")))
        nodes[name] = {
            "node_id": node.get("node_id"),
            "name": node.get("name"),
            "status": node.get("status", "stopped"),
            "x": node.get("x", 0),
            "y": node.get("y", 0),
            "template_id": node.get("template_id"),
            "template_name": node.get("template_name"),
            "template_type": node.get("template_type"),
            "ports": [
                {
                    "name": port.get("name"),
                    "short_name": port.get("short_name"),
                }
                for port in node.get("ports", [])
            ],
        }

    return {
        "mode": "dry_run",
        "dry_run": True,
        "project_id": simulated_topology.get("project_id"),
        "name": simulated_topology.get("project_name", "Dry Run Project"),
        "status": simulated_topology.get("project_status", "opened"),
        "nodes": nodes,
        "links": copy.deepcopy(links_data),
        "drawings": copy.deepcopy(simulated_topology.get("drawings", [])),
        "config_previews": copy.deepcopy(simulated_topology.get("config_previews", [])),
        "stats": {
            "total_nodes": len(nodes_data),
            "total_links": len(links_data),
            "total_drawings": len(simulated_topology.get("drawings", [])),
            "total_config_previews": len(simulated_topology.get("config_previews", [])),
        },
    }


def execute_dry_run_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    simulated_topology: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Execute a dry-run tool and mutate topology state in-memory."""
    topology = copy.deepcopy(simulated_topology)

    if tool_name == "get_gns3_templates":
        observation = _dry_run_get_templates(topology)
    elif tool_name == "gns3_topology_reader":
        observation = _dry_run_topology_reader(tool_args, topology)
    elif tool_name == "create_gns3_node":
        observation = _dry_run_create_nodes(tool_args, topology)
    elif tool_name == "create_gns3_link":
        observation = _dry_run_create_links(tool_args, topology)
    elif tool_name == "start_gns3_node":
        observation = _dry_run_start_nodes(tool_args, topology)
    elif tool_name == "create_gns3_area_drawing":
        observation = _dry_run_create_area_drawing(tool_args, topology)
    elif tool_name == "execute_multiple_device_config_commands":
        observation = _dry_run_execute_config_commands(tool_args, topology)
    elif tool_name == "execute_multiple_device_commands":
        observation = _dry_run_execute_show_commands(tool_args, topology)
    else:
        observation = {
            "error": f"Dry-run mode does not support tool '{tool_name}'.",
        }

    return observation, topology


def _parse_tool_payload(tool_args: dict[str, Any]) -> dict[str, Any]:
    tool_input = tool_args.get("tool_input")

    if isinstance(tool_input, dict):
        return copy.deepcopy(tool_input)

    if isinstance(tool_input, str):
        text = tool_input.strip()
        if not text:
            return {}
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                return loaded
            return {"tool_input": loaded}
        except json.JSONDecodeError:
            return {}

    if isinstance(tool_args, dict):
        # gns3_topology_reader usually passes `project_id` directly.
        return copy.deepcopy(tool_args)

    return {}


def _dry_run_get_templates(topology: dict[str, Any]) -> dict[str, Any]:
    _append_operation(
        topology=topology,
        tool_name="get_gns3_templates",
        payload={},
        summary="Returned dry-run template catalog",
    )
    return {"templates": copy.deepcopy(topology.get("templates", []))}


def _dry_run_topology_reader(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    payload = _parse_tool_payload(tool_args)
    project_id = payload.get("project_id")
    if project_id and project_id != topology.get("project_id"):
        logger.warning(
            "Dry-run topology reader received project_id=%s, but simulated project_id=%s",
            project_id,
            topology.get("project_id"),
        )

    output = build_topology_reader_output(topology)
    _append_operation(
        topology=topology,
        tool_name="gns3_topology_reader",
        payload=payload,
        summary=f"Returned topology snapshot with {output['stats']['total_nodes']} node(s)",
    )
    return output


def _dry_run_create_nodes(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    payload = _parse_tool_payload(tool_args)
    project_id = payload.get("project_id")
    nodes_input = payload.get("nodes")

    if not project_id:
        return {"error": "Missing project_id."}
    if not isinstance(nodes_input, list) or not nodes_input:
        return {"error": "nodes must be a non-empty array."}

    templates_by_id = {
        template.get("template_id"): template for template in topology.get("templates", [])
    }

    created_nodes: list[dict[str, Any]] = []

    for i, node_data in enumerate(nodes_input):
        if not isinstance(node_data, dict):
            return {"error": f"Node {i + 1} must be a dictionary."}

        template_id = node_data.get("template_id")
        x = node_data.get("x")
        y = node_data.get("y")

        if not all([template_id, isinstance(x, (int, float)), isinstance(y, (int, float))]):
            return {"error": f"Node {i + 1} missing or invalid template_id, x, or y."}

        template = templates_by_id.get(template_id, {})
        template_name = str(template.get("name", "Unknown-Template"))
        template_type = str(template.get("template_type", "qemu"))

        if template_name == "Unknown-Template":
            inferred_name, inferred_type = _infer_template_from_template_id(
                str(template_id)
            )
            template_name = inferred_name
            template_type = inferred_type

        node_id = _next_identifier(topology, key="node", prefix="dry-node")
        node_name = _next_node_name(topology, _name_prefix(template_name, template_type))

        node_info = {
            "node_id": node_id,
            "name": node_name,
            "template_id": template_id,
            "template_name": template_name,
            "template_type": template_type,
            "x": x,
            "y": y,
            "status": "stopped",
            "ports": _build_ports(template_name=template_name, template_type=template_type),
        }
        topology["nodes"].append(node_info)
        created_nodes.append(
            {
                "node_id": node_id,
                "name": node_name,
                "status": "success",
            }
        )

    result = {
        "project_id": project_id,
        "created_nodes": created_nodes,
        "total_nodes": len(nodes_input),
        "successful_nodes": len(created_nodes),
        "failed_nodes": 0,
    }
    _append_operation(
        topology=topology,
        tool_name="create_gns3_node",
        payload=payload,
        summary=f"Created {len(created_nodes)} dry-run node(s)",
    )
    return result


def _dry_run_create_links(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> list[dict[str, Any]]:
    payload = _parse_tool_payload(tool_args)
    project_id = payload.get("project_id")
    links_input = payload.get("links")

    if not project_id:
        return [{"error": "Missing required field: project_id"}]
    if not isinstance(links_input, list) or not links_input:
        return [{"error": "Invalid links data: must be a non-empty array"}]

    created_links: list[dict[str, Any]] = []
    fallback_cursor = 0
    for index, link in enumerate(links_input):
        node_id1 = link.get("node_id1") if isinstance(link, dict) else None
        port1 = link.get("port1") if isinstance(link, dict) else None
        node_id2 = link.get("node_id2") if isinstance(link, dict) else None
        port2 = link.get("port2") if isinstance(link, dict) else None

        if not all([node_id1, port1, node_id2, port2]):
            created_links.append(
                {"error": f"Missing required fields in link definition {index}"}
            )
            continue

        node1 = _resolve_node_reference(topology, str(node_id1), fallback_cursor)
        if node1 is None:
            created_links.append({"error": f"Node not found in link {index}"})
            continue
        fallback_cursor += 1

        node2 = _resolve_node_reference(topology, str(node_id2), fallback_cursor)
        if node2 is None:
            created_links.append({"error": f"Node not found in link {index}"})
            continue
        fallback_cursor += 1

        if node1 is None or node2 is None:
            created_links.append({"error": f"Node not found in link {index}"})
            continue

        resolved_port1 = _resolve_port_name(node1, str(port1))
        resolved_port2 = _resolve_port_name(node2, str(port2))
        resolved_port1 = _allocate_fortigate_business_port(
            topology=topology,
            node=node1,
            requested_port=resolved_port1,
        )
        resolved_port2 = _allocate_fortigate_business_port(
            topology=topology,
            node=node2,
            requested_port=resolved_port2,
        )

        link_id = _next_identifier(topology, key="link", prefix="dry-link")
        link_info = {
            "link_id": link_id,
            "node_id1": str(node1.get("node_id")),
            "port1": resolved_port1,
            "node_id2": str(node2.get("node_id")),
            "port2": resolved_port2,
        }
        topology["links"].append(copy.deepcopy(link_info))
        created_links.append(link_info)

    success_count = len([item for item in created_links if "error" not in item])
    _append_operation(
        topology=topology,
        tool_name="create_gns3_link",
        payload=payload,
        summary=f"Created {success_count} dry-run link(s)",
    )
    return created_links


def _dry_run_start_nodes(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    payload = _parse_tool_payload(tool_args)
    project_id = payload.get("project_id")
    node_ids = payload.get("node_ids")

    if not project_id or not node_ids:
        return {"error": "Missing required fields: project_id and node_ids."}
    if not isinstance(node_ids, list):
        return {"error": "node_ids must be a list."}

    results = []
    fallback_cursor = 0
    for node_id in node_ids:
        node = _resolve_node_reference(topology, str(node_id), fallback_cursor)
        fallback_cursor += 1
        if node is None:
            results.append(
                {
                    "node_id": node_id,
                    "name": "N/A",
                    "status": "error",
                    "error": "Node not found in dry-run topology.",
                }
            )
            continue
        node["status"] = "started"
        results.append(
            {
                "node_id": node["node_id"],
                "name": node["name"],
                "status": node["status"],
            }
        )

    successful_nodes = [item for item in results if item.get("status") != "error"]
    failed_nodes = [item for item in results if item.get("status") == "error"]

    response = {
        "project_id": project_id,
        "total_nodes": len(node_ids),
        "successful": len(successful_nodes),
        "failed": len(failed_nodes),
        "nodes": results,
    }
    _append_operation(
        topology=topology,
        tool_name="start_gns3_node",
        payload=payload,
        summary=f"Started {len(successful_nodes)} dry-run node(s)",
    )
    return response


def _dry_run_create_area_drawing(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    payload = _parse_tool_payload(tool_args)
    project_id = payload.get("project_id")
    area_name = payload.get("area_name")
    node_names = payload.get("node_names")
    shape_type = payload.get("shape_type", "ellipse")

    if not project_id:
        return {"error": "Missing project_id."}
    if not area_name:
        return {"error": "Missing area_name."}
    if not isinstance(node_names, list) or not node_names:
        return {"error": "node_names must be a non-empty array."}
    if len(node_names) != 2:
        return {
            "error": (
                f"Exactly 2 nodes are required, got {len(node_names)}. "
                "Please provide exactly 2 node names."
            )
        }
    if shape_type not in {"ellipse", "rectangle"}:
        return {
            "error": f"Invalid shape_type '{shape_type}'. Must be 'ellipse' or 'rectangle'."
        }

    for node_name in node_names:
        if _find_node_by_name(topology, str(node_name)) is None:
            return {"error": f"Node '{node_name}' not found in project topology."}

    shape_drawing = {
        "drawing_id": _next_identifier(topology, key="drawing", prefix="dry-drawing"),
        "type": shape_type,
        "status": "success",
        "area_name": area_name,
    }
    text_drawing = {
        "drawing_id": _next_identifier(topology, key="drawing", prefix="dry-drawing"),
        "type": "text",
        "status": "success",
        "area_name": area_name,
    }
    topology["drawings"].append(copy.deepcopy(shape_drawing))
    topology["drawings"].append(copy.deepcopy(text_drawing))

    result = {
        "project_id": project_id,
        "area_name": area_name,
        "node_count": len(node_names),
        "nodes": node_names,
        "shape_type": shape_type,
        "created_drawings": [shape_drawing, text_drawing],
        "total_drawings": 2,
        "successful_drawings": 2,
        "failed_drawings": 0,
    }
    _append_operation(
        topology=topology,
        tool_name="create_gns3_area_drawing",
        payload=payload,
        summary=f"Created dry-run drawing for '{area_name}'",
    )
    return result


def _append_operation(
    topology: dict[str, Any],
    tool_name: str,
    payload: dict[str, Any],
    summary: str,
) -> None:
    topology["operation_log"].append(
        {
            "step": len(topology.get("operation_log", [])) + 1,
            "tool": tool_name,
            "payload": payload,
            "summary": summary,
        }
    )


def _parse_project_and_device_configs(
    tool_args: dict[str, Any], command_key: str
) -> tuple[str | None, list[dict[str, Any]]]:
    payload = _parse_tool_payload(tool_args)

    if isinstance(payload, dict):
        project_id = payload.get("project_id")
        device_configs = payload.get("device_configs", [])
        if isinstance(device_configs, list):
            return project_id, device_configs
        return project_id, []

    if isinstance(payload, list):
        return None, payload

    return None, []


def _dry_run_execute_config_commands(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> list[dict[str, Any]]:
    project_id, device_configs = _parse_project_and_device_configs(
        tool_args, "config_commands"
    )

    if not isinstance(device_configs, list) or not device_configs:
        return [{"error": "device_configs must be a non-empty array"}]

    preview_results: list[dict[str, Any]] = []

    for item in device_configs:
        if not isinstance(item, dict):
            preview_results.append({"error": "Each device config must be a dictionary"})
            continue

        device_name = str(item.get("device_name", "unknown-device"))
        commands = item.get("config_commands", [])
        if not isinstance(commands, list):
            commands = []
        is_fortigate = _is_fortigate_device(device_name=device_name, topology=topology)
        validation_status = "success"
        missing_requirements: list[str] = []
        status = "success"
        output = "Commands generated in dry-run mode (not executed on device)."
        source = "manual_preview"

        if is_fortigate:
            source = "fortigate_prompt_driven"
            validation_status, missing_requirements = _validate_fortigate_commands(
                commands=commands
            )
            if validation_status == "incomplete":
                status = "incomplete"
                missing_text = ", ".join(missing_requirements) or "unknown"
                output = (
                    "FortiGate config preview is incomplete in dry-run mode. "
                    f"Missing requirements: {missing_text}. "
                    "Ask follow-up questions and regenerate complete config preview."
                )

        preview = {
            "project_id": project_id or topology.get("project_id"),
            "device_name": device_name,
            "status": status,
            "validation_status": validation_status,
            "missing_requirements": missing_requirements,
            "recommended_next_step": (
                "ask_user_for_missing_requirements"
                if status == "incomplete"
                else "none"
            ),
            "source": source,
            "mode": "dry_run_preview_only",
            "config_commands": commands,
            "output": output,
        }
        preview_results.append(preview)
        topology["config_previews"].append(copy.deepcopy(preview))

    _append_operation(
        topology=topology,
        tool_name="execute_multiple_device_config_commands",
        payload={
            "project_id": project_id or topology.get("project_id"),
            "device_configs": device_configs,
        },
        summary=f"Generated {len(preview_results)} device config preview(s)",
    )

    return preview_results


def _is_fortigate_device(device_name: str, topology: dict[str, Any]) -> bool:
    lower_name = device_name.lower()
    if "forti" in lower_name or "fgt" in lower_name:
        return True

    node = _find_node_by_name(topology, device_name)
    if node is None:
        return False
    return _node_role(node) == "fortigate"


def _normalize_config_commands(commands: list[Any]) -> list[str]:
    normalized: list[str] = []
    for command in commands:
        text = str(command).strip()
        if text:
            normalized.append(text)
    return normalized


def _extract_edit_target(line: str) -> str | None:
    match = re.match(r'^edit\s+"?([^"]+)"?$', line.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip().lower()


def _extract_set_tokens(line: str, prefix: str) -> list[str]:
    if not line.lower().startswith(prefix.lower()):
        return []

    payload = line[len(prefix) :].strip()
    if not payload:
        return []

    tokens = [m.group(1) or m.group(2) for m in re.finditer(r'"([^"]+)"|(\S+)', payload)]
    return [str(token).strip().lower() for token in tokens if str(token).strip()]


def _analyze_fortigate_interface_block(commands: list[str]) -> tuple[bool, bool]:
    in_block = False
    current_port: str | None = None
    business_ports_with_ip: set[str] = set()
    mgmt_port_used = False

    for raw_line in commands:
        line = raw_line.lower()
        if line == "config system interface":
            in_block = True
            current_port = None
            continue
        if not in_block:
            continue
        if line == "end":
            break
        if line == "next":
            current_port = None
            continue
        if line.startswith("edit "):
            current_port = _extract_edit_target(raw_line)
            continue
        if line.startswith("set ip ") and current_port:
            if current_port == FORTIGATE_MGMT_PORT:
                mgmt_port_used = True
            else:
                business_ports_with_ip.add(current_port)

    has_required_ip = len(business_ports_with_ip) >= 2
    return has_required_ip, mgmt_port_used


def _analyze_fortigate_route_block(commands: list[str]) -> tuple[bool, bool]:
    in_block = False
    has_dst = False
    has_device = False
    device_port = ""
    valid_entries = 0
    mgmt_port_used = False

    def finalize_entry() -> tuple[bool, bool]:
        nonlocal has_dst, has_device, device_port, valid_entries, mgmt_port_used
        if has_dst and has_device:
            valid_entries += 1
        if device_port == FORTIGATE_MGMT_PORT:
            mgmt_port_used = True
        has_dst = False
        has_device = False
        device_port = ""
        return has_dst, has_device

    for raw_line in commands:
        line = raw_line.lower()
        if line == "config router static":
            in_block = True
            has_dst = False
            has_device = False
            device_port = ""
            continue
        if not in_block:
            continue
        if line == "end":
            finalize_entry()
            break
        if line.startswith("edit "):
            finalize_entry()
            continue
        if line == "next":
            finalize_entry()
            continue
        if line.startswith("set dst "):
            has_dst = True
            continue
        if line.startswith("set device "):
            tokens = _extract_set_tokens(raw_line, "set device ")
            if tokens:
                has_device = True
                device_port = tokens[0]

    return valid_entries >= 2, mgmt_port_used


def _analyze_fortigate_policy_block(commands: list[str]) -> tuple[bool, bool]:
    in_block = False
    has_srcintf = False
    has_dstintf = False
    has_accept = False
    entry_uses_mgmt = False
    valid_entries = 0
    mgmt_port_used = False

    def finalize_entry() -> None:
        nonlocal has_srcintf, has_dstintf, has_accept
        nonlocal entry_uses_mgmt, valid_entries, mgmt_port_used
        if has_srcintf and has_dstintf and has_accept:
            valid_entries += 1
        if entry_uses_mgmt:
            mgmt_port_used = True
        has_srcintf = False
        has_dstintf = False
        has_accept = False
        entry_uses_mgmt = False

    for raw_line in commands:
        line = raw_line.lower()
        if line == "config firewall policy":
            in_block = True
            has_srcintf = False
            has_dstintf = False
            has_accept = False
            entry_uses_mgmt = False
            continue
        if not in_block:
            continue
        if line == "end":
            finalize_entry()
            break
        if line.startswith("edit "):
            finalize_entry()
            continue
        if line == "next":
            finalize_entry()
            continue
        if line.startswith("set srcintf "):
            tokens = _extract_set_tokens(raw_line, "set srcintf ")
            has_srcintf = len(tokens) > 0
            if FORTIGATE_MGMT_PORT in tokens:
                entry_uses_mgmt = True
            continue
        if line.startswith("set dstintf "):
            tokens = _extract_set_tokens(raw_line, "set dstintf ")
            has_dstintf = len(tokens) > 0
            if FORTIGATE_MGMT_PORT in tokens:
                entry_uses_mgmt = True
            continue
        if line.startswith("set action "):
            tokens = _extract_set_tokens(raw_line, "set action ")
            has_accept = "accept" in tokens

    return valid_entries >= 2, mgmt_port_used


def _ordered_missing_requirements(missing: list[str]) -> list[str]:
    order = list(FORTIGATE_REQUIRED_BLOCKS) + ["mgmt_port_reserved"]
    ordered: list[str] = []
    for item in order:
        if item in missing:
            ordered.append(item)
    for item in missing:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _validate_fortigate_commands(commands: list[Any]) -> tuple[str, list[str]]:
    normalized_commands = _normalize_config_commands(commands)
    missing: list[str] = []

    has_ip, ip_uses_mgmt = _analyze_fortigate_interface_block(normalized_commands)
    has_route, route_uses_mgmt = _analyze_fortigate_route_block(normalized_commands)
    has_policy, policy_uses_mgmt = _analyze_fortigate_policy_block(normalized_commands)

    if not has_ip:
        missing.append("ip")
    if not has_route:
        missing.append("route")
    if not has_policy:
        missing.append("policy")
    if ip_uses_mgmt or route_uses_mgmt or policy_uses_mgmt:
        missing.append("mgmt_port_reserved")

    ordered_missing = _ordered_missing_requirements(missing)
    if ordered_missing:
        return "incomplete", ordered_missing
    return "success", []


def _dry_run_execute_show_commands(
    tool_args: dict[str, Any],
    topology: dict[str, Any],
) -> list[dict[str, Any]]:
    project_id, device_configs = _parse_project_and_device_configs(tool_args, "commands")

    if not isinstance(device_configs, list) or not device_configs:
        return [{"error": "device_configs must be a non-empty array"}]

    results: list[dict[str, Any]] = []

    for item in device_configs:
        if not isinstance(item, dict):
            results.append({"error": "Each device config must be a dictionary"})
            continue

        device_name = str(item.get("device_name", "unknown-device"))
        commands = item.get("commands", [])
        if not isinstance(commands, list):
            commands = []

        outputs = {
            str(cmd): (
                "[dry-run] command not executed. "
                "This is a preview-only response because topology dry-run mode is enabled."
            )
            for cmd in commands
        }
        results.append(
            {
                "project_id": project_id or topology.get("project_id"),
                "device_name": device_name,
                "status": "success",
                "mode": "dry_run_preview_only",
                "commands": commands,
                "output": outputs,
            }
        )

    _append_operation(
        topology=topology,
        tool_name="execute_multiple_device_commands",
        payload={
            "project_id": project_id or topology.get("project_id"),
            "device_configs": device_configs,
        },
        summary=f"Generated {len(results)} show-command preview result(s)",
    )

    return results


def _next_identifier(topology: dict[str, Any], key: str, prefix: str) -> str:
    if key == "node":
        existing = {str(node.get("node_id")) for node in topology.get("nodes", [])}
    elif key == "link":
        existing = {str(link.get("link_id")) for link in topology.get("links", [])}
    else:
        existing = {
            str(drawing.get("drawing_id")) for drawing in topology.get("drawings", [])
        }

    index = 1
    while True:
        candidate = f"{prefix}-{index:03d}"
        if candidate not in existing:
            return candidate
        index += 1


def _name_prefix(template_name: str, template_type: str) -> str:
    name = template_name.lower()
    if "fortigate" in name:
        return "FGT"
    if template_type == "vpcs" or "vpcs" in name or name.startswith("pc"):
        return "PC"
    if "switch" in name or "iosvl2" in name:
        return "SW"
    if "router" in name or "iosv" in name:
        return "R"
    return "NODE"


def _next_node_name(topology: dict[str, Any], prefix: str) -> str:
    used_names = {str(node.get("name")) for node in topology.get("nodes", [])}
    index = 1
    while True:
        candidate = f"{prefix}-{index}"
        if candidate not in used_names:
            return candidate
        index += 1


def _build_ports(template_name: str, template_type: str) -> list[dict[str, Any]]:
    lower_name = template_name.lower()

    if template_type == "vpcs" or "vpcs" in lower_name or lower_name.startswith("pc"):
        return [{"name": "Ethernet0", "short_name": "eth0"}]

    if "fortigate" in lower_name:
        return [
            {"name": "port1", "short_name": "p1"},
            {"name": "port2", "short_name": "p2"},
            {"name": "port3", "short_name": "p3"},
            {"name": "port4", "short_name": "p4"},
        ]

    return [
        {"name": "Ethernet0/0", "short_name": "e0/0"},
        {"name": "Ethernet0/1", "short_name": "e0/1"},
        {"name": "Ethernet0/2", "short_name": "e0/2"},
        {"name": "Ethernet0/3", "short_name": "e0/3"},
    ]


def _find_node_by_id(topology: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in topology.get("nodes", []):
        if str(node.get("node_id")) == node_id:
            return node
    return None


def _find_node_by_name(
    topology: dict[str, Any], node_name: str
) -> dict[str, Any] | None:
    for node in topology.get("nodes", []):
        if str(node.get("name")) == node_name:
            return node
    return None


def _has_port(node: dict[str, Any], port_name: str) -> bool:
    for port in node.get("ports", []):
        if str(port.get("name")) == port_name:
            return True
    return False


def _used_ports_for_node(topology: dict[str, Any], node_id: str) -> set[str]:
    used: set[str] = set()
    for link in topology.get("links", []):
        if str(link.get("node_id1")) == node_id:
            used.add(str(link.get("port1", "")))
        if str(link.get("node_id2")) == node_id:
            used.add(str(link.get("port2", "")))
    return used


def _allocate_fortigate_business_port(
    topology: dict[str, Any],
    node: dict[str, Any],
    requested_port: str,
) -> str:
    if _node_role(node) != "fortigate":
        return requested_port

    ports = [str(port.get("name")) for port in node.get("ports", []) if port.get("name")]
    business_ports = [port for port in ports if port != FORTIGATE_MGMT_PORT]
    if not business_ports:
        return requested_port

    used_ports = _used_ports_for_node(topology, str(node.get("node_id", "")))

    preferred_port = requested_port
    if preferred_port == FORTIGATE_MGMT_PORT or preferred_port not in business_ports:
        preferred_port = (
            FORTIGATE_BUSINESS_PORT_FALLBACK
            if FORTIGATE_BUSINESS_PORT_FALLBACK in business_ports
            else business_ports[0]
        )

    if preferred_port not in used_ports:
        return preferred_port

    for candidate in business_ports:
        if candidate not in used_ports:
            return candidate

    return preferred_port


def _infer_template_from_template_id(template_id: str) -> tuple[str, str]:
    """Infer template metadata from placeholder template IDs."""
    t = template_id.lower()
    if "forti" in t or "fgt" in t:
        return "FortiGate-VM64-KVM", "qemu"
    if "vpcs" in t or "pc" in t:
        return "vpcs", "vpcs"
    if "switch" in t or "iosvl2" in t:
        return "Cisco IOSvL2", "dynamips"
    if "router" in t or "iosv" in t:
        return "Cisco IOSv", "dynamips"
    return "Unknown-Template", "qemu"


def _node_role(node: dict[str, Any]) -> str:
    name = str(node.get("name", "")).lower()
    template_name = str(node.get("template_name", "")).lower()
    template_type = str(node.get("template_type", "")).lower()
    s = f"{name} {template_name} {template_type}"

    if "forti" in s or "fgt" in s:
        return "fortigate"
    if "pc" in s or "vpcs" in s:
        return "pc"
    if "switch" in s or "iosvl2" in s:
        return "switch"
    if "router" in s or "iosv" in s:
        return "router"
    return "node"


def _resolve_node_reference(
    topology: dict[str, Any], reference: str, fallback_index: int = 0
) -> dict[str, Any] | None:
    """Resolve node by id/name/placeholder alias in dry-run mode."""
    ref = reference.strip()
    if not ref:
        return None

    # 1) Exact node_id
    node = _find_node_by_id(topology, ref)
    if node is not None:
        return node

    # 2) Exact node name
    node = _find_node_by_name(topology, ref)
    if node is not None:
        return node

    nodes = topology.get("nodes", [])
    if not nodes:
        return None

    ref_lower = ref.lower()
    ref_alnum = re.sub(r"[^a-z0-9]", "", ref_lower)

    # 3) Pattern aliases: pc1-id, pc2, fortigate-id, r1, sw1, node3...
    m = re.search(r"(pc|fortigate|fgt|router|r|switch|sw|node)(\d+)", ref_alnum)
    if m:
        role_token = m.group(1)
        index = max(int(m.group(2)) - 1, 0)
        role = {
            "pc": "pc",
            "fortigate": "fortigate",
            "fgt": "fortigate",
            "router": "router",
            "r": "router",
            "switch": "switch",
            "sw": "switch",
            "node": "node",
        }.get(role_token, "node")

        candidates = [n for n in nodes if role == "node" or _node_role(n) == role]
        if candidates and index < len(candidates):
            return candidates[index]

    # 4) Textual aliases without index
    if any(token in ref_alnum for token in ("fortigate", "fgt")):
        for n in nodes:
            if _node_role(n) == "fortigate":
                return n
    if "pc" in ref_alnum:
        pcs = [n for n in nodes if _node_role(n) == "pc"]
        if pcs:
            return pcs[min(fallback_index, len(pcs) - 1)]
    if "router" in ref_alnum or re.fullmatch(r"r\d*", ref_alnum):
        routers = [n for n in nodes if _node_role(n) == "router"]
        if routers:
            return routers[min(fallback_index, len(routers) - 1)]
    if "switch" in ref_alnum or re.fullmatch(r"sw\d*", ref_alnum):
        switches = [n for n in nodes if _node_role(n) == "switch"]
        if switches:
            return switches[min(fallback_index, len(switches) - 1)]

    # 5) Final fallback by order to keep dry-run resilient
    if fallback_index < len(nodes):
        return nodes[fallback_index]
    return nodes[0]


def _resolve_port_name(node: dict[str, Any], requested_port: str) -> str:
    """Resolve a best-effort port name for dry-run link creation."""
    ports = [str(port.get("name")) for port in node.get("ports", []) if port.get("name")]
    if not ports:
        return requested_port

    # Exact match first
    if requested_port in ports:
        return requested_port

    role = _node_role(node)
    request = requested_port.lower().strip()
    request_alnum = re.sub(r"[^a-z0-9]", "", request)

    # Common alias mapping for placeholders
    if role == "pc":
        if request in {"port1", "eth0", "ethernet0/0"}:
            return ports[0]
        return ports[0]

    if role == "fortigate":
        if request.startswith("ethernet"):
            match = re.search(r"(\d+)$", request_alnum)
            if match:
                idx = int(match.group(1))
                # Ethernet0/0 -> port1
                target_idx = idx + 1
                candidate = f"port{target_idx}"
                if candidate in ports:
                    return candidate
        if request.startswith("port") and request in ports:
            return request
        if request.startswith("port"):
            match = re.search(r"(\d+)$", request_alnum)
            if match:
                candidate = f"port{int(match.group(1))}"
                if candidate in ports:
                    return candidate
        return ports[0]

    # Router/switch-like: support "port1" -> first interface
    if request.startswith("port"):
        match = re.search(r"(\d+)$", request_alnum)
        if match:
            idx = max(int(match.group(1)) - 1, 0)
            if idx < len(ports):
                return ports[idx]

    # Generic number-based fallback
    match = re.search(r"(\d+)$", request_alnum)
    if match:
        idx = int(match.group(1))
        if idx < len(ports):
            return ports[idx]
        idx = idx - 1
        if 0 <= idx < len(ports):
            return ports[idx]

    return ports[0]
