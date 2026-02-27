# mypy: ignore-errors
"""
GNS3 Copilot - AI-Powered Network Engineering Assistant
GNS3 助手 - AI 驱动的网络工程助手

This module implements the main Streamlit web application for GNS3 Copilot,
an AI-powered assistant designed to help network engineers with GNS3-related
tasks through a conversational chat interface.

本模块实现了 GNS3 Copilot 的主 Streamlit Web 应用程序，
这是一个人工智能驱动的助手，旨在通过对话聊天界面帮助网络工程师完成 GNS3 相关任务。

Features / 功能：
- Real-time chat interface with streaming responses
  实时聊天界面，支持流式响应
- Integration with LangChain agents for intelligent conversation
  与 LangChain 代理集成，实现智能对话
- Tool calling support for GNS3 network operations
  支持工具调用以执行 GNS3 网络操作
- Message history and session state management
  消息历史和会话状态管理
- Support for multiple message types (Human, AI, Tool messages)
  支持多种消息类型（用户消息、AI 消息、工具消息）
- Interactive tool call and response visualization
  交互式工具调用和响应可视化

The application leverages / 应用程序利用：
- Streamlit for the web UI / Streamlit 用于 Web UI
- LangGraph for AI agent functionality / LangGraph 用于 AI 代理功能
- Custom GNS3 integration tools / 自定义 GNS3 集成工具
- Session-based conversation tracking with unique thread IDs / 基于会话的对话跟踪，使用唯一的线程 ID

Usage / 使用方法：
Run this module directly to start the GNS3 Copilot web interface:
直接运行此模块以启动 GNS3 Copilot Web 界面：
    streamlit run app.py

Note: Requires proper configuration of GNS3 server and API credentials.
注意：需要正确配置 GNS3 服务器和 API 凭据。
"""

import json
import uuid
from time import sleep
from typing import Any

import streamlit as st
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from gns3_copilot.agent import agent
from gns3_copilot.agent.prompt_trace import (
    append_fortigate_config_trace,
    end_trace_request,
    start_trace_request,
)
from gns3_copilot.gns3_client import GNS3ProjectList
from gns3_copilot.log_config import setup_logger
from gns3_copilot.ui_model.utils import (
    build_topology_iframe_url,
    generate_topology_iframe_html,
    render_create_project_form,
    render_project_cards,
)
from gns3_copilot.utils import (
    format_tool_response,
    get_duration,
    speech_to_text,
    text_to_speech_wav,
)

logger = setup_logger("chat")


def _parse_bool(value: Any, default: bool = False) -> bool:
    """将会话/配置值解析为布尔值。Parse session/config value to bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _extract_thread_id(config: dict[str, Any]) -> str | None:
    """Extract thread_id from LangGraph config."""
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    thread_id = configurable.get("thread_id")
    return str(thread_id) if thread_id else None


def _build_request_config(
    base_config: dict[str, Any],
    trace_request_id: str,
) -> dict[str, Any]:
    """Inject trace_request_id into a per-request config copy."""
    configurable = dict(base_config.get("configurable", {}))
    configurable["trace_request_id"] = trace_request_id
    return {
        **base_config,
        "configurable": configurable,
    }


def _get_snapshot_values(snapshot: Any) -> dict[str, Any]:
    """从 LangGraph 快照对象中提取状态值。Extract state values from a LangGraph snapshot-like object."""
    if snapshot is None:
        return {}

    values = getattr(snapshot, "values", None)
    if isinstance(values, dict):
        return values
    if isinstance(snapshot, dict):
        return snapshot
    return {}


def _get_config_previews(snapshot: Any) -> list[dict[str, Any]]:
    """Extract dry-run config previews from snapshot values."""
    values = _get_snapshot_values(snapshot)
    simulated_topology = values.get("simulated_topology")
    if not isinstance(simulated_topology, dict):
        return []

    previews = simulated_topology.get("config_previews", [])
    if not isinstance(previews, list):
        return []

    return [item for item in previews if isinstance(item, dict)]


def _is_fortigate_preview(item: dict[str, Any]) -> bool:
    source = str(item.get("source", "")).lower()
    strategy = str(item.get("fortigate_strategy", "")).lower()
    device_name = str(item.get("device_name", "")).lower()
    return (
        "forti" in device_name
        or "fgt" in device_name
        or source.startswith("fortigate_")
        or strategy.startswith("predefined")
        or strategy.startswith("hybrid")
        or strategy.startswith("persona")
    )


def _count_fortigate_previews(snapshot: Any) -> int:
    return sum(1 for item in _get_config_previews(snapshot) if _is_fortigate_preview(item))


def _extract_new_fortigate_config(
    snapshot: Any,
    previous_fortigate_preview_count: int | None,
) -> str | None:
    """Extract pure FortiGate CLI from newly generated preview in current request."""
    if previous_fortigate_preview_count is None:
        return None

    fortigate_previews = [
        item for item in _get_config_previews(snapshot) if _is_fortigate_preview(item)
    ]
    if not fortigate_previews:
        return None

    if previous_fortigate_preview_count >= len(fortigate_previews):
        return None

    candidates = fortigate_previews[previous_fortigate_preview_count:]
    eligible: list[dict[str, Any]] = []
    for item in candidates:
        validation_status = str(item.get("validation_status", "")).lower()
        if validation_status in {"success", "not_validated"}:
            eligible.append(item)

    if not eligible:
        return None

    latest_preview = eligible[-1]
    commands = latest_preview.get("config_commands", [])
    if not isinstance(commands, list):
        return None

    lines = [str(command).strip() for command in commands if str(command).strip()]
    if not lines:
        return None

    return "\n".join(lines)


def _render_simulated_topology_data(snapshot: Any) -> None:
    """如果可用，渲染干运行（dry-run）拓扑数据。Render dry-run topology payload if available."""
    values = _get_snapshot_values(snapshot)
    simulated_topology = values.get("simulated_topology")

    if (
        not isinstance(simulated_topology, dict)
        or simulated_topology.get("mode") != "dry_run"
    ):
        return

    nodes = simulated_topology.get("nodes", [])
    links = simulated_topology.get("links", [])
    drawings = simulated_topology.get("drawings", [])
    config_previews = simulated_topology.get("config_previews", [])

    st.markdown(
        """
        <h4 style='text-align: left; font-size: 18px; font-weight: 700; margin-top: 18px;'>Generated Topology Data (Dry Run)</h4>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Topology write operations are simulated in memory only; no node/link/drawing is created on GNS3 server."
    )

    with st.expander("View generated topology JSON", expanded=True):
        st.json(
            {
                "mode": "dry_run",
                "project_id": simulated_topology.get("project_id"),
                "project_name": simulated_topology.get("project_name"),
                "stats": {
                    "total_nodes": len(nodes),
                    "total_links": len(links),
                    "total_drawings": len(drawings),
                    "total_config_previews": len(config_previews),
                    "total_operations": len(simulated_topology.get("operation_log", [])),
                },
                "nodes": nodes,
                "links": links,
                "drawings": drawings,
                "config_previews": config_previews,
                "operation_log": simulated_topology.get("operation_log", []),
            },
            expanded=False,
        )


# 初始化线程 ID 的会话状态
# Initialize session state for thread ID
if "thread_id" not in st.session_state:
    # 如果会话状态中没有 thread_id，创建并保存一个新的
    # If thread_id is not in session_state, create and save a new one
    st.session_state["thread_id"] = str(uuid.uuid4())

# 初始化 iframe URL 模式（项目页面 vs 登录页面）
# Initialize iframe URL mode (project page vs login page)
if "gns3_url_mode" not in st.session_state:
    st.session_state.gns3_url_mode = "project"

# 初始化 iframe 可见性状态
# Initialize iframe visibility state
# 用于显示/隐藏 GNS3 拓扑界面
# Used to show/hide GNS3 topology interface
if "show_iframe" not in st.session_state:
    st.session_state.show_iframe = False

# 为新会话初始化临时选定的项目
# Initialize temp_selected_project for new sessions
if "temp_selected_project" not in st.session_state:
    st.session_state["temp_selected_project"] = None

# 获取当前线程 ID
current_thread_id = st.session_state["thread_id"]

# 从会话状态获取选定的线程 ID 和标题（由侧边栏设置）
# Get selected thread ID and title from session state (set by sidebar)
selected_thread_id = st.session_state.get("selected_thread_id")
title = st.session_state.get("session_title")


# 为每个会话创建唯一的线程 ID
# Unique thread ID for each session
# 如果选择了一个会话，使用其线程 ID 继续对话；
# 否则初始化一个新的线程 ID
# If a session is selected, continue the conversation using its thread ID;
# otherwise, initialize a new thread ID.
if selected_thread_id:
    config = {
        "configurable": {
            "thread_id": st.session_state["current_thread_id"],
            "max_iterations": 50,
        },
        "recursion_limit": 28,
    }
else:
    config = {
        "configurable": {"thread_id": current_thread_id, "max_iterations": 50},
        "recursion_limit": 28,
    }

# --- 获取当前状态 ---
# --- Get current state ---
if selected_thread_id:
    # 历史会话：从代理状态获取
    # Historical session: get from agent state
    snapshot = agent.get_state(config)
    selected_p = snapshot.values.get("selected_project")
else:
    # 新会话：从临时存储获取
    # New session: get from temp storage
    selected_p = st.session_state.get("temp_selected_project")

dry_run_enabled = _parse_bool(st.session_state.get("TOPOLOGY_DRY_RUN", True), True)

# 在干运行模式下，允许虚拟项目，GNS3 服务器是可选的
# In dry-run mode, allow a virtual project so GNS3 server is optional.
# 当用户只想要生成的拓扑数据时，这避免了项目列表/创建 API 的依赖
# This avoids project list/create API dependency when users only want generated topology data.
if dry_run_enabled and not selected_p:
    dry_run_project = ("Dry Run Project", "dry-run-project-id", 0, 0, "opened")
    if selected_thread_id:
        agent.update_state(config, {"selected_project": dry_run_project})
    else:
        st.session_state["temp_selected_project"] = dry_run_project
    selected_p = dry_run_project

# --- 逻辑分支：如果没有选择项目，显示项目卡片 ---
# --- Logic branch: If no project is selected, display project cards ---
if not selected_p:
    st.markdown(
        """
        <h3 style='text-align: left; font-size: 22px; font-weight: bold; margin-top: 20px;'>GNS3 Copilot - Workspace Selection</h3>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "Please select a project to enter the conversation context. Closed projects can be opened directly.",
        width=800,
    )

    # 渲染创建项目表单
    # Render create project form
    render_create_project_form()

    # 获取项目列表并渲染项目卡片
    # Get project list and render project cards
    projects = GNS3ProjectList()._run().get("projects", [])
    if projects:
        render_project_cards(projects, selected_thread_id, config)
    else:
        st.error("No projects found in GNS3.")
        if st.button("Refresh List"):
            st.rerun()
else:
    # 保存当前项目到会话状态以供侧边栏显示
    # Save current project to session_state for sidebar display
    st.session_state["current_project"] = selected_p

# --- 主工作区（仅在选择项目时可见） ---
# --- Main workspace (only visible when a project is selected) ---
if selected_p:
    # 基于 iframe 可见性的动态列布局
    # Dynamic column layout based on iframe visibility
    if st.session_state.show_iframe:
        layout_col1, layout_col2 = st.columns([3, 7], gap="medium")
    else:
        layout_col1 = st.container()

    with layout_col1:
        history_container = st.container(
            height=st.session_state.CONTAINER_HEIGHT,
            border=False,
        )
        with history_container:
            st.markdown(
                """
                <h3 style='text-align: left; font-size: 22px; font-weight: bold; margin-top: 20px;'>Workspace</h3>
                """,
                unsafe_allow_html=True,
            )
            # 从状态历史显示之前的消息
            # Display previous messages from state history
            if st.session_state.get("state_history") is not None:
                # StateSnapshot 值字典
                # StateSnapshot values dictionary
                values_dict = st.session_state["state_history"].values
                message_to_render = values_dict.get("messages", [])

                # 跟踪当前打开的助手消息块
                # Track current open assistant message block
                current_assistant_block = None

                # 状态快照消息列表
                # StateSnapshot values messages list
                for message_object in message_to_render:
                    # 处理不同的消息类型
                    # Handle different message types
                    if isinstance(message_object, HumanMessage):
                        # Close any open assistant chat message block before starting a new user message
                        if current_assistant_block is not None:
                            current_assistant_block.__exit__(None, None, None)
                            current_assistant_block = None
                        # UserMessage
                        with st.chat_message("user"):
                            st.markdown(message_object.content)

                    elif isinstance(message_object, (AIMessage, ToolMessage)):
                        # Open a new assistant chat message block if none is open
                        if current_assistant_block is None:
                            current_assistant_block = st.chat_message("assistant")
                            current_assistant_block.__enter__()

                        # Handle AIMessage with tool_calls
                        if isinstance(message_object, AIMessage):
                            # AIMessage content
                            # adapted for gemini
                            # Check if content is a list and safely extract the first text element
                            if (
                                isinstance(message_object.content, list)
                                and message_object.content
                                and "text" in message_object.content[0]
                            ):
                                st.markdown(message_object.content[0]["text"])
                            # Plain string content
                            elif isinstance(message_object.content, str):
                                st.markdown(message_object.content)
                            # AIMessage tool_calls
                            if (
                                isinstance(message_object.tool_calls, list)
                                and message_object.tool_calls
                            ):
                                for tool in message_object.tool_calls:
                                    tool_id = tool.get("id", "UNKNOWN_ID")
                                    tool_name = tool.get("name", "UNKNOWN_TOOL")
                                    tool_args = tool.get("args", {})
                                    # Display tool call details
                                    with st.expander(
                                        f"**Tool Call:** `{tool_name}`",
                                        expanded=False,
                                    ):
                                        st.json(
                                            {
                                                # "name": tool_name,
                                                # "id": tool_id,
                                                "tool_input": tool_args.get(
                                                    "tool_input"
                                                ),
                                                # "type": "tool_call",
                                            },
                                            expanded=True,
                                        )
                        # Handle ToolMessage
                        if isinstance(message_object, ToolMessage):
                            content_pretty = format_tool_response(
                                message_object.content
                            )
                            with st.expander(
                                "**Tool Response**",
                                expanded=False,
                            ):
                                st.json(json.loads(content_pretty), expanded=2)

                # Close any remaining open assistant chat message block
                if current_assistant_block is not None:
                    current_assistant_block.__exit__(None, None, None)

                _render_simulated_topology_data(st.session_state.get("state_history"))

    # 仅在 show_iframe 为 True 时渲染 layout_col2 内容
    # Only render layout_col2 content when show_iframe is True
    if st.session_state.show_iframe:
        with layout_col2:
            # 从选定的项目中提取 project_id
            # Extract project_id from the selected project
            project_id = selected_p[
                1
            ]  # selected_p 是一个元组：(name, p_id, dev_count, link_count, status)
            # 基于 API 版本和 URL 模式构建拓扑 iframe URL
            # Build the topology iframe URL based on API version and URL mode
            iframe_url = build_topology_iframe_url(project_id)

            iframe_container = st.container(
                height=st.session_state.CONTAINER_HEIGHT,
                # horizontal_alignment="center",
                vertical_alignment="center",
                border=False,
            )
            with iframe_container:
                # Set zoom scale (0.7 = 70%, 0.8 = 80%, 0.9 = 90%)
                zoom_scale = (
                    st.session_state.zoom_scale_topology
                )  # Scale to 80%, you can adjust between 0.7-0.9

                iframe_html = generate_topology_iframe_html(
                    iframe_url=iframe_url,
                    zoom_scale=zoom_scale,
                    container_height=st.session_state.CONTAINER_HEIGHT,
                )

                st.markdown(iframe_html, unsafe_allow_html=True)

    # st.divider()
    # --- 聊天输入区域 ---
    # --- Chat Input Area ---
    if st.session_state.show_iframe:
        # 显示拓扑时：右侧有两个按钮，需要更宽
        # When Show Topology: there are two buttons on the right, needs to be wider
        # 左列较窄，中列适中，右列较宽
        # Left column is narrow, middle column is moderate, right column is wider
        col_ratio = [0.2, 0.6, 0.4]
    else:
        # 隐藏拓扑时：右侧只有一个按钮
        # When Hide Topology: there is only one button on the right
        # 左列较窄，中列较宽，右列适中
        # Left column is narrow, middle column is wide, right column is moderate
        col_ratio = [0.2, 0.7, 0.3]

    chat_input_left, chat_input_center, chat_input_right = st.columns(col_ratio)

    with chat_input_center:
        # 基于开关配置聊天输入
        # Configure chat_input based on switch
        # 从会话状态获取语音启用设置（从 .env 文件加载）
        # Get voice enabled setting from session_state (loaded from .env file)
        voice_enabled = st.session_state.get("VOICE", False)
        if voice_enabled:
            prompt = st.chat_input(
                "Say or record something...",
                accept_audio=True,
                audio_sample_rate=24000,
                # width=600,
            )
        else:
            # When voice is disabled, do not enable accept_audio attribute
            prompt = st.chat_input(
                "Type your message here...",
                # width=600
            )
        # 处理输入
        # Handle input
        if prompt:
            user_text = ""
            if voice_enabled:
                # 模式 A：prompt 是一个对象（包含 .text 和 .audio）
                # Mode A: prompt is an object (containing .text and .audio)
                if prompt.audio:
                    user_text = speech_to_text(prompt.audio)
                # 如果语音未转换为文本，或用户直接输入
                # If voice is not converted to text, or user directly types
                if not user_text:
                    user_text = prompt.text
            else:
                # 模式 B：prompt 直接是字符串
                # Mode B: prompt is directly a string
                user_text = prompt
            # 3. 最终检查并运行
            # 3. Final check and run
            if not user_text or user_text.strip() == "":
                st.stop()

            with history_container:
                # 在聊天消息容器中显示用户消息
                # Display user message in chat message container
                with st.chat_message("user"):
                    st.markdown(user_text)

            # 将临时选定的项目迁移到新会话的代理状态
            # Migrate temp selected project to agent state for new sessions
            if not selected_thread_id and st.session_state.get("temp_selected_project"):
                temp_project = st.session_state["temp_selected_project"]
                agent.update_state(config, {"selected_project": temp_project})
                # Don't clear temp_selected_project immediately
                # It will be cleared after rerun when selected_p is retrieved from agent state

            trace_request_id = str(uuid.uuid4())
            request_config = _build_request_config(config, trace_request_id)
            trace_thread_id = _extract_thread_id(request_config)
            if trace_thread_id:
                try:
                    start_trace_request(
                        thread_id=trace_thread_id,
                        request_id=trace_request_id,
                        user_prompt=user_text,
                    )
                except Exception as exc:
                    logger.warning(
                        "Prompt trace start failed (thread_id=%s, request_id=%s): %s",
                        trace_thread_id,
                        trace_request_id,
                        exc,
                    )

            previous_fortigate_preview_count: int | None = None
            try:
                previous_state_snapshot = agent.get_state(config)
                previous_fortigate_preview_count = _count_fortigate_previews(
                    previous_state_snapshot
                )
            except Exception as exc:
                logger.debug(
                    "Failed to read pre-request preview state (thread_id=%s): %s",
                    trace_thread_id,
                    exc,
                )

            stream_error: Exception | None = None
            with history_container:
                # 在聊天消息容器中显示助手响应
                # Display assistant response in chat message container
                with st.chat_message("assistant"):
                    active_text_placeholder = st.empty()
                    current_text_chunk = ""
                    # 核心聚合状态：仅存储当前流式工具信息
                    # Core aggregation state: only stores currently streaming tool information
                    # 结构：{'id': str, 'name': str, 'args_string': str} 或 None
                    # Structure: {'id': str, 'name': str, 'args_string': str} or None
                    current_tool_state = None
                    # 用于消息控制的 TTS 本地开关
                    # TTS local switch for message control
                    tts_played = False
                    # 初始化 audio_bytes 变量
                    # Initialize audio_bytes variable
                    audio_bytes = None
                    # 流式传输代理响应
                    # Stream the agent response
                    # 从代理流式获取响应块
                    try:
                        for chunk in agent.stream(
                            {
                                "messages": [HumanMessage(content=user_text)],
                            },
                            config=request_config,
                            stream_mode="messages",
                        ):
                            # 处理每个消息块
                            for msg in chunk:
                                # with open('log.txt', "a", encoding='utf-8') as f:
                                #    f.write(f"{msg}\n\n")
                                if isinstance(msg, AIMessage):
                                    # adapted for gemini
                                    # Check if content is a list and safely extract the first text element
                                    if (
                                        isinstance(msg.content, list)
                                        and msg.content
                                        and "text" in msg.content[0]
                                    ):
                                        actual_text = msg.content[0]["text"]
                                        # Now actual_text is the clean text you need
                                        current_text_chunk += actual_text
                                        # Only display text in non-voice mode
                                        if not voice_enabled:
                                            active_text_placeholder.markdown(
                                                current_text_chunk,
                                                unsafe_allow_html=True,
                                            )
                                    elif isinstance(msg.content, str):
                                        current_text_chunk += str(msg.content)
                                        # Only display text in non-voice mode
                                        if not voice_enabled:
                                            active_text_placeholder.markdown(
                                                current_text_chunk,
                                                unsafe_allow_html=True,
                                            )
                                    # Determine if text message (i.e., msg.content) reception is complete
                                    is_text_ending = (
                                        # Case 1: Tool call starts
                                        msg.tool_calls
                                        or
                                        # Case 2: End metadata received
                                        msg.response_metadata.get("finish_reason")
                                        in ["tool_calls", "stop"]
                                    )
                                    if (
                                        is_text_ending
                                        and not tts_played
                                        and current_text_chunk.strip()
                                        and voice_enabled
                                    ):
                                        # Play once in a round of AIMessage/ToolMessage
                                        tts_played = True
                                        # Text_to_speech
                                        try:
                                            with st.spinner(
                                                "Generating voice...", width=200
                                            ):
                                                audio_bytes = text_to_speech_wav(
                                                    current_text_chunk
                                                )
                                                st.audio(
                                                    audio_bytes,
                                                    format="audio/mp3",
                                                    autoplay=True,
                                                    width=200,
                                                )
                                                # Wait for audio playback to complete
                                                duration = get_duration(audio_bytes)
                                                logger.info(
                                                    "TTS audio duration: %.2f seconds",
                                                    duration,
                                                )
                                                sleep(duration)  # Extra buffer time
                                        except Exception as e:
                                            logger.error("TTS Error: %s", e)
                                            st.error(f"TTS Error: {e}")
                                    # Get metadata (ID and name) from tool_calls
                                    if msg.tool_calls:
                                        for tool in msg.tool_calls:
                                            tool_id = tool.get("id")
                                            # Only when ID is not empty, consider it as the start of a new tool call
                                            if tool_id:
                                                # Initialize current tool state (this is the only time to get ID)
                                                # Note: only one tool can be called at a time
                                                current_tool_state = {
                                                    "id": tool_id,
                                                    "name": tool.get(
                                                        "name", "UNKNOWN_TOOL"
                                                    ),
                                                    "args_string": "",
                                                }
                                    # Concatenate parameter strings from tool_call_chunk
                                    if (
                                        hasattr(msg, "tool_call_chunks")
                                        and msg.tool_call_chunks
                                    ):
                                        if current_tool_state:
                                            tool_data = current_tool_state
                                            for chunk_update in msg.tool_call_chunks:
                                                args_chunk = chunk_update.get(
                                                    "args", ""
                                                )
                                                # Core: string concatenation
                                                if isinstance(args_chunk, str):
                                                    tool_data["args_string"] += args_chunk
                                    # Determine if the tool_calls_chunks output is complete and
                                    # display the st.expander() for tool_calls
                                    if msg.response_metadata.get(
                                        "finish_reason"
                                    ) == "tool_calls" or (
                                        msg.response_metadata.get("finish_reason")
                                        == "STOP"
                                        and current_tool_state is not None
                                    ):
                                        tool_data = current_tool_state
                                        # Parse complete parameter string
                                        parsed_args: dict[str, Any] = {}
                                        try:
                                            parsed_args = json.loads(
                                                tool_data["args_string"]
                                            )
                                        except json.JSONDecodeError:
                                            parsed_args = {
                                                "error": "JSON parse failed after stream complete."
                                            }
                                        # Serialize the tool_input value in parsed_args to a JSON array
                                        # for expansion when using st.json
                                        try:
                                            command_list = json.loads(
                                                parsed_args["tool_input"]
                                            )
                                            parsed_args["tool_input"] = command_list
                                        except (
                                            json.JSONDecodeError,
                                            KeyError,
                                            TypeError,
                                        ):
                                            pass
                                        # Build the final display structure that meets your requirements
                                        display_tool_call = {
                                            "name": tool_data["name"],
                                            "id": tool_data["id"],
                                            # Inject tool_input structure
                                            "tool_input": parsed_args.get("tool_input"),
                                            "type": tool_data.get(
                                                "type", "tool_call"
                                            ),  # Maintain completeness
                                        }
                                        # Update Call Expander, display final parameters (collapsed)
                                        with st.expander(
                                            f"**Tool Call:** `{tool_data['name']}`",
                                            expanded=False,
                                        ):
                                            # Use the final complete structure
                                            st.json(display_tool_call, expanded=False)
                                if isinstance(msg, ToolMessage):
                                    # Clear state after completion, ready to receive next tool call
                                    current_tool_state = None
                                    content_pretty = format_tool_response(msg.content)
                                    with st.expander(
                                        "**Tool Response**",
                                        expanded=False,
                                    ):
                                        st.json(
                                            json.loads(content_pretty), expanded=False
                                        )
                                    active_text_placeholder = st.empty()
                                    current_text_chunk = ""
                                    tts_played = False
                    except Exception as exc:
                        stream_error = exc
                        logger.exception(
                            "Agent stream failed (thread_id=%s, request_id=%s)",
                            trace_thread_id,
                            trace_request_id,
                        )

            # 交互后，使用最新的状态快照更新会话状态
            # After the interaction, update the session state with the latest StateSnapshot
            state_history = None
            try:
                state_history = agent.get_state(config)
            except Exception as exc:
                logger.warning(
                    "Failed to get post-request state (thread_id=%s, request_id=%s): %s",
                    trace_thread_id,
                    trace_request_id,
                    exc,
                )
            # 避免在 state_history 为空时更新
            # Avoid updating if state_history is empty
            if state_history is not None and state_history[0]:
                # 更新会话状态
                # Update session state
                st.session_state["state_history"] = state_history
                with history_container:
                    _render_simulated_topology_data(state_history)
                # print(state_history)
            # with open('state_history.txt', "a", encoding='utf-8') as f:
            #    f.write(f"{state_history}\n\n")

            if trace_thread_id:
                try:
                    fortigate_config = _extract_new_fortigate_config(
                        snapshot=state_history,
                        previous_fortigate_preview_count=previous_fortigate_preview_count,
                    )
                    if fortigate_config:
                        append_fortigate_config_trace(
                            thread_id=trace_thread_id,
                            request_id=trace_request_id,
                            config_text=fortigate_config,
                        )
                except Exception as exc:
                    logger.warning(
                        "Prompt trace FortiGate config append failed (thread_id=%s, request_id=%s): %s",
                        trace_thread_id,
                        trace_request_id,
                        exc,
                    )

                try:
                    end_trace_request(
                        thread_id=trace_thread_id,
                        request_id=trace_request_id,
                        status="failed" if stream_error else "completed",
                        error_message=str(stream_error) if stream_error else None,
                    )
                except Exception as exc:
                    logger.warning(
                        "Prompt trace end failed (thread_id=%s, request_id=%s): %s",
                        trace_thread_id,
                        trace_request_id,
                        exc,
                    )

            if stream_error is not None:
                raise stream_error

    with chat_input_right:
        # 在右列中创建两个子列，按钮从左到右排列
        # Create two sub-columns in the right column, arrange buttons left and right
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(
                "Hide" if st.session_state.show_iframe else "Show",
                icon=":material/visibility:"
                if not st.session_state.show_iframe
                else ":material/visibility_off:",
                help="Show or hide the GNS3 project topology iframe",
            ):
                # 切换 iframe 的可见性
                # Toggle iframe visibility
                st.session_state.show_iframe = not st.session_state.show_iframe
                st.rerun()

        with btn_col2:
            if st.session_state.show_iframe:
                if st.button(
                    "Login"
                    if st.session_state.gns3_url_mode == "project"
                    else "Topology",
                    icon=":material/login:"
                    if st.session_state.gns3_url_mode == "project"
                    else ":material/device_hub:",
                    help="If the page is not displayed, please click me. Need to perform GNS3 web login once.",
                ):
                    # 切换 iframe 的 URL 模式（项目页面 vs 登录页面）
                    # Toggle iframe URL mode (project page vs login page)
                    st.session_state.gns3_url_mode = (
                        "login"
                        if st.session_state.gns3_url_mode == "project"
                        else "project"
                    )
                    st.rerun()

    with chat_input_left:
        # 左列为空布局
        st.empty()
