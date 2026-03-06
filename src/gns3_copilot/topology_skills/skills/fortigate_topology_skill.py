"""
FortiGate-specific topology skill for deterministic configuration sections.
"""

from __future__ import annotations

from .base import (
    ClarificationQuestion,
    PromptSpec,
    SectionContribution,
    StepDefinition,
    TopologySkill,
)


class FortiGateTopologySkill(TopologySkill):
    """Reusable FortiGate sub-skill that injects FortiGate-only execution logic."""

    skill_id = "fortigate-topology-skill"
    priority = 20

    def match(self, spec: PromptSpec) -> bool:
        return bool(spec.get("uses_fortigate", False))

    def required_slots(self, spec: PromptSpec) -> tuple[str, ...]:
        return ()

    def optional_slots(self, spec: PromptSpec) -> tuple[str, ...]:
        return ("include_license",)

    def next_question(
        self,
        spec: PromptSpec,
        asked_question_ids: set[str],
    ) -> ClarificationQuestion | None:
        include_license = spec.get("include_license")
        if include_license is None and "fortigate_include_license" not in asked_question_ids:
            return {
                "kind": "clarification_choice",
                "question_id": "fortigate_include_license",
                "question": "是否需要在部署流程中导入 FortiGate license 并等待重启？",
                "options": [
                    {
                        "id": "A",
                        "label": "需要导入 license",
                        "value": "需要导入 license",
                    },
                    {
                        "id": "B",
                        "label": "跳过 license 导入",
                        "value": "跳过 license 导入",
                    },
                ],
                "allow_free_text": True,
                "slot_name": "include_license",
                "slot_values": {"A": True, "B": False},
            }
        return None

    def contribute_sections(self, spec: PromptSpec) -> SectionContribution:
        if not bool(spec.get("uses_fortigate", False)):
            return {
                "nodes": [],
                "links": [],
                "steps": [],
                "rules": [],
                "checklist": [],
            }

        fortigate_name = str(spec.get("fortigate_name", "fortigate1") or "fortigate1")
        include_license = bool(spec.get("include_license", False))
        lan_count = int(spec.get("lan_count", 2) or 2)

        interface_cli = self._build_interface_cli(lan_count=lan_count)
        policy_cli = self._build_policy_cli()
        license_cli = str(
            spec.get(
                "license_restore_command",
                "execute restore vmlicense ftp /aiops/licenses/FGVMULTM26000146.lic "
                "10.65.10.243 test test",
            )
            or ""
        ).strip()

        steps: list[StepDefinition] = [
            {
                "order": 40,
                "title": "配置 FortiGate 接口和路由",
                "lines": [
                    f"- 使用 configure_node 配置 {fortigate_name}：",
                ],
                "code_block": interface_cli,
            },
        ]

        if include_license and license_cli:
            steps.append(
                {
                    "order": 50,
                    "title": "导入 FortiGate license 并等待重启",
                    "lines": [
                        f"1. 使用 configure_node 在 {fortigate_name} 上执行：",
                        "2. 当看到提示 \"Do you want to continue? (y/n)\" 时输入 `y`。",
                        "3. **license 导入会触发 FortiGate 自动重启。**",
                        "4. **必须调用 wait_for_nodes_ready(timeout=1200) 等待重启完成。**",
                    ],
                    "code_block": license_cli,
                }
            )

        steps.append(
            {
                "order": 60,
                "title": "配置 FortiGate 防火墙策略",
                "lines": [
                    f"- 使用 configure_node 在 {fortigate_name} 上执行：",
                ],
                "code_block": policy_cli,
            }
        )

        rules = [
            "FortiGate 业务口必须从 port2 起配置，port1 仅作为管理口。",
            "FortiGate 配置步骤必须在节点就绪后执行。",
        ]
        if include_license:
            rules.append("license 导入后必须再次等待节点就绪再继续策略配置。")

        checklist = [
            "FortiGate 接口与静态路由配置已完成（port1 管理口保留）。",
            "FortiGate 防火墙策略已配置。",
        ]
        if include_license:
            checklist.insert(1, "FortiGate license 已导入且重启后重新就绪。")

        return {
            "nodes": [],
            "links": [],
            "steps": steps,
            "rules": rules,
            "checklist": checklist,
        }

    def validate(self, spec: PromptSpec, rendered_prompt: str) -> list[str]:
        if not bool(spec.get("uses_fortigate", False)):
            return []

        missing: list[str] = []
        lowered = str(rendered_prompt or "").lower()

        for marker in (
            "config system interface",
            "config router static",
            "config firewall policy",
            "set dst 0.0.0.0 0.0.0.0",
            "set device port1",
        ):
            if marker not in lowered:
                missing.append(f"缺少 FortiGate 关键配置：`{marker}`")

        # 关键安全约束：管理口 port1 仅用于管理，业务网段必须落在 port2+。
        # Safety constraint: Management port1 is reserved; business subnets must be on port2+.
        if 'edit port1\nset mode static\nset ip 192.168.1.1' in lowered:
            missing.append("检测到 port1 被用于业务网段，请保持 port1 仅管理用途。")
        return missing

    def _build_interface_cli(self, lan_count: int) -> str:
        lines = [
            "config system interface",
            "edit port1",
            "set mode static",
            "set ip 192.168.122.10 255.255.255.0",
            "set allowaccess ping https ssh http",
            "next",
        ]
        for index in range(1, lan_count + 1):
            lines.extend(
                [
                    f"edit port{index + 1}",
                    "set mode static",
                    f"set ip 192.168.{index}.1 255.255.255.0",
                    "set allowaccess ping",
                    "next",
                ]
            )

        lines.extend(
            [
                "end",
                "config router static",
                "edit 1",
                "set dst 0.0.0.0 0.0.0.0",
                "set gateway 192.168.122.1",
                "set device port1",
                "next",
                "end",
            ]
        )
        return "\n".join(lines)

    def _build_policy_cli(self) -> str:
        return "\n".join(
            [
                "config firewall policy",
                "edit 0",
                'set name "allow_all"',
                'set srcintf "any"',
                'set dstintf "any"',
                'set srcaddr "all"',
                'set dstaddr "all"',
                "set action accept",
                'set schedule "always"',
                'set service "ALL"',
                'set logtraffic "all"',
                "set nat enable",
                "next",
                "end",
            ]
        )
