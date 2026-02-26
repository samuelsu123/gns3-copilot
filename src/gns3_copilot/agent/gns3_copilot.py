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

import operator
import sqlite3
import json
from typing import Annotated, Any, Literal

import streamlit as st
from langchain.messages import AnyMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.managed.is_last_step import RemainingSteps
from typing_extensions import TypedDict

from gns3_copilot.agent.model_factory import (
    create_base_model_with_tools,
    create_title_model,
)
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
from gns3_copilot.prompts.fortigate_config_prompt import (
    should_inject_fortigate_prompt,
)
from gns3_copilot.prompts.fortigate_config_strategy import (
    build_fortigate_strategy_prompt,
    get_fortigate_config_strategy,
)
from gns3_copilot.tools_v2 import (
    ExecuteMultipleDeviceCommands,
    ExecuteMultipleDeviceConfigCommands,
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


def _localize_llm_log_tag(tag: str) -> str:
    """Return Chinese tag for common LLM log channels."""
    tag_mapping = {
        "base_model": "主模型",
        "title_model": "标题模型",
    }
    return tag_mapping.get(tag, tag)


def _is_system_payload(payload: dict[str, Any]) -> bool:
    """Check whether serialized payload is a system message (prompt)."""
    return str(payload.get("type", "")).lower() == "system"


def _log_llm_interaction(
    tag: str,
    inputs: list[AnyMessage],
    output: AnyMessage,
) -> None:
    """Log each LLM interaction input and output in structured JSON format."""
    input_payload = [_serialize_message_for_log(msg) for msg in inputs]
    output_payload = _serialize_message_for_log(output)
    input_payload_json = json.dumps(input_payload, ensure_ascii=False)
    output_payload_json = json.dumps(output_payload, ensure_ascii=False)
    localized_tag = _localize_llm_log_tag(tag)
    input_payload_non_prompt = [
        payload for payload in input_payload if not _is_system_payload(payload)
    ]
    input_payload_non_prompt_json = json.dumps(
        input_payload_non_prompt, ensure_ascii=False
    )

    logger.info(
        "[LLM_INTERACTION][%s][INPUT] %s",
        tag,
        input_payload_json,
    )
    if input_payload_non_prompt:
        logger.info(
            "[LLM交互][%s][输入] %s",
            localized_tag,
            input_payload_non_prompt_json,
        )
    logger.info(
        "[LLM_INTERACTION][%s][OUTPUT] %s",
        tag,
        output_payload_json,
    )
    if not _is_system_payload(output_payload):
        logger.info(
            "[LLM交互][%s][输出] %s",
            localized_tag,
            output_payload_json,
        )


# Define llm call node
# 定义 LLM 调用节点
def llm_call(state: dict):
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

    if dry_run_enabled and should_inject_fortigate_prompt(
        messages=state.get("messages", []),
        topology_info=topology_info,
        simulated_topology=simulated_topology,
    ):
        fortigate_strategy = get_fortigate_config_strategy()
        logger.info(
            "Injecting FortiGate dry-run strategy prompt: strategy=%s",
            fortigate_strategy,
        )
        context_messages.append(
            SystemMessage(
                content=build_fortigate_strategy_prompt(
                    topology_info=topology_info,
                    simulated_topology=simulated_topology,
                    strategy=fortigate_strategy,
                )
            )
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

    # Create fresh model with tools for each LLM call
    # This ensures configuration changes in .env take effect immediately
    # 为每次 LLM 调用创建新的带工具的模型
    # 这确保 .env 中的配置更改立即生效
    model_with_tools = create_base_model_with_tools(tools)
    llm_response = model_with_tools.invoke(full_messages)
    _log_llm_interaction(
        tag="base_model",
        inputs=full_messages,
        output=llm_response,
    )

    result: dict[str, Any] = {
        "messages": [llm_response],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "topology_info": topology_info,
    }
    if dry_run_enabled and simulated_topology is not None:
        result["simulated_topology"] = simulated_topology
    return result


# Define generate title node
# 定义生成标题节点
def generate_title(state: MessagesState) -> dict:
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
            title_model = create_title_model()
            title_response = title_model.invoke(
                title_prompt_messages,
                config={"configurable": {"foo_temperature": 1.0}},
            )
            _log_llm_interaction(
                tag="title_model",
                inputs=title_prompt_messages,
                output=title_response,
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
