"""
Tests for FortiGate dry-run prompt helpers.
"""

from langchain.messages import HumanMessage

from gns3_copilot.prompts.fortigate_config_prompt import (
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
