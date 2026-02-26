"""
Tests for FortiGate dry-run prompt helpers.
"""

from langchain.messages import HumanMessage

from gns3_copilot.prompts.fortigate_config_prompt import (
    build_fortigate_dry_run_prompt,
    collect_incomplete_fortigate_requirements,
    should_inject_fortigate_prompt,
)


def test_should_inject_prompt_when_request_mentions_fortigate() -> None:
    """Prompt should be injected when user request mentions FortiGate."""
    messages = [HumanMessage(content="建2个pc通过1个fortigate相连的拓扑")]
    assert should_inject_fortigate_prompt(messages, topology_info=None) is True


def test_should_inject_prompt_when_topology_has_fortigate() -> None:
    """Prompt should be injected when topology already includes FortiGate node."""
    messages = [HumanMessage(content="帮我看下当前拓扑")]
    topology_info = {
        "nodes": {
            "FGT-1": {
                "name": "FGT-1",
                "template_name": "FortiGate-VM64-KVM",
                "template_type": "qemu",
            }
        }
    }
    assert should_inject_fortigate_prompt(messages, topology_info=topology_info) is True


def test_should_not_inject_prompt_when_no_fortigate_signal() -> None:
    """Prompt should not be injected for non-FortiGate scenarios."""
    messages = [HumanMessage(content="创建3个iosv路由器并连接")]
    topology_info = {
        "nodes": {
            "R-1": {
                "name": "R-1",
                "template_name": "Cisco IOSv",
                "template_type": "dynamips",
            }
        }
    }
    assert should_inject_fortigate_prompt(messages, topology_info=topology_info) is False


def test_collect_incomplete_fortigate_requirements_deduplicates_items() -> None:
    """Collector should deduplicate and merge incomplete requirements."""
    simulated_topology = {
        "config_previews": [
            {
                "device_name": "FGT-1",
                "source": "fortigate_prompt_driven",
                "validation_status": "incomplete",
                "missing_requirements": ["route", "policy"],
            },
            {
                "device_name": "FGT-1",
                "source": "fortigate_prompt_driven",
                "validation_status": "incomplete",
                "missing_requirements": ["policy", "ip"],
            },
        ]
    }
    missing = collect_incomplete_fortigate_requirements(simulated_topology)
    assert missing == ["route", "policy", "ip"]


def test_build_fortigate_dry_run_prompt_contains_required_instructions() -> None:
    """Generated prompt must include core FortiGate dry-run requirements."""
    simulated_topology = {
        "config_previews": [
            {
                "device_name": "FGT-1",
                "source": "fortigate_prompt_driven",
                "validation_status": "incomplete",
                "missing_requirements": ["route"],
            }
        ]
    }
    prompt = build_fortigate_dry_run_prompt(simulated_topology=simulated_topology)
    assert "execute_multiple_device_config_commands" in prompt
    assert "config system interface" in prompt
    assert "config router static" in prompt
    assert "config firewall policy" in prompt
    assert "Reserve `port1` for management only" in prompt
    assert "Latest missing requirements reported by validator: route" in prompt
