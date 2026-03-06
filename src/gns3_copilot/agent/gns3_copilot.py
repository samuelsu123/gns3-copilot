# mypy: ignore-errors

"""
GNS3 Network Automation Assistant
GNS3 网络自动化助手

This module implements an AI-powered assistant for GNS3 network automation and management.
It uses LangChain for agent orchestration and DeepSeek LLM for natural language processing.
The assistant provides comprehensive GNS3 topology management capabilities including:
- Reading and analyzing GNS3 project topologies
- Creating and managing network nodes and links
- Executing network configuration and display commands on multiple devices
- Managing VPCS (Virtual PC Simulator) commands
- Starting and controlling GNS3 nodes

此模块实现了用于 GNS3 网络自动化和管理的 AI 助手。
它使用 LangChain 进行代理编排，使用 DeepSeek LLM 进行自然语言处理。
助手提供全面的 GNS3 拓扑管理功能，包括：
- 读取和分析 GNS3 项目拓扑
- 创建和管理网络节点和链路
- 在多个设备上执行网络配置和显示命令
- 管理 VPCS（虚拟 PC 模拟器）命令
- 启动和控制 GNS3 节点

The assistant integrates with various tools to provide a complete network automation
solution for GNS3 environments.
助手与各种工具集成，为 GNS3 环境提供完整的网络自动化解决方案。
"""

import ast
import json
import operator
import sqlite3
from typing import Annotated, Any, Literal

import streamlit as st
from langchain.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.managed.is_last_step import RemainingSteps
from typing_extensions import TypedDict

from gns3_copilot.agent.model_factory import (
    create_base_model,
    create_base_model_with_tools,
    create_title_model,
)
from gns3_copilot.agent.prompt_trace import append_llm_trace_round
from gns3_copilot.agent.topology_dry_run import (
    DRY_RUN_TOOL_NAMES,
    build_topology_reader_output,
    execute_dry_run_tool,
    initialize_simulated_topology,
    is_topology_dry_run_enabled,
)
from gns3_copilot.gns3_client import GNS3TopologyTool
from gns3_copilot.log_config import setup_logger
from gns3_copilot.prompts import TITLE_PROMPT, load_system_prompt
from gns3_copilot.prompts.clarification_choice_prompt import (
    build_clarification_choice_prompt,
)
from gns3_copilot.prompts.fortigate_config_prompt import (
    should_inject_fortigate_prompt,
)
from gns3_copilot.prompts.fortigate_config_strategy import (
    build_fortigate_strategy_prompt,
)
from gns3_copilot.prompts.fortinet_base_prompt import (
    build_fortinet_baseline_prompt,
)
from gns3_copilot.prompts.native_topology_prompt import (
    build_native_topology_repair_prompt,
    build_topology_skill_generation_prompt,
    build_topology_intent_detection_prompt,
    build_topology_prompt_confirmation_message,
    build_topology_prompt_missing_requirements_question,
    is_fortigate_request,
    load_simple_fgt_reference,
    load_topology_skill_markdown,
    parse_topology_intent_result,
    validate_native_topology_prompt,
)
from gns3_copilot.tools_v2 import (
    ExecuteMultipleDeviceCommands,
    ExecuteMultipleDeviceConfigCommands,
    FortinetDocSearchTool,
    GNS3CreateAreaDrawingTool,
    GNS3CreateNodeTool,
    GNS3LinkTool,
    GNS3StartNodeTool,
    GNS3TemplateTool,
    LinuxTelnetBatchTool,
    VPCSMultiCommands,
)
from gns3_copilot.utils import get_config

# Set up logger for GNS3 Copilot
# 为 GNS3 Copilot 设置日志记录器
logger = setup_logger("gns3_copilot", log_file="gns3_copilot.log")

# Log loaded LLM model information
# 记录加载的 LLM 模型信息
model_name = get_config("MODEL_NAME")
model_provider = get_config("MODE_PROVIDER")
base_url = get_config("BASE_URL", "")
temperature = get_config("TEMPERATURE", "0")
logger.info(
    "LLM model configuration: name=%s, provider=%s, base_url=%s, temperature=%s",
    model_name,
    model_provider,
    base_url,
    temperature,
)

# Define the available tools for the agent
# 定义代理可用的工具
tools = [
    GNS3TemplateTool(),  # Get GNS3 node templates 获取 GNS3 节点模板
    GNS3TopologyTool(),  # Read GNS3 topology information 读取 GNS3 拓扑信息
    FortinetDocSearchTool(),  # Search Fortinet docs from local ChromaDB
                             # 从本地 ChromaDB 检索 Fortinet 文档
    GNS3CreateNodeTool(),  # Create new nodes in GNS3 在 GNS3 中创建新节点
    GNS3LinkTool(),  # Create links between nodes 在节点之间创建链路
    GNS3StartNodeTool(),  # Start GNS3 nodes 启动 GNS3 节点
    ExecuteMultipleDeviceCommands(),  # Execute show/display commands on multiple devices
                                       # 在多个设备上执行 show/display 命令
    ExecuteMultipleDeviceConfigCommands(),  # Execute configuration commands on multiple devices
                                             # 在多个设备上执行配置命令
    VPCSMultiCommands(),  # Execute VPCS commands on multiple devices
                          # 在多个设备上执行 VPCS 命令
    LinuxTelnetBatchTool(),  # Execute Linux commands via Telnet on multiple devices
                              # 通过 Telnet 在多个设备上执行 Linux 命令
    GNS3CreateAreaDrawingTool(),  # Create area drawings in GNS3 topologies
                                   # 在 GNS3 拓扑中创建区域绘图
]
# Augment the LLM with tools
# 使用工具增强 LLM
tools_by_name = {tool.name: tool for tool in tools}
# Model with tools will be created dynamically by the factory when needed
# 带工具的模型将在需要时由工厂动态创建

# Log application startup
# 记录应用程序启动
logger.info("GNS3 Copilot application starting up")
logger.debug("Available tools: %s", [tool.__class__.__name__ for tool in tools])

FORTIGATE_CONFIG_TOOL_NAME = "execute_multiple_device_config_commands"
FORTINET_DOC_SEARCH_TOOL_NAME = "fortinet_doc_search"
RAG_TRUTHY_VALUES = {"1", "true", "yes", "on"}

# Tag used to suppress internal helper LLM calls from stream_mode="messages" output.
# Internal calls (intent detection, title generation, prompt generation) should not
# appear in the user-facing streaming display.
# 用于在 stream_mode="messages" 输出中抑制内部辅助 LLM 调用的标签。
INTERNAL_LLM_TAG = "__internal_llm"

FORTIGATE_CONFIRM_KEYWORDS = {
    "确认执行",
    "确认",
    "同意执行",
    "请执行",
    "confirm",
    "approve",
    "yes",
    "y",
}
FORTIGATE_CANCEL_KEYWORDS = {
    "取消执行",
    "取消",
    "不要执行",
    "不执行",
    "cancel",
    "abort",
    "no",
    "n",
}
FORTIGATE_QUALITY_PASS_KEYWORDS = {
    "配置无问题",
    "没问题",
    "继续",
    "ok",
    "okay",
}
TOPOLOGY_PROMPT_CONFIRM_KEYWORDS = {
    "是",
    "好的",
    "可以",
    "生成",
    "yes",
    "y",
}
TOPOLOGY_PROMPT_DECLINE_KEYWORDS = {
    "否",
    "不用",
    "不需要",
    "no",
    "n",
}
TOPOLOGY_INTENT_MIN_CONFIDENCE = 0.55
TOPOLOGY_PROMPT_MAX_REPAIR_ATTEMPTS = 2
TOPOLOGY_ORCHESTRATOR_SKILL_NAME = "topology-prompt-orchestrator"
FORTIGATE_TOPOLOGY_SKILL_NAME = "fortigate-topology"


# Define state
# 定义状态
class MessagesState(TypedDict):
    """
    GNS3 Copilot conversation state management class.
    GNS3 Copilot 对话状态管理类。

    Maintains the conversation state for the LangGraph workflow, including message history,
    call counters, and session titles for comprehensive dialogue management.
    维护 LangGraph 工作流的对话状态，包括消息历史、调用计数器和会话标题，
    用于全面的对话管理。

    Attributes:
        messages: List of conversation messages with cumulative updates using operator.add
                  使用 operator.add 进行累积更新的对话消息列表
        llm_calls: Counter for tracking the number of LLM invocations
                   用于跟踪 LLM 调用次数的计数器
        remaining_steps: Is automatically managed by LangGraph's RemainingSteps to track and limit recursion depth.
                         由 LangGraph 的 RemainingSteps 自动管理，用于跟踪和限制递归深度
        conversation_title: Optional conversation title for session identification and management
                            用于会话识别和管理的可选对话标题
        topology_info: Dictionary containing GNS3 project topology information
                       包含 GNS3 项目拓扑信息的字典
    """

    messages: Annotated[list[AnyMessage], operator.add]

    llm_calls: int

    remaining_steps: RemainingSteps

    # Optional conversation title
    # 可选的对话标题
    conversation_title: str | None

    # Store the complete tuple selected by the user
    # 存储用户选择的完整元组
    selected_project: tuple[str, str, int, int, str] | None

    # Store GNS3 topology information
    # 存储 GNS3 拓扑信息
    topology_info: dict | None

    # Store dry-run topology simulation state
    # 存储 dry-run 拓扑模拟状态
    simulated_topology: dict | None

    # Pending FortiGate config tool call waiting for explicit user confirmation
    # 等待用户明确确认的 FortiGate 配置工具调用
    pending_fortigate_config_call: dict | None

    # Human-readable preview of pending FortiGate CLI commands
    # 待确认 FortiGate CLI 命令的可读预览
    pending_fortigate_config_preview: str | None

    # Pending FortiGate config tool call waiting for quality review confirmation
    # 等待质量确认的 FortiGate 配置工具调用
    pending_fortigate_quality_call: dict | None

    # Human-readable preview for pending FortiGate quality review
    # 待质量确认 FortiGate CLI 命令的可读预览
    pending_fortigate_quality_preview: str | None

    # Pending topology prompt generation request waiting for user yes/no confirmation
    # 等待用户确认是否生成拓扑 prompt 的待处理请求
    pending_topology_prompt_request: dict | None

    # Extra context attached to topology prompt pending request
    # 拓扑 prompt 待处理请求附加上下文
    pending_topology_prompt_context: dict | None

    # Pending topology skill runtime session
    # 待处理的拓扑 skill 运行时会话
    pending_topology_skill_session: dict | None

    # Pending single clarification question generated by topology skill runtime
    # 拓扑 skill 运行时生成的待回答单题澄清问题
    pending_clarification_question: dict | None

    # Persisted normalized topology prompt spec for observability/debug
    # 归一化后的拓扑 prompt 规格（用于可观测与调试）
    topology_prompt_spec: dict | None


def _normalize_content_blocks_to_text(content: list[Any]) -> str:
    """
    Normalize non-OpenAI-compatible content blocks to plain text.

    Some providers (or legacy checkpoints) may store message content as:
    [{"text": "..."}] without OpenAI-required {"type": "..."} blocks.
    OpenAI chat.completions rejects this payload, so we coerce it to text.
    """
    text_parts: list[str] = []

    for block in content:
        if isinstance(block, dict):
            # Preserve human-readable text when available
            if "text" in block and isinstance(block["text"], str):
                text_parts.append(block["text"])
                continue
            if "content" in block and isinstance(block["content"], str):
                text_parts.append(block["content"])
                continue
            text_parts.append(str(block))
            continue

        text_parts.append(str(block))

    return "\n".join([part for part in text_parts if part])


def _normalize_message_for_model(message: AnyMessage) -> AnyMessage:
    """
    Return a model-compatible message copy.

    If content is a list of dict blocks without `type`, convert to plain text.
    """
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return message

    dict_blocks = [block for block in content if isinstance(block, dict)]
    if not dict_blocks:
        return message

    all_blocks_have_type = all("type" in block for block in dict_blocks)
    # Already OpenAI-compatible block structure
    if all_blocks_have_type:
        return message

    normalized_text = _normalize_content_blocks_to_text(content)

    # pydantic v2 style copy
    if hasattr(message, "model_copy"):
        return message.model_copy(update={"content": normalized_text})
    # pydantic v1 style copy
    if hasattr(message, "copy"):
        return message.copy(update={"content": normalized_text})

    return message


def _serialize_message_for_log(message: AnyMessage) -> dict[str, Any]:
    """Convert LangChain message object to log-friendly dictionary."""
    content = getattr(message, "content", "")
    if isinstance(content, list):
        content = _normalize_content_blocks_to_text(content)

    payload: dict[str, Any] = {
        "type": getattr(message, "type", message.__class__.__name__),
        "content": content,
    }

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = tool_calls

    name = getattr(message, "name", None)
    if name:
        payload["name"] = name

    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id

    return payload


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


def _latest_human_text(messages: list[AnyMessage] | None) -> str:
    if not isinstance(messages, list):
        return ""

    for message in reversed(messages):
        msg_type = str(getattr(message, "type", "")).lower()
        cls_name = message.__class__.__name__.lower()
        if msg_type == "human" or "human" in cls_name:
            return _stringify_message_content(getattr(message, "content", "")).strip()
    return ""


def _normalize_confirmation_token(text: str) -> str:
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return ""
    # Chinese confirmations are usually written without spaces.
    return normalized.replace(" ", "")


def _resolve_fortigate_confirmation(text: str) -> Literal["confirm", "cancel", "unknown"]:
    token = _normalize_confirmation_token(text)
    if not token:
        return "unknown"
    if token in {item.replace(" ", "") for item in FORTIGATE_CONFIRM_KEYWORDS}:
        return "confirm"
    if token in {item.replace(" ", "") for item in FORTIGATE_CANCEL_KEYWORDS}:
        return "cancel"
    return "unknown"


def _resolve_fortigate_quality_review(
    text: str,
) -> Literal["pass", "cancel", "feedback"]:
    token = _normalize_confirmation_token(text)
    if token in {item.replace(" ", "") for item in FORTIGATE_QUALITY_PASS_KEYWORDS}:
        return "pass"
    if token in {item.replace(" ", "") for item in FORTIGATE_CANCEL_KEYWORDS}:
        return "cancel"
    return "feedback"


def _parse_json_payload(value: Any) -> dict[str, Any] | list[Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            try:
                literal = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                return None
            if isinstance(literal, (dict, list)):
                return literal
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


def _extract_tool_payload(tool_args: Any) -> dict[str, Any] | list[Any] | None:
    parsed_args = _parse_json_payload(tool_args)
    if isinstance(parsed_args, dict) and "tool_input" in parsed_args:
        payload = _parse_json_payload(parsed_args.get("tool_input"))
        return payload
    return parsed_args


def _extract_device_configs_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        configs = payload.get("device_configs", [])
        if isinstance(configs, list):
            return [item for item in configs if isinstance(item, dict)]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _node_looks_like_fortigate(node: dict[str, Any]) -> bool:
    text = " ".join(
        str(node.get(key, "")).lower()
        for key in ("name", "template_name", "template_type", "template_id")
    )
    return "forti" in text or "fgt" in text


def _topology_nodes(
    topology_info: dict[str, Any] | None,
    simulated_topology: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(topology_info, dict):
        topology_nodes = topology_info.get("nodes", {})
        if isinstance(topology_nodes, dict):
            nodes.extend(
                item for item in topology_nodes.values() if isinstance(item, dict)
            )
        elif isinstance(topology_nodes, list):
            nodes.extend(item for item in topology_nodes if isinstance(item, dict))
    if isinstance(simulated_topology, dict):
        simulated_nodes = simulated_topology.get("nodes", [])
        if isinstance(simulated_nodes, list):
            nodes.extend(item for item in simulated_nodes if isinstance(item, dict))
    return nodes


def _is_fortigate_device_name(
    device_name: str,
    topology_info: dict[str, Any] | None = None,
    simulated_topology: dict[str, Any] | None = None,
) -> bool:
    lowered = str(device_name or "").strip().lower()
    if "forti" in lowered or "fgt" in lowered:
        return True

    if not lowered:
        return False

    for node in _topology_nodes(topology_info, simulated_topology):
        node_name = str(node.get("name", "")).strip().lower()
        if node_name and node_name == lowered and _node_looks_like_fortigate(node):
            return True
    return False


def _fortigate_command_blocks_from_tool_call(
    tool_call: dict[str, Any],
    topology_info: dict[str, Any] | None = None,
    simulated_topology: dict[str, Any] | None = None,
) -> list[tuple[str, list[str]]]:
    if str(tool_call.get("name", "")) != FORTIGATE_CONFIG_TOOL_NAME:
        return []

    payload = _extract_tool_payload(tool_call.get("args", {}))
    configs = _extract_device_configs_from_payload(payload)
    blocks: list[tuple[str, list[str]]] = []

    for cfg in configs:
        device_name = str(cfg.get("device_name", "")).strip()
        if not _is_fortigate_device_name(
            device_name=device_name,
            topology_info=topology_info,
            simulated_topology=simulated_topology,
        ):
            continue
        commands = cfg.get("config_commands", [])
        if not isinstance(commands, list):
            commands = []
        command_lines = [str(item).strip() for item in commands if str(item).strip()]
        blocks.append((device_name or "FortiGate", command_lines))
    return blocks


def _find_fortigate_config_tool_call(
    tool_calls: list[dict[str, Any]] | None,
    topology_info: dict[str, Any] | None = None,
    simulated_topology: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(tool_calls, list):
        return None
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        blocks = _fortigate_command_blocks_from_tool_call(
            tool_call,
            topology_info=topology_info,
            simulated_topology=simulated_topology,
        )
        if blocks:
            return tool_call
    return None


def _render_fortigate_cli_preview(
    tool_call: dict[str, Any],
    topology_info: dict[str, Any] | None = None,
    simulated_topology: dict[str, Any] | None = None,
) -> str:
    blocks = _fortigate_command_blocks_from_tool_call(
        tool_call,
        topology_info=topology_info,
        simulated_topology=simulated_topology,
    )
    if not blocks:
        return "Unable to parse FortiGate CLI preview from tool call."

    preview_lines: list[str] = []
    for index, (device_name, commands) in enumerate(blocks, start=1):
        if len(blocks) > 1:
            preview_lines.append(f"# Device {index}: {device_name}")
        elif device_name:
            preview_lines.append(f"# Device: {device_name}")
        preview_lines.extend(commands)
        if index < len(blocks):
            preview_lines.append("")
    return "\n".join(preview_lines).strip()


def _build_fortigate_confirmation_message(preview: str) -> str:
    return (
        "检测到 FortiGate 配置调用。为避免误下发，我已先拦截执行。\n\n"
        "请先确认以下 FortiGate CLI 草案：\n\n"
        f"```cli\n{preview}\n```\n\n"
        "若确认执行，请回复 `确认执行`（或 `confirm`）。\n"
        "若取消执行，请回复 `取消执行`（或 `cancel`）。"
    )


def _build_fortigate_quality_review_message(preview: str) -> str:
    return (
        "检测到 FortiGate 配置调用。请先完成配置质量确认。\n\n"
        "请检查以下 FortiGate CLI 草案：\n\n"
        f"```cli\n{preview}\n```\n\n"
        "若草案有问题，请直接回复要修改的点，我会重新生成。\n"
        "若草案无问题，请回复 `配置无问题`（或 `没问题` / `继续` / `ok`）继续到执行确认。\n"
        "若取消执行，请回复 `取消执行`（或 `cancel`）。"
    )


def _build_pending_confirmation_reminder(preview: str) -> str:
    message = (
        "当前有一个待确认的 FortiGate 配置任务。\n"
        "请回复 `确认执行`（或 `confirm`）继续，或回复 `取消执行`（或 `cancel`）放弃。"
    )
    if preview.strip():
        return f"{message}\n\n```cli\n{preview}\n```"
    return message


def _resolve_topology_prompt_confirmation(
    text: str,
) -> Literal["confirm", "decline", "unknown"]:
    token = _normalize_confirmation_token(text)
    if not token:
        return "unknown"
    if token in {item.replace(" ", "") for item in TOPOLOGY_PROMPT_CONFIRM_KEYWORDS}:
        return "confirm"
    if token in {item.replace(" ", "") for item in TOPOLOGY_PROMPT_DECLINE_KEYWORDS}:
        return "decline"
    return "unknown"


def _build_pending_topology_prompt_reminder() -> str:
    return (
        "我还在等待你的确认：是否要生成完整的原生 gns3-copilot 拓扑部署 prompt？\n"
        "请回复 `是` / `yes` 或 `否` / `no`。"
    )


def _detect_topology_prompt_intent_via_llm(
    messages: list[AnyMessage] | None,
    config: RunnableConfig | None = None,
) -> bool:
    latest_query = _latest_human_text(messages)
    if not latest_query:
        return False

    trace_thread_id, trace_request_id = _extract_trace_context(config)
    trace_context = (
        (trace_thread_id, trace_request_id)
        if trace_thread_id and trace_request_id
        else None
    )
    detector_model = create_base_model(
        trace_context=trace_context,
        model_tag="topology_intent_model",
    )
    detector_messages: list[AnyMessage] = [
        SystemMessage(content=build_topology_intent_detection_prompt()),
        HumanMessage(content=latest_query),
    ]
    detector_response = detector_model.invoke(
        detector_messages, config={"tags": [INTERNAL_LLM_TAG]}
    )
    _log_llm_interaction(
        tag="topology_intent_model",
        inputs=detector_messages,
        output=detector_response,
        config=config,
    )

    detector_text = _stringify_message_content(getattr(detector_response, "content", ""))
    intent_flag, confidence = parse_topology_intent_result(detector_text)
    logger.info(
        "Topology intent detection: intent=%s confidence=%.2f query=%s",
        intent_flag,
        confidence,
        latest_query[:120],
    )
    return bool(intent_flag and confidence >= TOPOLOGY_INTENT_MIN_CONFIDENCE)


def _build_topology_spec_extraction_prompt() -> str:
    """Build system prompt for extracting structured topology spec draft."""
    return (
        "你是拓扑需求结构化提取器。请从用户自然语言中提取 JSON 草案。"
        "仅输出 JSON，不要输出解释。\n"
        "字段约束：\n"
        "- uses_fortigate: bool\n"
        "- lan_count: int 或 null（1-4）\n"
        "- use_switch: bool 或 null（未提及时 null）\n"
        "- use_nat: bool 或 null（未提及时 null）\n"
        "- include_license: bool 或 null（仅 FortiGate 场景）\n"
        "- fortigate_name: string 或 null\n"
        "- fortigate_template: string 或 null\n"
        "- dns_server: string 或 null\n"
        "- license_restore_command: string 或 null\n"
        "输出示例：\n"
        '{"uses_fortigate": true, "lan_count": 2, "use_switch": null, "use_nat": null, '
        '"include_license": null, "fortigate_name": "fortigate1", "fortigate_template": "FortiGate7.6.6模板"}'
    )


def _extract_topology_prompt_spec_with_llm(
    user_request: str,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Extract initial topology spec draft via internal LLM call."""
    request_text = str(user_request or "").strip()
    if not request_text:
        return {}

    trace_thread_id, trace_request_id = _extract_trace_context(config)
    trace_context = (
        (trace_thread_id, trace_request_id)
        if trace_thread_id and trace_request_id
        else None
    )
    extraction_model = create_base_model(
        trace_context=trace_context,
        model_tag="topology_spec_model",
    )
    extraction_messages: list[AnyMessage] = [
        SystemMessage(content=_build_topology_spec_extraction_prompt()),
        HumanMessage(content=request_text),
    ]
    extraction_response = extraction_model.invoke(
        extraction_messages, config={"tags": [INTERNAL_LLM_TAG]}
    )
    _log_llm_interaction(
        tag="topology_spec_model",
        inputs=extraction_messages,
        output=extraction_response,
        config=config,
    )

    content_text = _stringify_message_content(
        getattr(extraction_response, "content", "")
    ).strip()
    parsed = _parse_json_payload(content_text)
    if isinstance(parsed, dict):
        return parsed

    # 兜底：模型偶尔会在 JSON 前后带解释，尝试截取首尾大括号再解析。
    # Fallback: some providers wrap JSON with extra prose; salvage object span.
    start = content_text.find("{")
    end = content_text.rfind("}")
    if start >= 0 and end > start:
        parsed = _parse_json_payload(content_text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    return {}


def _select_topology_skill_names(
    user_request: str,
    draft_spec: dict[str, Any] | None = None,
) -> list[str]:
    """Select internal skill docs used for topology prompt generation."""
    skill_names = [TOPOLOGY_ORCHESTRATOR_SKILL_NAME]
    spec = draft_spec if isinstance(draft_spec, dict) else {}
    use_fortigate_from_spec = _safe_bool(spec.get("uses_fortigate"), default=False)
    if use_fortigate_from_spec or is_fortigate_request(user_request):
        skill_names.append(FORTIGATE_TOPOLOGY_SKILL_NAME)
    return skill_names


def _contains_clarification_block(text: str) -> bool:
    lowered = str(text or "").lower()
    return "```clarify_options" in lowered or "'''clarify_options" in lowered


def _invoke_topology_skill_session_llm(
    *,
    session: dict[str, Any],
    conversation_messages: list[AnyMessage],
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    Run one skill-driven generation turn.

    设计说明（中文）:
    - 本函数采用“skill.md 约束 + LLM 编排”模式，而非硬模板填槽。
    - LLM 可以先提单题澄清（clarify_options），也可以直接产出最终 prompt。
    """
    request_text = str(session.get("user_request", "")).strip()
    if not request_text:
        return {
            "status": "invalid",
            "output_text": "未检测到可生成拓扑 prompt 的需求描述。",
            "missing_requirements": ["缺少原始用户需求"],
            "session": session,
        }

    active_skill_names = session.get("active_skill_names", [])
    if not isinstance(active_skill_names, list) or not active_skill_names:
        active_skill_names = [TOPOLOGY_ORCHESTRATOR_SKILL_NAME]
        session["active_skill_names"] = active_skill_names

    active_skill_documents: list[tuple[str, str]] = []
    for skill_name in active_skill_names:
        document = load_topology_skill_markdown(str(skill_name))
        if document.strip():
            active_skill_documents.append((str(skill_name), document))

    reference_prompt = load_simple_fgt_reference()
    system_prompt = build_topology_skill_generation_prompt(
        user_request=request_text,
        active_skill_documents=active_skill_documents,
        reference_prompt=reference_prompt,
    )

    trace_thread_id, trace_request_id = _extract_trace_context(config)
    trace_context = (
        (trace_thread_id, trace_request_id)
        if trace_thread_id and trace_request_id
        else None
    )
    prompt_model = create_base_model(
        trace_context=trace_context,
        model_tag="topology_prompt_model",
    )

    normalized_messages = [
        _normalize_message_for_model(message) for message in conversation_messages
    ]
    recent_messages = normalized_messages[-10:]
    generation_messages: list[AnyMessage] = [
        SystemMessage(content=build_clarification_choice_prompt()),
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"原始用户需求：{request_text}"),
        *recent_messages,
    ]

    generation_response = prompt_model.invoke(
        generation_messages, config={"tags": [INTERNAL_LLM_TAG]}
    )
    _log_llm_interaction(
        tag="topology_prompt_model",
        inputs=generation_messages,
        output=generation_response,
        config=config,
    )

    output_text = _stringify_message_content(
        getattr(generation_response, "content", "")
    ).strip()
    session["round"] = int(session.get("round", 0)) + 1

    if _contains_clarification_block(output_text):
        return {
            "status": "need_clarification",
            "output_text": output_text,
            "missing_requirements": [],
            "session": session,
        }

    validation = validate_native_topology_prompt(
        text=output_text,
        user_request=request_text,
    )
    if validation.get("ok"):
        return {
            "status": "completed",
            "output_text": output_text,
            "missing_requirements": [],
            "session": session,
        }

    candidate_text = output_text
    missing_requirements = list(validation.get("missing_requirements", []))
    for attempt in range(1, TOPOLOGY_PROMPT_MAX_REPAIR_ATTEMPTS + 1):
        repair_messages: list[AnyMessage] = [
            SystemMessage(content=build_clarification_choice_prompt()),
            SystemMessage(content=system_prompt),
            SystemMessage(
                content=build_native_topology_repair_prompt(
                    user_request=request_text,
                    previous_output=candidate_text or "(empty)",
                    missing_requirements=missing_requirements,
                )
            ),
            HumanMessage(content=request_text),
        ]
        repair_response = prompt_model.invoke(
            repair_messages, config={"tags": [INTERNAL_LLM_TAG]}
        )
        _log_llm_interaction(
            tag=f"topology_prompt_model_repair_{attempt}",
            inputs=repair_messages,
            output=repair_response,
            config=config,
        )
        candidate_text = _stringify_message_content(
            getattr(repair_response, "content", "")
        ).strip()

        if _contains_clarification_block(candidate_text):
            return {
                "status": "need_clarification",
                "output_text": candidate_text,
                "missing_requirements": [],
                "session": session,
            }

        validation = validate_native_topology_prompt(
            text=candidate_text,
            user_request=request_text,
        )
        if validation.get("ok"):
            return {
                "status": "completed",
                "output_text": candidate_text,
                "missing_requirements": [],
                "session": session,
            }
        missing_requirements = list(validation.get("missing_requirements", []))

    return {
        "status": "invalid",
        "output_text": candidate_text,
        "missing_requirements": missing_requirements,
        "session": session,
    }


def _is_human_message(message: AnyMessage | None) -> bool:
    if message is None:
        return False
    msg_type = str(getattr(message, "type", "")).lower()
    cls_name = message.__class__.__name__.lower()
    return msg_type == "human" or "human" in cls_name


def _is_rag_enabled() -> bool:
    raw = str(get_config("RAG_ENABLED", "False")).strip().lower()
    return raw in RAG_TRUTHY_VALUES


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in RAG_TRUTHY_VALUES


def _extract_latest_fortinet_doc_result(
    messages: list[AnyMessage] | None,
) -> dict[str, Any] | None:
    if not isinstance(messages, list) or not messages:
        return None

    last_message = messages[-1]
    if not isinstance(last_message, ToolMessage):
        return None

    if str(getattr(last_message, "name", "")) != FORTINET_DOC_SEARCH_TOOL_NAME:
        return None

    payload = _parse_json_payload(getattr(last_message, "content", None))
    if isinstance(payload, dict):
        return payload
    return None


def _build_strict_no_evidence_message(payload: dict[str, Any]) -> str:
    product = str(payload.get("product", get_config("RAG_DEFAULT_PRODUCT", "fortigate")))
    version = str(payload.get("version", get_config("RAG_DEFAULT_VERSION", "7.6.6")))

    clarify_payload = {
        "kind": "clarification_choice",
        "question_id": "fortinet_doc_scope",
        "question": "你希望我优先检索哪个配置方向？",
        "options": [
            {
                "id": "policy",
                "label": "防火墙策略",
                "value": "请优先检索防火墙策略和地址对象相关章节",
            },
            {
                "id": "interface",
                "label": "接口与地址",
                "value": "请优先检索接口 IP、zone 和管理口相关章节",
            },
            {
                "id": "route",
                "label": "路由与下一跳",
                "value": "请优先检索静态路由/动态路由相关章节",
            },
            {
                "id": "nat",
                "label": "NAT",
                "value": "请优先检索 SNAT/DNAT/central NAT 相关章节",
            },
        ],
        "allow_free_text": True,
    }

    return (
        f"我没有在 `{product} {version}` 文档中检索到足够证据，"
        "为保证准确性，我不会直接生成配置命令。\\n\\n"
        "请告诉我你最关心的配置方向，我会按该方向继续检索。\\n\\n"
        f"```clarify_options\\n{json.dumps(clarify_payload, ensure_ascii=False, indent=2)}\\n```"
    )


def _build_auto_retrieval_tool_call(
    query: str,
    llm_calls: int,
) -> dict[str, Any]:
    product = str(get_config("RAG_DEFAULT_PRODUCT", "fortigate")).strip() or "fortigate"
    version = str(get_config("RAG_DEFAULT_VERSION", "7.6.6")).strip() or "7.6.6"
    top_k = max(1, _safe_int(get_config("RAG_TOP_K", "6"), 6))

    return {
        "name": FORTINET_DOC_SEARCH_TOOL_NAME,
        "args": {
            "query": query,
            "product": product,
            "version": version,
            "top_k": top_k,
        },
        "id": f"call_auto_fortinet_doc_search_{max(0, llm_calls)}",
        "type": "tool_call",
    }


def _extract_trace_context(config: Any) -> tuple[str | None, str | None]:
    """Extract thread_id and trace_request_id from LangGraph config."""
    if not isinstance(config, dict):
        return None, None

    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None, None

    thread_id = configurable.get("thread_id")
    request_id = configurable.get("trace_request_id")

    return (
        str(thread_id) if thread_id else None,
        str(request_id) if request_id else None,
    )


def _log_llm_interaction(
    tag: str,
    inputs: list[AnyMessage],
    output: AnyMessage,
    config: RunnableConfig | None = None,
) -> None:
    """Write one readable LLM round into prompt_trace and emit concise summary log."""
    input_payload = [_serialize_message_for_log(msg) for msg in inputs]
    output_payload = _serialize_message_for_log(output)
    thread_id, request_id = _extract_trace_context(config)

    if not thread_id or not request_id:
        logger.info(
            "[LLM_TRACE][%s] skipped: missing thread_id/trace_request_id", tag
        )
        return

    try:
        trace_info = append_llm_trace_round(
            thread_id=thread_id,
            request_id=request_id,
            model_tag=tag,
            input_payload=input_payload,
            output_payload=output_payload,
        )
        logger.info(
            "[LLM_TRACE][%s] request=%s round=%s file=%s",
            tag,
            trace_info["request_number"],
            trace_info["round_number"],
            trace_info["file_path"],
        )
    except Exception as exc:
        logger.warning("[LLM_TRACE][%s] write failed: %s", tag, exc)


# Define llm call node
# 定义 LLM 调用节点
def llm_call(state: dict, config: RunnableConfig | None = None):
    """LLM decides whether to call a tool or not. LLM 决定是否调用工具。"""

    current_prompt = load_system_prompt()
    # print(current_prompt)

    # Get the previously stored project tuple
    # 获取之前存储的项目元组
    selected_p = state.get("selected_project")

    # Construct context messages
    # 构建上下文消息
    context_messages = []
    topology_info = None
    dry_run_enabled = is_topology_dry_run_enabled()
    simulated_topology = state.get("simulated_topology")

    if selected_p:
        # Convert tuple information to natural language to tell LLM which project user selected
        # 将元组信息转换为自然语言告诉 LLM 用户选择了哪个项目
        project_info = (
            "User has selected project: "
            f"Project_Name={selected_p[0]}, "
            f"Project_ID={selected_p[1]}, "
            f"Device_Number={selected_p[2]}, "
            f"Link_Number={selected_p[3]}, "
            f"Status={selected_p[4]}"
        )
        logger.debug("Project info for LLM context: %s", project_info)

        if dry_run_enabled:
            simulated_topology = initialize_simulated_topology(
                selected_project=selected_p,
                existing_topology=simulated_topology,
            )
            topology_info = build_topology_reader_output(simulated_topology)
            topology_context = str(topology_info)
            logger.debug("Dry-run topology context for LLM:\n%s", topology_context)
            context_messages.append(
                SystemMessage(
                    content=f"Current Context: {project_info}\n\nTopology:\n{topology_context}"
                )
            )
        else:
            # Try to retrieve topology information
            # 尝试获取拓扑信息
            try:
                topology_tool = GNS3TopologyTool()
                topology = topology_tool._run(project_id=selected_p[1])

                if topology and "error" not in topology:
                    topology_info = topology
                    logger.info(
                        "Successfully retrieved topology for project: %s", selected_p[0]
                    )

                    # Convert topology dict to string for LLM consumption
                    # 将拓扑字典转换为字符串供 LLM 使用
                    topology_context = str(topology)
                    logger.debug("Topology context for LLM:\n%s", topology_context)
                    context_messages.append(
                        SystemMessage(
                            content=f"Current Context: {project_info}\n\nTopology:\n{topology_context}"
                        )
                    )
                else:
                    logger.warning(
                        "Failed to retrieve topology: %s",
                        topology.get("error", "Unknown error"),
                    )
                    context_messages.append(
                        SystemMessage(content=f"Current Context: {project_info}")
                    )
            except Exception as e:
                logger.warning("Error retrieving topology: %s", e)
                context_messages.append(
                    SystemMessage(content=f"Current Context: {project_info}")
                )

    context_messages.append(
        SystemMessage(content=build_clarification_choice_prompt())
    )

    fortigate_context = should_inject_fortigate_prompt(
        messages=state.get("messages", []),
        topology_info=topology_info,
        simulated_topology=simulated_topology,
    )
    if fortigate_context:
        include_completeness_intent = not dry_run_enabled
        context_messages.append(
            SystemMessage(
                content=build_fortinet_baseline_prompt(
                    include_completeness_intent=include_completeness_intent
                )
            )
        )

    if dry_run_enabled and fortigate_context:
        logger.info("Injecting FortiGate dry-run persona-only strategy prompt")
        context_messages.append(
            SystemMessage(content=build_fortigate_strategy_prompt())
        )

    # Merge message lists
    # 合并消息列表
    normalized_messages = [
        _normalize_message_for_model(message) for message in state["messages"]
    ]
    full_messages = (
        [SystemMessage(content=current_prompt)] + context_messages + normalized_messages
    )
    # print(full_messages)
    messages = state.get("messages", [])
    last_message = messages[-1] if isinstance(messages, list) and messages else None
    latest_human_text = _latest_human_text(messages)

    quality_pending_reset: dict[str, Any] = {}
    pending_quality_call = state.get("pending_fortigate_quality_call")
    pending_quality_preview = str(state.get("pending_fortigate_quality_preview", "") or "")
    if isinstance(pending_quality_call, dict):
        quality_decision = _resolve_fortigate_quality_review(latest_human_text)
        if quality_decision == "pass":
            confirmation_message = AIMessage(
                content=_build_fortigate_confirmation_message(pending_quality_preview)
            )
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=confirmation_message,
                config=config,
            )
            result = {
                "messages": [confirmation_message],
                "topology_info": topology_info,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
                "pending_fortigate_config_call": pending_quality_call,
                "pending_fortigate_config_preview": pending_quality_preview,
            }
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        if quality_decision == "cancel":
            canceled_message = AIMessage(
                content=(
                    "已取消本次 FortiGate 配置执行。"
                    "请告诉我你希望如何调整配置，我会重新生成草案。"
                )
            )
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=canceled_message,
                config=config,
            )
            result = {
                "messages": [canceled_message],
                "topology_info": topology_info,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
            }
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        # Any other reply is treated as revision feedback; clear quality pending
        # and let this user message flow into a normal LLM regeneration turn.
        quality_pending_reset = {
            "pending_fortigate_quality_call": None,
            "pending_fortigate_quality_preview": None,
        }

    pending_call = state.get("pending_fortigate_config_call")
    pending_preview = str(state.get("pending_fortigate_config_preview", "") or "")
    if isinstance(pending_call, dict):
        decision = _resolve_fortigate_confirmation(latest_human_text)
        if decision == "confirm":
            confirmed_message = AIMessage(content="", tool_calls=[pending_call])
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=confirmed_message,
                config=config,
            )
            result: dict[str, Any] = {
                "messages": [confirmed_message],
                "topology_info": topology_info,
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
            }
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        if decision == "cancel":
            canceled_message = AIMessage(
                content=(
                    "已取消本次 FortiGate 配置执行。"
                    "请告诉我你希望如何调整配置，我会重新生成草案。"
                )
            )
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=canceled_message,
                config=config,
            )
            result = {
                "messages": [canceled_message],
                "topology_info": topology_info,
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
            }
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        reminder_message = AIMessage(
            content=_build_pending_confirmation_reminder(pending_preview)
        )
        _log_llm_interaction(
            tag="base_model",
            inputs=full_messages,
            output=reminder_message,
            config=config,
        )
        result = {
            "messages": [reminder_message],
            "topology_info": topology_info,
        }
        if dry_run_enabled and simulated_topology is not None:
            result["simulated_topology"] = simulated_topology
        return result

    pending_topology_skill_session = state.get("pending_topology_skill_session")
    if isinstance(pending_topology_skill_session, dict):
        # skill 会话期间由 LLM 按 skill.md 继续推进（提问或给最终 prompt）。
        # During an active skill session, LLM keeps driving next clarification/final output.
        session_result = _invoke_topology_skill_session_llm(
            session=dict(pending_topology_skill_session),
            conversation_messages=messages,
            config=config,
        )
        status = str(session_result.get("status", "invalid"))
        output_text = str(session_result.get("output_text", "")).strip()

        if status == "need_clarification":
            clarification_message = AIMessage(content=output_text)
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=clarification_message,
                config=config,
            )
            result = {
                "messages": [clarification_message],
                "topology_info": topology_info,
                "pending_topology_prompt_request": None,
                "pending_topology_prompt_context": state.get(
                    "pending_topology_prompt_context"
                ),
                "pending_topology_skill_session": session_result.get("session"),
                "pending_clarification_question": (
                    {"raw_text": output_text}
                    if _contains_clarification_block(output_text)
                    else None
                ),
                "topology_prompt_spec": session_result.get("session", {}).get(
                    "draft_spec"
                ),
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
            }
            if quality_pending_reset:
                result.update(quality_pending_reset)
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        if status == "completed":
            generated_message = AIMessage(content=output_text)
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=generated_message,
                config=config,
            )
            result = {
                "messages": [generated_message],
                "topology_info": topology_info,
                "pending_topology_prompt_request": None,
                "pending_topology_prompt_context": None,
                "pending_topology_skill_session": None,
                "pending_clarification_question": None,
                "topology_prompt_spec": session_result.get("session", {}).get(
                    "draft_spec"
                ),
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
            }
            if quality_pending_reset:
                result.update(quality_pending_reset)
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        missing_requirements = list(session_result.get("missing_requirements", []))
        fallback_message = AIMessage(
            content=build_topology_prompt_missing_requirements_question(
                user_request=str(
                    session_result.get("session", {}).get(
                        "user_request", latest_human_text
                    )
                ),
                missing_requirements=missing_requirements,
            )
        )
        _log_llm_interaction(
            tag="base_model",
            inputs=full_messages,
            output=fallback_message,
            config=config,
        )
        result = {
            "messages": [fallback_message],
            "topology_info": topology_info,
            "pending_topology_prompt_request": None,
            "pending_topology_prompt_context": {
                "missing_requirements": missing_requirements
            },
            "pending_topology_skill_session": session_result.get("session"),
            "pending_clarification_question": None,
            "topology_prompt_spec": session_result.get("session", {}).get("draft_spec"),
            "pending_fortigate_config_call": None,
            "pending_fortigate_config_preview": None,
            "pending_fortigate_quality_call": None,
            "pending_fortigate_quality_preview": None,
        }
        if quality_pending_reset:
            result.update(quality_pending_reset)
        if dry_run_enabled and simulated_topology is not None:
            result["simulated_topology"] = simulated_topology
        return result

    pending_topology_prompt = state.get("pending_topology_prompt_request")
    pending_topology_context = state.get("pending_topology_prompt_context")
    if isinstance(pending_topology_prompt, dict):
        topology_decision = _resolve_topology_prompt_confirmation(latest_human_text)
        if topology_decision == "confirm":
            request_text = str(
                pending_topology_prompt.get("user_request", latest_human_text)
            ).strip() or latest_human_text
            # 先抽取草案用于技能选择，再由 skill.md 驱动 LLM 执行主流程。
            draft_spec = _extract_topology_prompt_spec_with_llm(
                user_request=request_text,
                config=config,
            )
            active_skill_names = _select_topology_skill_names(
                user_request=request_text,
                draft_spec=draft_spec,
            )
            session = {
                "user_request": request_text,
                "active_skill_names": active_skill_names,
                "draft_spec": draft_spec,
                "round": 0,
            }
            session_result = _invoke_topology_skill_session_llm(
                session=session,
                conversation_messages=messages,
                config=config,
            )
            session_status = str(session_result.get("status", "invalid"))
            session_output = str(session_result.get("output_text", "")).strip()

            if session_status == "need_clarification":
                clarification_message = AIMessage(content=session_output)
                _log_llm_interaction(
                    tag="base_model",
                    inputs=full_messages,
                    output=clarification_message,
                    config=config,
                )
                result = {
                    "messages": [clarification_message],
                    "topology_info": topology_info,
                    "pending_topology_prompt_request": None,
                    "pending_topology_prompt_context": pending_topology_context,
                    "pending_topology_skill_session": session_result.get("session"),
                    "pending_clarification_question": (
                        {"raw_text": session_output}
                        if _contains_clarification_block(session_output)
                        else None
                    ),
                    "topology_prompt_spec": draft_spec,
                    "pending_fortigate_config_call": None,
                    "pending_fortigate_config_preview": None,
                    "pending_fortigate_quality_call": None,
                    "pending_fortigate_quality_preview": None,
                }
                if quality_pending_reset:
                    result.update(quality_pending_reset)
                if dry_run_enabled and simulated_topology is not None:
                    result["simulated_topology"] = simulated_topology
                return result

            if session_status == "completed":
                generated_message = AIMessage(content=session_output)
                _log_llm_interaction(
                    tag="base_model",
                    inputs=full_messages,
                    output=generated_message,
                    config=config,
                )
                result = {
                    "messages": [generated_message],
                    "topology_info": topology_info,
                    "pending_topology_prompt_request": None,
                    "pending_topology_prompt_context": None,
                    "pending_topology_skill_session": None,
                    "pending_clarification_question": None,
                    "topology_prompt_spec": draft_spec,
                    "pending_fortigate_config_call": None,
                    "pending_fortigate_config_preview": None,
                    "pending_fortigate_quality_call": None,
                    "pending_fortigate_quality_preview": None,
                }
                if quality_pending_reset:
                    result.update(quality_pending_reset)
                if dry_run_enabled and simulated_topology is not None:
                    result["simulated_topology"] = simulated_topology
                return result

            missing_requirements = list(session_result.get("missing_requirements", []))
            missing_message = AIMessage(
                content=build_topology_prompt_missing_requirements_question(
                    user_request=request_text,
                    missing_requirements=missing_requirements,
                )
            )
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=missing_message,
                config=config,
            )
            result = {
                "messages": [missing_message],
                "topology_info": topology_info,
                "pending_topology_prompt_request": None,
                "pending_topology_prompt_context": {
                    "missing_requirements": missing_requirements,
                },
                "pending_topology_skill_session": session_result.get("session"),
                "pending_clarification_question": None,
                "topology_prompt_spec": draft_spec,
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
            }
            if quality_pending_reset:
                result.update(quality_pending_reset)
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        if topology_decision == "decline":
            decline_message = AIMessage(
                content=(
                    "好的，我先不生成完整拓扑 prompt。"
                    "我会继续按常规方式协助你，请告诉我下一步要做什么。"
                )
            )
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=decline_message,
                config=config,
            )
            result = {
                "messages": [decline_message],
                "topology_info": topology_info,
                "pending_topology_prompt_request": None,
                "pending_topology_prompt_context": None,
                "pending_topology_skill_session": None,
                "pending_clarification_question": None,
                "topology_prompt_spec": None,
            }
            if quality_pending_reset:
                result.update(quality_pending_reset)
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

        reminder_message = AIMessage(content=_build_pending_topology_prompt_reminder())
        _log_llm_interaction(
            tag="base_model",
            inputs=full_messages,
            output=reminder_message,
            config=config,
        )
        result = {
            "messages": [reminder_message],
            "topology_info": topology_info,
            "pending_topology_prompt_request": pending_topology_prompt,
            "pending_topology_prompt_context": pending_topology_context,
            "pending_topology_skill_session": None,
            "pending_clarification_question": None,
        }
        if quality_pending_reset:
            result.update(quality_pending_reset)
        if dry_run_enabled and simulated_topology is not None:
            result["simulated_topology"] = simulated_topology
        return result

    should_ask_topology_confirmation = False
    if _is_human_message(last_message) and not quality_pending_reset:
        try:
            should_ask_topology_confirmation = _detect_topology_prompt_intent_via_llm(
                messages=messages,
                config=config,
            )
        except Exception as exc:
            logger.warning("Topology intent detection failed: %s", exc)

    if should_ask_topology_confirmation and latest_human_text:
        confirmation_message = AIMessage(
            content=build_topology_prompt_confirmation_message(latest_human_text)
        )
        _log_llm_interaction(
            tag="base_model",
            inputs=full_messages,
            output=confirmation_message,
            config=config,
        )
        result = {
            "messages": [confirmation_message],
            "topology_info": topology_info,
            "pending_topology_prompt_request": {
                "user_request": latest_human_text,
            },
            "pending_topology_prompt_context": {
                "selected_project": selected_p,
                "has_topology_info": isinstance(topology_info, dict),
            },
            "pending_fortigate_config_call": None,
            "pending_fortigate_config_preview": None,
            "pending_fortigate_quality_call": None,
            "pending_fortigate_quality_preview": None,
            "pending_topology_skill_session": None,
            "pending_clarification_question": None,
            "topology_prompt_spec": None,
        }
        if quality_pending_reset:
            result.update(quality_pending_reset)
        if dry_run_enabled and simulated_topology is not None:
            result["simulated_topology"] = simulated_topology
        return result

    rag_tool_result = _extract_latest_fortinet_doc_result(messages)
    if isinstance(rag_tool_result, dict) and _safe_bool(
        rag_tool_result.get("no_evidence"), default=False
    ):
        no_evidence_message = AIMessage(
            content=_build_strict_no_evidence_message(rag_tool_result)
        )
        _log_llm_interaction(
            tag="base_model",
            inputs=full_messages,
            output=no_evidence_message,
            config=config,
        )
        result = {
            "messages": [no_evidence_message],
            "topology_info": topology_info,
        }
        if quality_pending_reset:
            result.update(quality_pending_reset)
        if dry_run_enabled and simulated_topology is not None:
            result["simulated_topology"] = simulated_topology
        return result

    # Enforce retrieval-first behavior for Fortinet requests.
    if _is_rag_enabled() and fortigate_context and _is_human_message(last_message):
        latest_query = _latest_human_text(messages)
        if latest_query:
            retrieval_tool_call = _build_auto_retrieval_tool_call(
                query=latest_query,
                llm_calls=state.get("llm_calls", 0),
            )
            retrieval_message = AIMessage(content="", tool_calls=[retrieval_tool_call])
            _log_llm_interaction(
                tag="base_model",
                inputs=full_messages,
                output=retrieval_message,
                config=config,
            )
            result = {
                "messages": [retrieval_message],
                "topology_info": topology_info,
            }
            if quality_pending_reset:
                result.update(quality_pending_reset)
            if dry_run_enabled and simulated_topology is not None:
                result["simulated_topology"] = simulated_topology
            return result

    # Create fresh model with tools for each LLM call
    # This ensures configuration changes in .env take effect immediately
    # 为每次 LLM 调用创建新的带工具的模型
    # 这确保 .env 中的配置更改立即生效
    trace_thread_id, trace_request_id = _extract_trace_context(config)
    trace_context = (
        (trace_thread_id, trace_request_id)
        if trace_thread_id and trace_request_id
        else None
    )
    model_with_tools = create_base_model_with_tools(
        tools,
        trace_context=trace_context,
        model_tag="base_model",
    )
    llm_response = model_with_tools.invoke(full_messages)
    pending_update: dict[str, Any] = {}
    fortigate_tool_call = _find_fortigate_config_tool_call(
        getattr(llm_response, "tool_calls", None),
        topology_info=topology_info,
        simulated_topology=simulated_topology,
    )
    if fortigate_tool_call:
        preview_text = _render_fortigate_cli_preview(
            fortigate_tool_call,
            topology_info=topology_info,
            simulated_topology=simulated_topology,
        )
        if dry_run_enabled:
            llm_response = AIMessage(
                content=_build_fortigate_quality_review_message(preview_text)
            )
            pending_update = {
                "pending_fortigate_quality_call": fortigate_tool_call,
                "pending_fortigate_quality_preview": preview_text,
                "pending_fortigate_config_call": None,
                "pending_fortigate_config_preview": None,
            }
        else:
            llm_response = AIMessage(
                content=_build_fortigate_confirmation_message(preview_text)
            )
            pending_update = {
                "pending_fortigate_config_call": fortigate_tool_call,
                "pending_fortigate_config_preview": preview_text,
                "pending_fortigate_quality_call": None,
                "pending_fortigate_quality_preview": None,
            }

    _log_llm_interaction(
        tag="base_model",
        inputs=full_messages,
        output=llm_response,
        config=config,
    )

    result: dict[str, Any] = {
        "messages": [llm_response],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "topology_info": topology_info,
    }
    if quality_pending_reset:
        result.update(quality_pending_reset)
    if pending_update:
        result.update(pending_update)
    if dry_run_enabled and simulated_topology is not None:
        result["simulated_topology"] = simulated_topology
    return result


# Define generate title node
# 定义生成标题节点
def generate_title(
    state: MessagesState,
    config: RunnableConfig | None = None,
) -> dict:
    """
    Generate a conversation title using a lightweight assistant LLM (title_model).
    This node is only executed when no title has been set yet (first round only).
    使用轻量级助手 LLM（title_model）生成对话标题。
    此节点仅在尚未设置标题时执行（仅第一轮）。
    """

    # Only generate a title if it hasn't been set yet
    # 仅在尚未设置标题时生成标题
    if state.get("conversation_title") in [None, "New Session"]:
        messages = state["messages"]

        # Build the prompt for title generation
        # 构建用于生成标题的提示
        title_prompt_messages = [
            SystemMessage(content=TITLE_PROMPT),
            messages[0],  # User's first message 用户的第一条消息
            messages[-1],  # Assistant's final response in this turn 助手在此轮的最终响应
        ]
        logger.debug("summary_messages for title generation: %s", title_prompt_messages)

        # Call the title generation model (create fresh instance for each call)
        # 调用标题生成模型（为每次调用创建新实例）
        try:
            # Create fresh title model instance from current env configuration
            # 从当前 env 配置创建新的标题模型实例
            trace_thread_id, trace_request_id = _extract_trace_context(config)
            trace_context = (
                (trace_thread_id, trace_request_id)
                if trace_thread_id and trace_request_id
                else None
            )
            title_model = create_title_model(
                trace_context=trace_context,
                model_tag="title_model",
            )
            title_response = title_model.invoke(
                title_prompt_messages,
                config={
                    "configurable": {"foo_temperature": 1.0},
                    "tags": [INTERNAL_LLM_TAG],
                },
            )
            _log_llm_interaction(
                tag="title_model",
                inputs=title_prompt_messages,
                output=title_response,
                config=config,
            )
            logger.debug("generate_title: %s", title_response)
            raw_content = title_response.content
            logger.debug("Raw title output from model: %s", raw_content)

            new_title = raw_content.strip()

            # Safety: truncate long titles and avoid line breaks
            # 安全处理：截断过长标题并避免换行
            if len(new_title) > 40:  # Increased limit for better Chinese support
                                      # 增加限制以更好地支持中文
                new_title = new_title[:38] + "..."

            # Remove unwanted characters
            # 删除不需要的字符
            new_title = new_title.replace("\n", " ").replace('"', "").replace("'", "")

            if not new_title:
                new_title = "GNS3 Session"

            logger.info("Generated new title: %s", new_title)
            return {"conversation_title": new_title}

        except Exception as e:
            logger.error("Title generation failed: %s", e)
            return {"conversation_title": "Untitled Session"}

    # Title already exists → no update needed
    # 标题已存在 → 无需更新
    return {}


# Define tool node
# 定义工具节点
def tool_node(state: dict):
    """Performs the tool call. 执行工具调用。"""

    result = []
    dry_run_enabled = is_topology_dry_run_enabled()
    simulated_topology = state.get("simulated_topology")

    if dry_run_enabled:
        simulated_topology = initialize_simulated_topology(
            selected_project=state.get("selected_project"),
            existing_topology=simulated_topology,
        )

    for tool_call in state["messages"][-1].tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})

        if dry_run_enabled and tool_name in DRY_RUN_TOOL_NAMES:
            try:
                observation, simulated_topology = execute_dry_run_tool(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    simulated_topology=simulated_topology,
                )
            except Exception as exc:
                logger.exception("Dry-run tool execution failed for %s", tool_name)
                observation = {
                    "error": f"Dry-run execution failed for {tool_name}: {exc}"
                }
        else:
            tool = tools_by_name[tool_name]
            observation = tool.invoke(tool_args)

        result.append(
            ToolMessage(
                content=observation,
                tool_call_id=tool_call["id"],
                name=tool_name,
            )
        )

    response: dict[str, Any] = {"messages": result}
    if dry_run_enabled and simulated_topology is not None:
        response["simulated_topology"] = simulated_topology
        response["topology_info"] = build_topology_reader_output(simulated_topology)
    return response


# Routing logic after the LLM node
# LLM 节点后的路由逻辑
def should_continue(
    state: MessagesState,
) -> Literal["tool_node", "title_generator_node", END]:
    """
    Determine the next step after the LLM has produced a response.
    确定 LLM 生成响应后的下一步。

    - If the LLM requested any tool calls → route to tool_node
      如果 LLM 请求任何工具调用 → 路由到 tool_node
    - If this is the first complete turn (llm_calls == 1) and no title exists → generate a title
      如果这是第一个完整轮次（llm_calls == 1）且没有标题 → 生成标题
    - Otherwise → conversation is complete, go to END
      否则 → 对话完成，转到 END
    """
    last_message = state["messages"][-1]
    llm_calls = state.get("llm_calls", 0)
    current_title = state.get("conversation_title")

    # LLM requested one or more tool executions
    # LLM 请求一个或多个工具执行
    if last_message.tool_calls:
        logger.debug(
            "LLM requested %s tool call(s) → routing to 'tool_node'",
            len(last_message.tool_calls),
        )
        return "tool_node"

    # First full interaction completed and title not yet generated
    # 第一次完整交互完成且标题尚未生成
    if current_title in [None, "GNS3 Session"]:
        logger.info(
            "First turn finished, no title yet → routing to 'title_generator_node'"
        )
        return "title_generator_node"

    # Normal completion (multi-turn conversation or title already exists)
    # 正常完成（多轮对话或标题已存在）
    logger.debug(
        "Conversation turn complete (llm_calls= %s ) → routing to END", llm_calls
    )
    return END


# Routing logic after the tool node, Check remaining_steps
# 工具节点后的路由逻辑，检查剩余步骤
def recursion_limit_continue(state: MessagesState) -> Literal["llm_call", END]:
    """
    Routing logic after tool execution to prevent infinite recursion.
    工具执行后的路由逻辑，防止无限递归。

    Determines whether to continue with another LLM call or end the conversation
    based on remaining steps and message type.
    根据剩余步骤和消息类型确定是继续另一个 LLM 调用还是结束对话。

    Args:
        state: Current conversation state with messages and remaining steps
               包含消息和剩余步骤的当前对话状态

    Returns:
        "llm_call" to continue processing, END to terminate conversation
        "llm_call" 继续处理，END 终止对话

    Logic:
        - If the last message is ToolMessage and steps >= 4: continue to LLM
          如果最后一条消息是 ToolMessage 且步骤 >= 4：继续到 LLM
        - Otherwise: end the conversation to prevent infinite loops
          否则：结束对话以防止无限循环
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        if state["remaining_steps"] < 4:
            return END
        return "llm_call"

    return END


# Build and compile the agent
# 构建并编译代理
# Build workflow
# 构建工作流
agent_builder = StateGraph(MessagesState)

# Add nodes
# 添加节点
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("title_generator_node", generate_title)

# Add edges to connect nodes
# 添加边以连接节点
agent_builder.add_edge(START, "llm_call")
# Conditional routing after LLM response
# Determines the next step based on whether LLM needs to call tools or generate title
# LLM 响应后的条件路由
# 根据 LLM 是否需要调用工具或生成标题来确定下一步
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node",  # Route to tool execution if LLM requested tools
                                    # 如果 LLM 请求工具则路由到工具执行
        "title_generator_node": "title_generator_node",  # Generate title on first interaction
                                                          # 在第一次交互时生成标题
        END: END,  # End conversation if no tools needed 如果不需要工具则结束对话
    },
)
# Conditional routing after tool execution
# Prevents infinite recursion by checking remaining steps before continuing
# 工具执行后的条件路由
# 通过在继续之前检查剩余步骤来防止无限递归
agent_builder.add_conditional_edges(
    "tool_node",
    recursion_limit_continue,
    {
        "llm_call": "llm_call",  # Continue to LLM if tools executed and steps remain
                                  # 如果工具已执行且步骤剩余则继续到 LLM
        END: END,  # End conversation to prevent infinite loops 结束对话以防止无限循环
    },
)

agent_builder.add_edge("title_generator_node", END)

# Add checkpointing
# 添加检查点
LANGGRAPH_DB_PATH = "gns3_langgraph.db"


@st.cache_resource(show_spinner="Initializing conversation persistence...")
def get_checkpointer() -> SqliteSaver:
    """
    Create and cache a single SqliteSaver instance for the entire app lifetime.
    为整个应用程序生命周期创建并缓存单个 SqliteSaver 实例。

    Important notes:
    - `check_same_thread=False` is required because Streamlit runs in a multi-threaded environment.
    - The returned checkpointer is automatically shared across all user sessions.
    重要说明：
    - 需要 `check_same_thread=False`，因为 Streamlit 在多线程环境中运行。
    - 返回的检查点器自动在所有用户会话之间共享。
    """
    conn = sqlite3.connect(LANGGRAPH_DB_PATH, check_same_thread=False)
    # SqliteSaver will create the necessary tables on first use
    # SqliteSaver 将在首次使用时创建必要的表
    return SqliteSaver(conn)


# Compile the agent
# 编译代理
@st.cache_resource(show_spinner="Compiling LangGraph agent...")
def get_agent():
    """
    Compile and cache the LangGraph agent.
    编译并缓存 LangGraph 代理。

    Args:
        checkpointer: Optional checkpointer for persistence.
                     If None, uses the default SqliteSaver for Streamlit.
                     用于持久化的可选检查点器。
                     如果为 None，则使用 Streamlit 的默认 SqliteSaver。
    """
    return agent_builder.compile(
        checkpointer=get_checkpointer(),
    )


langgraph_checkpointer = get_checkpointer()  # Cached SqliteSaver instance 缓存的 SqliteSaver 实例

# Streamlit UI use
# Streamlit UI 使用
agent = get_agent()  # Cached compiled LangGraph agent (with persistence)
                     # 缓存的编译后 LangGraph 代理（带持久化）
