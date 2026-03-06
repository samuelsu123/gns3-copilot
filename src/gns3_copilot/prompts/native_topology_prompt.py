"""
Prompt utilities for generating native gns3-copilot topology task prompts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_PROMPT_SECTIONS = (
    "## 节点清单",
    "## 链路清单",
    "## 执行步骤",
    "## 执行规则",
    "## CRITICAL: 部署完成检查清单",
)
FORTIGATE_REQUEST_TOKENS = (
    "fortigate",
    "forti",
    "fgt",
    "防火墙",
)
FORTIGATE_REQUIRED_MARKERS = (
    "config system interface",
    "config router static",
    "config firewall policy",
    "set dst",
    "set device",
)
TOPOLOGY_SKILL_BASE_DIR = Path(__file__).with_name("skills")


def load_simple_fgt_reference() -> str:
    """Load bundled FortiGate topology prompt example as style reference."""
    reference_path = Path(__file__).with_name("simple_fgt.txt")
    try:
        return reference_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_topology_skill_markdown(skill_name: str) -> str:
    """
    Load one internal topology skill markdown body.

    This is runtime-facing skill content used as prompt guidance, not Codex host skills.
    """
    normalized = str(skill_name or "").strip()
    if not normalized:
        return ""
    skill_path = TOPOLOGY_SKILL_BASE_DIR / normalized / "SKILL.md"
    try:
        return skill_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def build_topology_skill_generation_prompt(
    *,
    user_request: str,
    active_skill_documents: list[tuple[str, str]],
    reference_prompt: str = "",
) -> str:
    """Build one system prompt that composes orchestrator skill + FortiGate skill docs."""
    skill_blocks: list[str] = []
    for skill_name, skill_doc in active_skill_documents:
        if not skill_doc.strip():
            continue
        skill_blocks.append(f"[Skill: {skill_name}]\n```markdown\n{skill_doc.strip()}\n```")
    skills_text = "\n\n".join(skill_blocks)

    reference_block = ""
    if reference_prompt.strip():
        reference_block = (
            "风格参考（仅作结构参考，内容必须按当前需求重写）：\n"
            f"```text\n{reference_prompt.strip()}\n```"
        )

    return (
        "你是 gns3-copilot 拓扑 prompt 生成代理。"
        "请严格遵循下方技能文档中定义的流程与约束。\n\n"
        "输出要求：\n"
        "1) 若信息不足：只输出一个 `clarify_options` 问题块（单题单轮）。\n"
        "2) 若信息充足：输出完整拓扑部署 prompt，且必须包含并按顺序输出：\n"
        "   - ## 节点清单\n"
        "   - ## 链路清单\n"
        "   - ## 执行步骤\n"
        "   - ## 执行规则\n"
        "   - ## CRITICAL: 部署完成检查清单\n"
        "3) 不要输出分析过程、道歉和与执行无关的解释。\n\n"
        f"{reference_block}\n\n"
        "技能文档：\n"
        f"{skills_text}\n\n"
        f"原始用户需求：{str(user_request or '').strip()}"
    ).strip()


def build_topology_intent_detection_prompt() -> str:
    """System prompt for classifying whether user asks for topology prompt generation."""
    return (
        "你是一个意图分类器。"
        "判断用户是否在请求“设计/搭建/部署网络拓扑，并希望产出可执行的拓扑描述或部署指令”。\n"
        "仅输出严格 JSON，不要输出其他文字，格式如下：\n"
        '{"is_topology_design_intent": true/false, "confidence": 0.0-1.0, "reason": "简短原因"}\n'
        "判定为 false 的常见情形：纯排障、show 命令、配置解释、报错分析、文档问答。"
    )


def parse_topology_intent_result(raw_text: str) -> tuple[bool, float]:
    """Parse intent detector JSON output; fallback to safe defaults."""
    text = str(raw_text or "").strip()
    if not text:
        return False, 0.0

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Try to salvage from fenced blocks or leading text.
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return False, 0.0
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return False, 0.0

    if not isinstance(payload, dict):
        return False, 0.0

    flag = bool(payload.get("is_topology_design_intent", False))
    confidence_raw = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return flag, confidence


def build_topology_prompt_confirmation_message(user_request: str) -> str:
    """Build a single-turn confirmation question before generating full prompt."""
    request_text = str(user_request or "").strip()
    if len(request_text) > 220:
        request_text = request_text[:220].rstrip() + "..."

    return (
        "我识别到你可能希望我生成一份可直接用于原生 gns3-copilot 的完整拓扑部署 prompt。\n\n"
        f"你的需求摘要：{request_text}\n\n"
        "是否现在生成这份完整 prompt？\n"
        "- 回复 `是` / `yes`：立即生成\n"
        "- 回复 `否` / `no`：继续按常规对话处理"
    )


def build_native_topology_generation_prompt(
    user_request: str,
    reference_prompt: str = "",
) -> str:
    """Build system prompt for generating executable native topology description."""
    reference_block = ""
    if reference_prompt.strip():
        reference_block = (
            "\n\n以下是风格参考（仅作结构参考，内容必须根据当前需求重写）：\n"
            f"```text\n{reference_prompt.strip()}\n```"
        )

    return (
        "你是 gns3-copilot 拓扑任务编写专家。"
        "请将用户需求转换为“可直接交给原生 gns3-copilot 执行”的完整部署指令文本。\n"
        "必须使用中文输出，且必须包含以下章节且顺序一致：\n"
        "1) ## 节点清单\n"
        "2) ## 链路清单\n"
        "3) ## 执行步骤\n"
        "4) ## 执行规则\n"
        "5) ## CRITICAL: 部署完成检查清单\n"
        "要求：\n"
        "- 内容必须可执行，步骤清晰，避免空泛描述。\n"
        "- 遇到 FortiGate 场景时，步骤中体现等待节点就绪、配置顺序与必要验证。\n"
        "- 不要输出解释、分析过程、道歉或多余前后缀。\n"
        "- 最终只输出部署指令正文。\n"
        f"{reference_block}\n\n"
        f"用户需求：{user_request.strip()}"
    )


def build_native_topology_repair_prompt(
    user_request: str,
    previous_output: str,
    missing_requirements: list[str] | None = None,
) -> str:
    """Build a one-shot repair prompt when section validation fails."""
    missing_text = ""
    if missing_requirements:
        missing_text = (
            "\n请特别补齐以下缺失项：\n"
            + "\n".join(f"- {item}" for item in missing_requirements)
            + "\n"
        )
    return (
        "请修复下面这份部署指令，使其满足固定章节结构，且可直接执行。\n"
        "必须包含并按顺序输出：\n"
        "## 节点清单\n"
        "## 链路清单\n"
        "## 执行步骤\n"
        "## 执行规则\n"
        "## CRITICAL: 部署完成检查清单\n\n"
        "如果是 FortiGate 场景，必须补齐完整 FortiGate 配置块：\n"
        "- config system interface\n"
        "- config router static（含 set dst 与 set device）\n"
        "- config firewall policy\n"
        "- 建议包含 wait_for_nodes_ready 与配置顺序控制\n"
        f"{missing_text}\n"
        f"用户需求：{user_request.strip()}\n\n"
        f"当前输出：\n```text\n{previous_output.strip()}\n```"
    )


def is_native_topology_prompt_format(text: str) -> bool:
    """Check whether generated text includes all required topology prompt sections."""
    body = str(text or "")
    if not body.strip():
        return False

    search_start = 0
    for section in REQUIRED_PROMPT_SECTIONS:
        pos = body.find(section, search_start)
        if pos < 0:
            return False
        search_start = pos + len(section)
    return True


def is_fortigate_request(user_request: str) -> bool:
    text = str(user_request or "").lower()
    return any(token in text for token in FORTIGATE_REQUEST_TOKENS)


def validate_native_topology_prompt(
    text: str,
    user_request: str = "",
) -> dict[str, Any]:
    """
    Validate generated topology prompt.

    Returns:
        {
            "ok": bool,
            "missing_requirements": list[str],
        }
    """
    missing: list[str] = []
    body = str(text or "")

    if not is_native_topology_prompt_format(body):
        missing.append("固定章节结构不完整（节点/链路/步骤/规则/检查清单）")

    if is_fortigate_request(user_request):
        lowered = body.lower()
        for marker in FORTIGATE_REQUIRED_MARKERS:
            if marker not in lowered:
                missing.append(f"缺少 FortiGate 配置关键项：`{marker}`")
        if "wait_for_nodes_ready" not in lowered:
            missing.append("缺少节点就绪等待步骤：`wait_for_nodes_ready`")
        if "configure_node" not in lowered:
            missing.append("缺少设备配置动作：`configure_node`")

    return {
        "ok": not missing,
        "missing_requirements": missing,
    }


def build_topology_prompt_missing_requirements_question(
    user_request: str,
    missing_requirements: list[str],
) -> str:
    """Build a concise clarification prompt when repeated regeneration still fails."""
    missing_text = "\n".join(f"- {item}" for item in missing_requirements)
    return (
        "我尝试生成了完整拓扑 prompt，但自动校验仍提示关键信息不完整。\n\n"
        f"当前缺失项：\n{missing_text}\n\n"
        "请确认是否按默认参数补齐（默认会参考 simple_fgt 风格并自动生成 FortiGate 完整配置块）。\n"
        "- 回复 `是` / `yes`：按默认参数补齐并重新生成\n"
        "- 回复 `否` / `no`：请补充你的 IP 规划、路由和策略偏好后我再生成\n\n"
        f"原始需求：{user_request.strip()}"
    )
