"""
Generic topology prompt skill that always participates in prompt generation.
"""

from __future__ import annotations

from typing import Any

from .base import (
    ClarificationQuestion,
    PromptSpec,
    SectionContribution,
    StepDefinition,
    TopologySkill,
)


class NativeTopologyPromptSkill(TopologySkill):
    """Core skill that builds stable topology skeleton and optional component Q&A."""

    skill_id = "native-topology-prompt-skill"
    priority = 10

    def match(self, spec: PromptSpec) -> bool:
        return bool(spec.get("user_request", "").strip())

    def required_slots(self, spec: PromptSpec) -> tuple[str, ...]:
        return ()

    def optional_slots(self, spec: PromptSpec) -> tuple[str, ...]:
        return ("use_switch", "use_nat")

    def next_question(
        self,
        spec: PromptSpec,
        asked_question_ids: set[str],
    ) -> ClarificationQuestion | None:
        use_switch = spec.get("use_switch")
        if use_switch is None and "topology_use_switch" not in asked_question_ids:
            return {
                "kind": "clarification_choice",
                "question_id": "topology_use_switch",
                "question": "该拓扑是否需要添加交换机作为外网汇聚节点？",
                "options": [
                    {"id": "A", "label": "需要交换机", "value": "需要交换机"},
                    {"id": "B", "label": "不需要交换机", "value": "不需要交换机"},
                ],
                "allow_free_text": True,
                "slot_name": "use_switch",
                "slot_values": {"A": True, "B": False},
            }

        use_nat = spec.get("use_nat")
        if use_nat is None and "topology_use_nat" not in asked_question_ids:
            return {
                "kind": "clarification_choice",
                "question_id": "topology_use_nat",
                "question": "该拓扑是否需要 NAT 节点用于外网访问？",
                "options": [
                    {"id": "A", "label": "需要 NAT", "value": "需要 NAT"},
                    {"id": "B", "label": "不需要 NAT", "value": "不需要 NAT"},
                ],
                "allow_free_text": True,
                "slot_name": "use_nat",
                "slot_values": {"A": True, "B": False},
            }

        return None

    def contribute_sections(self, spec: PromptSpec) -> SectionContribution:
        uses_fortigate = bool(spec.get("uses_fortigate", False))
        lan_count = int(spec.get("lan_count", 2) or 2)
        use_switch = bool(spec.get("use_switch", False))
        use_nat = bool(spec.get("use_nat", False))
        fortigate_name = str(spec.get("fortigate_name", "fortigate1") or "fortigate1")

        nodes: list[str] = [f"PC{index} - VPCS模板" for index in range(1, lan_count + 1)]
        if uses_fortigate:
            template_name = str(
                spec.get("fortigate_template", "FortiGate7.6.6模板")
                or "FortiGate7.6.6模板"
            )
            nodes.append(f"{fortigate_name} - {template_name}")
        else:
            nodes.append("router1 - Router模板")
        if use_nat:
            nodes.append("nat1 - NAT模板")
        if use_switch:
            nodes.append("switch1 - Ethernet switch模板")

        links = self._build_links(
            uses_fortigate=uses_fortigate,
            lan_count=lan_count,
            use_switch=use_switch,
            use_nat=use_nat,
            fortigate_name=fortigate_name,
        )

        steps: list[StepDefinition] = [
            {
                "order": 10,
                "title": "创建所有节点并启动",
                "lines": [
                    f"- 使用 create_node 创建以下节点：{', '.join(self._node_names(nodes))}",
                    "- 使用 start_all_nodes 启动所有节点",
                ],
                "code_block": "",
            },
            {
                "order": 20,
                "title": "创建所有链路",
                "lines": [
                    f"- 使用 create_link 创建以下 {len(links)} 条链路：",
                    *[f"  * {link}" for link in links],
                ],
                "code_block": "",
            },
            {
                "order": 30,
                "title": "等待所有节点就绪",
                "lines": [
                    "- **必须调用 wait_for_nodes_ready(timeout=600)**",
                    "- **必须等待该步骤成功后才能继续后续配置**",
                ],
                "code_block": "",
            },
        ]

        if uses_fortigate:
            steps.append(
                {
                    "order": 80,
                    "title": "配置 PC 地址",
                    "lines": self._build_pc_config_lines(lan_count, str(spec.get("dns_server", "1.1.1.1"))),
                    "code_block": "",
                }
            )
        else:
            steps.append(
                {
                    "order": 40,
                    "title": "根据路由设备模板补齐三层配置",
                    "lines": [
                        "- 使用 configure_node 在 router1 上完成接口 IP 与默认路由配置",
                        "- 为每台 PC 配置同网段地址并验证互通",
                    ],
                    "code_block": "",
                }
            )

        rules = [
            "严格按步骤顺序执行，完成上一步后才能进行下一步。",
            "不要跳过等待步骤，wait_for_nodes_ready 必须返回成功。",
            "节点、链路、配置、验证必须全部完成后才算部署成功。",
        ]

        checklist = [
            f"{len(nodes)} 个节点已创建并启动完成。",
            f"{len(links)} 条链路已创建完成。",
            "wait_for_nodes_ready 已调用并返回成功。",
        ]
        if uses_fortigate:
            checklist.append("所有 PC 地址和默认网关已配置。")
        else:
            checklist.append("路由设备与终端基础三层配置已完成。")

        return {
            "nodes": nodes,
            "links": links,
            "steps": steps,
            "rules": rules,
            "checklist": checklist,
        }

    def validate(self, spec: PromptSpec, rendered_prompt: str) -> list[str]:
        missing: list[str] = []
        body = str(rendered_prompt or "").lower()
        if "## 节点清单" not in body or "## 链路清单" not in body:
            missing.append("缺少基础章节：节点清单/链路清单。")
        if "## 执行步骤" not in body:
            missing.append("缺少基础章节：执行步骤。")
        if "## 执行规则" not in body:
            missing.append("缺少基础章节：执行规则。")
        if "## critical: 部署完成检查清单" not in body:
            missing.append("缺少基础章节：部署完成检查清单。")
        return missing

    def _build_links(
        self,
        *,
        uses_fortigate: bool,
        lan_count: int,
        use_switch: bool,
        use_nat: bool,
        fortigate_name: str,
    ) -> list[str]:
        links: list[str] = []
        if uses_fortigate:
            for index in range(1, lan_count + 1):
                # 约束：FortiGate 业务口从 port2 开始，对应 GNS3 的 Ethernet1/2/3...
                # Constraint: FortiGate business ports start from port2, mapped to Ethernet1/2/3...
                links.append(
                    f"PC{index}端口0 连接 {fortigate_name}的Ethernet{index}"
                )
            if use_switch:
                links.append(f"{fortigate_name}的Ethernet0 连接 switch1的Ethernet0")
                if use_nat:
                    links.append("nat1端口0 连接 switch1的Ethernet1")
            elif use_nat:
                links.append(f"{fortigate_name}的Ethernet0 连接 nat1端口0")
            return links

        for index in range(1, lan_count + 1):
            links.append(f"PC{index}端口0 连接 router1的Ethernet{index - 1}")
        if use_switch:
            links.append(f"router1的Ethernet{lan_count} 连接 switch1的Ethernet0")
            if use_nat:
                links.append("nat1端口0 连接 switch1的Ethernet1")
        elif use_nat:
            links.append(f"router1的Ethernet{lan_count} 连接 nat1端口0")
        return links

    def _build_pc_config_lines(self, lan_count: int, dns_server: str) -> list[str]:
        lines: list[str] = []
        for index in range(1, lan_count + 1):
            lines.append(
                f"{index}. 使用 configure_node 在 PC{index} 上执行以下命令："
            )
            lines.append(
                f"  ip 192.168.{index}.10/24 192.168.{index}.1"
            )
            lines.append(f"  ip dns {dns_server}")
            lines.append("  save")
        return lines

    def _node_names(self, node_entries: list[str]) -> list[str]:
        names: list[str] = []
        for entry in node_entries:
            if " - " in entry:
                names.append(entry.split(" - ", 1)[0])
            else:
                names.append(entry)
        return names
