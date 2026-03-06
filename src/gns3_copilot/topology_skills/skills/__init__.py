"""Topology prompt skill implementations."""

from .base import (
    ClarificationOption,
    ClarificationQuestion,
    PromptSpec,
    SectionContribution,
    StepDefinition,
    TopologySkill,
)
from .fortigate_topology_skill import FortiGateTopologySkill
from .native_topology_skill import NativeTopologyPromptSkill

__all__ = [
    "TopologySkill",
    "PromptSpec",
    "ClarificationOption",
    "ClarificationQuestion",
    "SectionContribution",
    "StepDefinition",
    "NativeTopologyPromptSkill",
    "FortiGateTopologySkill",
]
