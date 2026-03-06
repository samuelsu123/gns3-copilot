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
VPN_REQUEST_TOKENS = (
    "ipsec",
    "vpn",
    "站点互联",
    "site-to-site",
    "site to site",
)
FORTIGATE_VPN_REQUIRED_MARKERS = (
    "config vpn ipsec phase1-interface",
    "config vpn ipsec phase2-interface",
    "set psksecret",
)
TOPOLOGY_SKILL_BASE_DIR = Path(__file__).with_name("skills")

# ---------------------------------------------------------------------------
# Progressive disclosure phases
# 渐进式披露阶段定义
# ---------------------------------------------------------------------------
TOPOLOGY_PHASE_OVERVIEW = "topology_overview"
TOPOLOGY_PHASE_NODE_LINK = "node_and_link_plan"
TOPOLOGY_PHASE_EXECUTION = "execution_steps"
TOPOLOGY_PHASE_COMPLETED = "completed"

TOPOLOGY_PHASES = (
    TOPOLOGY_PHASE_OVERVIEW,
    TOPOLOGY_PHASE_NODE_LINK,
    TOPOLOGY_PHASE_EXECUTION,
    TOPOLOGY_PHASE_COMPLETED,
)

# Simple topologies (node count <= this threshold) may skip to completed directly.
TOPOLOGY_FAST_TRACK_MAX_NODES = 3


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


def _phase_instruction(phase: str, confirmed_layers: dict[str, str]) -> str:
    """Build phase-specific output instruction block."""
    confirmed_block = ""
    if confirmed_layers:
        parts: list[str] = []
        for layer_name, layer_text in confirmed_layers.items():
            parts.append(f"[已确认 - {layer_name}]\n{layer_text.strip()}")
        confirmed_block = (
            "以下是用户已确认的前序阶段输出，后续阶段必须基于这些内容：\n\n"
            + "\n\n".join(parts)
            + "\n\n"
        )

    if phase == TOPOLOGY_PHASE_OVERVIEW:
        return (
            "当前阶段：Phase 1 — 拓扑概要\n"
            "请输出拓扑概要，包含站点、设备、网段、互联方式和上网策略。\n"
            "使用 `## 拓扑概要` 章节标题。\n"
            "当用户未指定 IP 时自动分配合理默认网段，不要为此发起澄清。\n"
            "若存在真正歧义，使用 `clarify_options` 提出一个澄清问题。\n"
            "不要输出后续阶段的内容。"
        )
    if phase == TOPOLOGY_PHASE_NODE_LINK:
        return (
            f"{confirmed_block}"
            "当前阶段：Phase 2 — 节点与链路清单\n"
            "基于已确认的拓扑概要，输出：\n"
            "- `## 节点清单` — 每个节点的名称、模板、所属站点\n"
            "- `## 链路清单` — 每条链路的两端节点与端口\n"
            "端口编号必须明确，节点命名需包含站点前缀。\n"
            "不要输出执行步骤或配置命令。"
        )
    if phase == TOPOLOGY_PHASE_EXECUTION:
        return (
            f"{confirmed_block}"
            "当前阶段：Phase 3 — 执行步骤、规则与检查清单\n"
            "基于已确认的节点和链路清单，输出：\n"
            "- `## 执行步骤` — 完整步骤序列，含设备配置 CLI 命令块\n"
            "- `## 执行规则` — 步骤间的顺序约束\n"
            "- `## CRITICAL: 部署完成检查清单` — 与步骤一一对应的验证项\n"
            "配置命令必须完整内联在步骤中，不得省略。"
        )
    # TOPOLOGY_PHASE_COMPLETED
    return (
        f"{confirmed_block}"
        "当前阶段：Phase 4 — 合并最终输出\n"
        "将所有已确认的层合并为一份完整可执行 prompt，必须包含且按顺序输出：\n"
        "1) ## 节点清单\n"
        "2) ## 链路清单\n"
        "3) ## 执行步骤\n"
        "4) ## 执行规则\n"
        "5) ## CRITICAL: 部署完成检查清单\n"
        "仅输出最终 prompt 正文，不要夹带解释。"
    )


def build_topology_skill_phase_prompt(
    *,
    user_request: str,
    phase: str,
    confirmed_layers: dict[str, str],
    active_skill_documents: list[tuple[str, str]],
    reference_prompt: str = "",
) -> str:
    """Build a phase-aware system prompt for progressive topology generation."""
    skill_blocks: list[str] = []
    for skill_name, skill_doc in active_skill_documents:
        if not skill_doc.strip():
            continue
        skill_blocks.append(
            f"[Skill: {skill_name}]\n```markdown\n{skill_doc.strip()}\n```"
        )
    skills_text = "\n\n".join(skill_blocks)

    reference_block = ""
    if reference_prompt.strip():
        reference_block = (
            "风格参考（仅作结构参考，内容必须按当前需求重写）：\n"
            f"```text\n{reference_prompt.strip()}\n```\n\n"
        )

    phase_block = _phase_instruction(phase, confirmed_layers)

    return (
        "你是 gns3-copilot 拓扑 prompt 生成代理。"
        "请严格遵循下方技能文档和阶段指令。\n\n"
        f"{reference_block}"
        f"{phase_block}\n\n"
        "技能文档：\n"
        f"{skills_text}\n\n"
        "不要输出分析过程、道歉和与执行无关的解释。\n\n"
        f"原始用户需求：{str(user_request or '').strip()}"
    ).strip()


def next_phase(current_phase: str) -> str | None:
    """Return the next phase after *current_phase*, or ``None`` if already final."""
    try:
        idx = TOPOLOGY_PHASES.index(current_phase)
    except ValueError:
        return TOPOLOGY_PHASE_OVERVIEW
    if idx + 1 < len(TOPOLOGY_PHASES):
        return TOPOLOGY_PHASES[idx + 1]
    return None


def is_vpn_request(user_request: str) -> bool:
    """Detect whether the user request involves VPN / site-to-site connectivity."""
    text = str(user_request or "").lower()
    return any(token in text for token in VPN_REQUEST_TOKENS)


def validate_phase_output(
    text: str,
    phase: str,
    user_request: str = "",
) -> dict[str, Any]:
    """Validate generated output for a specific phase."""
    missing: list[str] = []
    body = str(text or "")

    if phase == TOPOLOGY_PHASE_OVERVIEW:
        if "## 拓扑概要" not in body:
            missing.append("缺少 `## 拓扑概要` 章节")
    elif phase == TOPOLOGY_PHASE_NODE_LINK:
        if "## 节点清单" not in body:
            missing.append("缺少 `## 节点清单` 章节")
        if "## 链路清单" not in body:
            missing.append("缺少 `## 链路清单` 章节")
    elif phase == TOPOLOGY_PHASE_EXECUTION:
        if "## 执行步骤" not in body:
            missing.append("缺少 `## 执行步骤` 章节")
        if "## 执行规则" not in body:
            missing.append("缺少 `## 执行规则` 章节")
        if "## CRITICAL: 部署完成检查清单" not in body:
            missing.append("缺少 `## CRITICAL: 部署完成检查清单` 章节")
        if is_fortigate_request(user_request):
            lowered = body.lower()
            for marker in FORTIGATE_REQUIRED_MARKERS:
                if marker not in lowered:
                    missing.append(f"缺少 FortiGate 配置关键项：`{marker}`")
            if "wait_for_nodes_ready" not in lowered:
                missing.append("缺少节点就绪等待步骤：`wait_for_nodes_ready`")
            if "configure_node" not in lowered:
                missing.append("缺少设备配置动作：`configure_node`")
            if is_vpn_request(user_request):
                for marker in FORTIGATE_VPN_REQUIRED_MARKERS:
                    if marker not in lowered:
                        missing.append(f"缺少 VPN 配置关键项：`{marker}`")
    elif phase == TOPOLOGY_PHASE_COMPLETED:
        return validate_native_topology_prompt(text, user_request)

    return {
        "ok": not missing,
        "missing_requirements": missing,
    }


def build_phase_confirmation_message(phase: str, output_text: str) -> str:
    """Build confirmation prompt shown to user after a phase completes."""
    phase_labels = {
        TOPOLOGY_PHASE_OVERVIEW: "拓扑概要（Phase 1）",
        TOPOLOGY_PHASE_NODE_LINK: "节点与链路清单（Phase 2）",
        TOPOLOGY_PHASE_EXECUTION: "执行步骤与规则（Phase 3）",
    }
    label = phase_labels.get(phase, phase)
    return (
        f"以下是生成的 **{label}**：\n\n"
        f"{output_text.strip()}\n\n"
        "---\n"
        "- 回复 `确认` / `ok`：确认并进入下一阶段\n"
        "- 直接回复修改意见：我会根据你的反馈调整后重新输出本阶段"
    )


PHASE_CONFIRM_KEYWORDS = {
    "确认",
    "ok",
    "OK",
    "Ok",
    "好",
    "好的",
    "可以",
    "没问题",
    "通过",
    "yes",
    "y",
    "是",
    "继续",
    "下一步",
    "next",
}


def resolve_phase_confirmation(user_text: str) -> str:
    """Classify user reply to a phase confirmation: 'confirm' or 'revise'."""
    text = str(user_text or "").strip()
    if not text:
        return "revise"
    if text in PHASE_CONFIRM_KEYWORDS:
        return "confirm"
    return "revise"


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
        if is_vpn_request(user_request):
            for marker in FORTIGATE_VPN_REQUIRED_MARKERS:
                if marker not in lowered:
                    missing.append(f"缺少 VPN 配置关键项：`{marker}`")

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
