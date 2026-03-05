"""
Tests for dry-run topology simulation helpers.
"""

import json

from gns3_copilot.agent.topology_dry_run import (
    build_topology_reader_output,
    execute_dry_run_tool,
    initialize_simulated_topology,
    is_topology_dry_run_enabled,
    parse_bool,
)


def test_parse_bool_variants() -> None:
    """Boolean parser should accept common truthy/falsy strings."""
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("false") is False
    assert parse_bool("0") is False
    assert parse_bool("no") is False
    assert parse_bool("unexpected", default=True) is True


def test_is_topology_dry_run_enabled_from_config_getter() -> None:
    """Dry-run switch should read from injected config getter."""
    assert is_topology_dry_run_enabled(lambda _k, _d: "true") is True
    assert is_topology_dry_run_enabled(lambda _k, _d: "false") is False


def test_dry_run_topology_workflow_end_to_end() -> None:
    """Simulated topology workflow should produce deterministic topology data."""
    simulated_topology = initialize_simulated_topology(
        ("DemoProject", "project-001", 0, 0, "opened")
    )

    templates_result, simulated_topology = execute_dry_run_tool(
        tool_name="get_gns3_templates",
        tool_args={},
        simulated_topology=simulated_topology,
    )
    templates = templates_result["templates"]
    vpcs_template_id = next(
        item["template_id"] for item in templates if item["name"] == "vpcs"
    )
    fgt_template_id = next(
        item["template_id"]
        for item in templates
        if item["name"] == "FortiGate-VM64-KVM"
    )

    create_nodes_input = {
        "project_id": "project-001",
        "nodes": [
            {"template_id": vpcs_template_id, "x": -300, "y": 0},
            {"template_id": vpcs_template_id, "x": 300, "y": 0},
            {"template_id": fgt_template_id, "x": 0, "y": 0},
        ],
    }
    nodes_result, simulated_topology = execute_dry_run_tool(
        tool_name="create_gns3_node",
        tool_args={"tool_input": json.dumps(create_nodes_input)},
        simulated_topology=simulated_topology,
    )
    assert nodes_result["successful_nodes"] == 3
    assert len(simulated_topology["nodes"]) == 3

    pc_nodes = sorted(
        [item for item in simulated_topology["nodes"] if item["name"].startswith("PC-")],
        key=lambda x: x["name"],
    )
    fgt_node = next(
        item for item in simulated_topology["nodes"] if item["name"].startswith("FGT-")
    )

    create_links_input = {
        "project_id": "project-001",
        "links": [
            {
                "node_id1": pc_nodes[0]["node_id"],
                "port1": "Ethernet0",
                "node_id2": fgt_node["node_id"],
                "port2": "port1",
            },
            {
                "node_id1": pc_nodes[1]["node_id"],
                "port1": "Ethernet0",
                "node_id2": fgt_node["node_id"],
                "port2": "port2",
            },
        ],
    }
    links_result, simulated_topology = execute_dry_run_tool(
        tool_name="create_gns3_link",
        tool_args={"tool_input": json.dumps(create_links_input)},
        simulated_topology=simulated_topology,
    )
    assert len([item for item in links_result if "error" not in item]) == 2
    assert len(simulated_topology["links"]) == 2

    start_nodes_input = {
        "project_id": "project-001",
        "node_ids": [item["node_id"] for item in simulated_topology["nodes"]],
    }
    start_result, simulated_topology = execute_dry_run_tool(
        tool_name="start_gns3_node",
        tool_args={"tool_input": json.dumps(start_nodes_input)},
        simulated_topology=simulated_topology,
    )
    assert start_result["failed"] == 0
    assert all(item["status"] == "started" for item in simulated_topology["nodes"])

    topology_result, _ = execute_dry_run_tool(
        tool_name="gns3_topology_reader",
        tool_args={"project_id": "project-001"},
        simulated_topology=simulated_topology,
    )
    assert topology_result["stats"]["total_nodes"] == 3
    assert topology_result["stats"]["total_links"] == 2
    assert topology_result["mode"] == "dry_run"


def test_dry_run_create_link_invalid_port_is_normalized() -> None:
    """Invalid port in link creation should be normalized to available port."""
    simulated_topology = initialize_simulated_topology(
        ("DemoProject", "project-002", 0, 0, "opened")
    )

    templates_result, simulated_topology = execute_dry_run_tool(
        tool_name="get_gns3_templates",
        tool_args={},
        simulated_topology=simulated_topology,
    )
    vpcs_template_id = next(
        item["template_id"]
        for item in templates_result["templates"]
        if item["name"] == "vpcs"
    )

    create_nodes_input = {
        "project_id": "project-002",
        "nodes": [
            {"template_id": vpcs_template_id, "x": -100, "y": 0},
            {"template_id": vpcs_template_id, "x": 100, "y": 0},
        ],
    }
    _, simulated_topology = execute_dry_run_tool(
        tool_name="create_gns3_node",
        tool_args={"tool_input": json.dumps(create_nodes_input)},
        simulated_topology=simulated_topology,
    )

    n1, n2 = simulated_topology["nodes"]
    create_links_input = {
        "project_id": "project-002",
        "links": [
            {
                "node_id1": n1["node_id"],
                "port1": "BadPort",
                "node_id2": n2["node_id"],
                "port2": "Ethernet0",
            }
        ],
    }
    links_result, _ = execute_dry_run_tool(
        tool_name="create_gns3_link",
        tool_args={"tool_input": json.dumps(create_links_input)},
        simulated_topology=simulated_topology,
    )
    assert "error" not in links_result[0]
    assert links_result[0]["port1"] == "Ethernet0"


def test_dry_run_placeholder_node_ids_are_resolved() -> None:
    """Placeholder ids like fortigate-id/pc1-id should be resolved in dry-run."""
    simulated_topology = initialize_simulated_topology(
        ("DemoProject", "project-004", 0, 0, "opened")
    )

    create_nodes_input = {
        "project_id": "project-004",
        "nodes": [
            {"template_id": "fortigate-template-id", "x": 0, "y": 0},
            {"template_id": "pc-template-id", "x": -100, "y": 0},
            {"template_id": "pc-template-id", "x": 100, "y": 0},
        ],
    }
    nodes_result, simulated_topology = execute_dry_run_tool(
        tool_name="create_gns3_node",
        tool_args={"tool_input": json.dumps(create_nodes_input)},
        simulated_topology=simulated_topology,
    )
    assert nodes_result["successful_nodes"] == 3

    create_links_input = {
        "project_id": "project-004",
        "links": [
            {
                "node_id1": "fortigate-id",
                "port1": "port1",
                "node_id2": "pc1-id",
                "port2": "port1",
            },
            {
                "node_id1": "fortigate-id",
                "port1": "port2",
                "node_id2": "pc2-id",
                "port2": "port1",
            },
        ],
    }
    links_result, simulated_topology = execute_dry_run_tool(
        tool_name="create_gns3_link",
        tool_args={"tool_input": json.dumps(create_links_input)},
        simulated_topology=simulated_topology,
    )
    assert len([item for item in links_result if "error" not in item]) == 2
    fortigate_ports = [item["port1"] for item in links_result if "error" not in item]
    assert "port1" not in fortigate_ports

    start_nodes_input = {
        "project_id": "project-004",
        "node_ids": ["fortigate-id", "pc1-id", "pc2-id"],
    }
    start_result, simulated_topology = execute_dry_run_tool(
        tool_name="start_gns3_node",
        tool_args={"tool_input": json.dumps(start_nodes_input)},
        simulated_topology=simulated_topology,
    )
    assert start_result["failed"] == 0
    assert start_result["successful"] == 3


def test_build_topology_reader_output_shape() -> None:
    """Reader output should contain gns3_topology_reader style keys."""
    simulated_topology = initialize_simulated_topology(
        ("DemoProject", "project-003", 0, 0, "opened")
    )
    topology_output = build_topology_reader_output(simulated_topology)

    assert topology_output["project_id"] == "project-003"
    assert "nodes" in topology_output
    assert "links" in topology_output
    assert "stats" in topology_output


def test_dry_run_config_tool_returns_preview_and_stores_it() -> None:
    """Config tool should return preview output and persist preview entries."""
    simulated_topology = initialize_simulated_topology(
        ("DemoProject", "project-005", 0, 0, "opened")
    )

    tool_input = {
        "project_id": "project-005",
        "device_configs": [
            {
                "device_name": "FGT-1",
                "config_commands": [
                    "config system interface",
                    "edit port2",
                    "set ip 10.10.1.1/24",
                    "next",
                    "edit port3",
                    "set ip 10.10.2.1/24",
                    "next",
                    "end",
                    "config router static",
                    "edit 1",
                    "set dst 10.10.1.0/24",
                    "set device port2",
                    "next",
                    "edit 2",
                    "set dst 10.10.2.0/24",
                    "set device port3",
                    "next",
                    "end",
                    "config firewall policy",
                    "edit 1",
                    "set srcintf port2",
                    "set dstintf port3",
                    "set action accept",
                    "next",
                    "edit 2",
                    "set srcintf port3",
                    "set dstintf port2",
                    "set action accept",
                    "next",
                    "end",
                ],
            }
        ],
    }
    result, simulated_topology = execute_dry_run_tool(
        tool_name="execute_multiple_device_config_commands",
        tool_args={"tool_input": json.dumps(tool_input)},
        simulated_topology=simulated_topology,
    )

    assert isinstance(result, list)
    assert result[0]["status"] == "success"
    assert result[0]["validation_status"] == "not_validated"
    assert result[0]["missing_requirements"] == []
    assert result[0]["source"] == "fortigate_persona_only"
    assert result[0]["fortigate_strategy"] == "persona_only"
    assert result[0]["mode"] == "dry_run_preview_only"
    assert len(simulated_topology["config_previews"]) == 1

    topology_output = build_topology_reader_output(simulated_topology)
    assert topology_output["stats"]["total_config_previews"] == 1


def test_dry_run_config_tool_persona_only_audit_only() -> None:
    """Persona-only strategy keeps validator as audit-only and does not drive LLM decisions."""
    simulated_topology = initialize_simulated_topology(
        ("DemoProject", "project-007", 0, 0, "opened")
    )
    tool_input = {
        "project_id": "project-007",
        "device_configs": [
            {
                "device_name": "FGT-1",
                "config_commands": [
                    "config system interface",
                    "edit port1",
                    "set ip 10.10.1.1/24",
                    "next",
                    "edit port3",
                    "set ip 10.10.2.1/24",
                    "next",
                    "end",
                    "config router static",
                    "edit 1",
                    "set dst 10.10.1.0/24",
                    "set device port1",
                    "next",
                    "edit 2",
                    "set dst 10.10.2.0/24",
                    "set device port3",
                    "next",
                    "end",
                    "config firewall policy",
                    "edit 1",
                    "set srcintf port1",
                    "set dstintf port3",
                    "set action accept",
                    "next",
                    "edit 2",
                    "set srcintf port3",
                    "set dstintf port1",
                    "set action accept",
                    "next",
                    "end",
                ],
            }
        ],
    }
    result, _ = execute_dry_run_tool(
        tool_name="execute_multiple_device_config_commands",
        tool_args={"tool_input": json.dumps(tool_input)},
        simulated_topology=simulated_topology,
    )
    assert result[0]["status"] == "success"
    assert result[0]["validation_status"] == "not_validated"
    assert result[0]["source"] == "fortigate_persona_only"
    assert result[0]["fortigate_strategy"] == "persona_only"
    assert result[0]["missing_requirements"] == []
    assert result[0]["recommended_next_step"] == "none"
