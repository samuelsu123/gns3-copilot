"""
GNS3 Copilot Checkpoint Utilities
GNS3 Copilot 检查点工具

This module provides utility functions for interacting with LangGraph checkpoint
database, including thread ID listing, checkpoint export, import, validation,
and session inspection.
此模块提供与 LangGraph 检查点数据库交互的实用函数，包括线程 ID 列表、
检查点导出、导入、验证和会话检查。
"""

import json
import uuid
from typing import Any

from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.pregel import Pregel
from langgraph.types import RunnableConfig

from gns3_copilot.log_config import setup_logger

logger = setup_logger("checkpoint_utils")


def list_thread_ids(checkpointer: Any) -> list[str]:
    """
    Get all unique thread IDs from LangGraph checkpoint database.
    从 LangGraph 检查点数据库获取所有唯一的线程 ID。

    Args:
        checkpointer: LangGraph checkpointer instance. LangGraph 检查点实例。

    Returns:
        list: List of unique thread IDs ordered by most recent activity.
              Returns empty list on error or if table doesn't exist.
              按最近活动排序的唯一线程 ID 列表。
              出错或表不存在时返回空列表。
    """
    try:
        res = checkpointer.conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY rowid DESC"
        ).fetchall()
        return [r[0] for r in res]
    except Exception as e:
        # Table might not exist yet, return empty list
        # 表可能还不存在，返回空列表
        logger.debug("Error listing thread IDs (table may not exist): %s", e)
        return []


def generate_thread_id() -> str:
    """
    Generate a new unique thread ID.
    生成新的唯一线程 ID。

    Returns:
        str: A UUID-based thread ID. 基于 UUID 的线程 ID。
    """
    return str(uuid.uuid4())


def validate_checkpoint_data(data: Any) -> tuple[bool, str]:
    """
    Validate checkpoint data structure.
    验证检查点数据结构。

    Ensures the imported checkpoint data has the required structure for
    importing into LangGraph checkpointer.
    确保导入的检查点数据具有导入 LangGraph 检查点所需的结构。

    Args:
        data: Dictionary containing checkpoint data. 包含检查点数据的字典。

    Returns:
        tuple: (is_valid, error_message)
               - is_valid: True if data is valid, False otherwise
                           如果数据有效则为 True，否则为 False
               - error_message: Empty string if valid, error description if invalid
                                如果有效则为空字符串，如果无效则为错误描述
    """
    # Check if data is a dictionary
    # 检查数据是否为字典
    if not isinstance(data, dict):
        return False, "Data must be a dictionary"

    # Check if checkpoint field exists
    # 检查 checkpoint 字段是否存在
    if "checkpoint" not in data:
        return False, "Missing required field: checkpoint"

    checkpoint = data["checkpoint"]

    # Check if checkpoint is a dictionary
    # 检查 checkpoint 是否为字典
    if not isinstance(checkpoint, dict):
        return False, "checkpoint must be a dictionary"

    # Check required top-level fields in checkpoint
    # 检查 checkpoint 中必需的顶层字段
    required_fields = ["v", "ts", "id", "channel_values", "channel_versions"]
    if not all(field in checkpoint for field in required_fields):
        missing = [f for f in required_fields if f not in checkpoint]
        return False, f"Missing required checkpoint field: {missing[0]}"

    # Check if channel_values is a dictionary
    # 检查 channel_values 是否为字典
    channel_values = checkpoint["channel_values"]
    if not isinstance(channel_values, dict):
        return False, "channel_values must be a dictionary"

    # Check if messages field exists in channel_values
    # 检查 channel_values 中是否存在 messages 字段
    if "messages" not in channel_values:
        return False, "Missing required field: channel_values.messages"

    # Check if messages is a list
    # 检查 messages 是否为列表
    if not isinstance(channel_values["messages"], list):
        return False, "channel_values.messages must be a list"

    # All validations passed
    # 所有验证通过
    return True, ""


def parse_message_string(msg_str: str) -> dict:
    """
    Parse a message string representation back to a dictionary.
    将消息字符串表示解析回字典。

    Handles the format: "content='xxx' additional_kwargs={} response_metadata={}"
    处理格式："content='xxx' additional_kwargs={} response_metadata={}"

    Args:
        msg_str: String representation of a LangChain message.
                 LangChain 消息的字符串表示。

    Returns:
        dict: Parsed message data with type and content.
              包含类型和内容的解析后消息数据。
    """
    import re

    # Try to determine message type from string content
    # 尝试从字符串内容确定消息类型
    msg_type = "unknown"

    # Check for ToolMessage pattern (has tool_call_id or tool_name)
    # 检查 ToolMessage 模式（包含 tool_call_id 或 tool_name）
    if "tool_call_id=" in msg_str or "name=" in msg_str:
        msg_type = "tool"
    # Check for AIMessage pattern (has tool_calls or is an AI response)
    # 检查 AIMessage 模式（包含 tool_calls 或是 AI 响应）
    elif "tool_calls=" in msg_str:
        msg_type = "ai"
    else:
        # Default to human if no other indicators
        # 如果没有其他指示则默认为 human
        msg_type = "human"

    # Extract content using regex
    # 使用正则表达式提取内容
    content_match = re.search(r"content='([^']*)'|content=\"([^\"]*)\"", msg_str)
    content = (
        content_match.group(1)
        if content_match and content_match.group(1)
        else (
            content_match.group(2) if content_match and content_match.group(2) else ""
        )
    )

    return {"type": msg_type, "content": content, "original_string": msg_str}


def serialize_message(msg: Any) -> dict:
    """
    Serialize a LangChain message to a dictionary for JSON storage.
    将 LangChain 消息序列化为字典以便 JSON 存储。

    Ensures all message fields are properly serialized for UI compatibility,
    including tool_calls structure for AIMessage and all metadata fields.
    确保所有消息字段都正确序列化以便 UI 兼容，
    包括 AIMessage 的 tool_calls 结构和所有元数据字段。

    Args:
        msg: LangChain message object (HumanMessage, AIMessage, or ToolMessage)
             or a string representation of a message.
             LangChain 消息对象（HumanMessage、AIMessage 或 ToolMessage）
             或消息的字符串表示。

    Returns:
        dict: Serialized message with type, content, and all metadata.
              包含类型、内容和所有元数据的序列化消息。
    """
    # If it's already a string (stored in database), parse it
    # 如果已经是字符串（存储在数据库中），则解析它
    if isinstance(msg, str):
        return parse_message_string(msg)

    if isinstance(msg, HumanMessage):
        return {
            "type": "human",
            "content": msg.content,
            "additional_kwargs": msg.additional_kwargs,
            "response_metadata": msg.response_metadata,
            "id": msg.id,
        }
    elif isinstance(msg, AIMessage):
        # Serialize tool_calls with complete structure
        # 使用完整结构序列化 tool_calls
        tool_calls = []
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tool_call.get("id", ""),
                        "name": tool_call.get("name", ""),
                        "args": tool_call.get("args", {}),
                        "type": tool_call.get("type", "tool_call"),
                    }
                )

        return {
            "type": "ai",
            "content": msg.content,
            "additional_kwargs": msg.additional_kwargs,
            "response_metadata": msg.response_metadata,
            "tool_calls": tool_calls,
            "id": msg.id,
        }
    elif isinstance(msg, ToolMessage):
        return {
            "type": "tool",
            "content": msg.content,
            "tool_call_id": msg.tool_call_id,
            "name": msg.name,
            "additional_kwargs": msg.additional_kwargs,
            "response_metadata": msg.response_metadata,
            "id": msg.id,
        }
    else:
        # For any other message types, try to serialize as dict
        # 对于任何其他消息类型，尝试序列化为字典
        return {"type": "unknown", "content": str(msg)}


def deserialize_message(msg_dict: dict) -> Any:
    """
    Deserialize a dictionary back to a LangChain message object.
    将字典反序列化回 LangChain 消息对象。

    Ensures proper reconstruction of message objects with all required fields
    for UI compatibility, including tool_calls structure for AIMessage.
    确保正确重建具有所有必需字段的消息对象以便 UI 兼容，
    包括 AIMessage 的 tool_calls 结构。

    Args:
        msg_dict: Dictionary containing serialized message data.
                  包含序列化消息数据的字典。

    Returns:
        LangChain message object (HumanMessage, AIMessage, or ToolMessage).
        LangChain 消息对象（HumanMessage、AIMessage 或 ToolMessage）。

    Raises:
        ValueError: If message type is unknown or required fields are missing.
                    如果消息类型未知或缺少必需字段。
    """
    msg_type = msg_dict.get("type", "unknown")

    if msg_type == "human":
        return HumanMessage(
            content=msg_dict.get("content", ""),
            additional_kwargs=msg_dict.get("additional_kwargs", {}),
            response_metadata=msg_dict.get("response_metadata", {}),
            id=msg_dict.get("id"),
        )
    elif msg_type == "ai":
        # Reconstruct tool_calls with proper structure
        # 使用正确结构重建 tool_calls
        tool_calls = []
        serialized_tool_calls = msg_dict.get("tool_calls", [])

        if serialized_tool_calls:
            for tool_call in serialized_tool_calls:
                # Handle both dict and list formats
                # 处理字典和列表两种格式
                if isinstance(tool_call, dict):
                    tool_calls.append(
                        {
                            "id": tool_call.get("id", ""),
                            "name": tool_call.get("name", ""),
                            "args": tool_call.get("args", {}),
                            "type": tool_call.get("type", "tool_call"),
                        }
                    )

        return AIMessage(
            content=msg_dict.get("content", ""),
            additional_kwargs=msg_dict.get("additional_kwargs", {}),
            response_metadata=msg_dict.get("response_metadata", {}),
            tool_calls=tool_calls,
            id=msg_dict.get("id"),
        )
    elif msg_type == "tool":
        return ToolMessage(
            content=msg_dict.get("content", ""),
            tool_call_id=msg_dict.get("tool_call_id", ""),
            name=msg_dict.get("name", ""),
            additional_kwargs=msg_dict.get("additional_kwargs", {}),
            response_metadata=msg_dict.get("response_metadata", {}),
            id=msg_dict.get("id"),
        )
    else:
        # Return as dict for unknown types
        # 对于未知类型返回字典
        logger.warning("Unknown message type: %s, returning dict", msg_type)
        return msg_dict


def export_checkpoint_to_file(
    checkpointer: Any, thread_id: str, file_path: str
) -> bool:
    """
    Export checkpoint data to a .txt file in JSON format.
    将检查点数据导出到 JSON 格式的 .txt 文件。

    Exports the checkpoint data for a specific thread to a text file.
    The exported data includes the complete checkpoint state with messages,
    conversation title, config, and metadata. Messages are properly serialized
    to ensure they can be correctly deserialized on import.
    将特定线程的检查点数据导出到文本文件。
    导出的数据包括完整的检查点状态（包含消息、对话标题、配置和元数据）。
    消息被正确序列化以确保导入时可以正确反序列化。

    Args:
        checkpointer: LangGraph checkpointer instance. LangGraph 检查点实例。
        thread_id: The thread ID to export. 要导出的线程 ID。
        file_path: Path to the output .txt file. 输出 .txt 文件的路径。

    Returns:
        bool: True if export succeeded, False otherwise.
              如果导出成功则为 True，否则为 False。
    """
    try:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple = checkpointer.get_tuple(config)

        if checkpoint_tuple is None:
            logger.error("Checkpoint not found for thread_id: %s", thread_id)
            return False

        # Create a copy of checkpoint data to avoid modifying the original
        # 创建检查点数据的副本以避免修改原始数据
        checkpoint_data = dict(checkpoint_tuple.checkpoint)

        # Serialize messages for proper JSON export
        # 序列化消息以便正确导出 JSON
        if (
            "channel_values" in checkpoint_data
            and "messages" in checkpoint_data["channel_values"]
        ):
            messages = checkpoint_data["channel_values"]["messages"]
            serialized_messages = [serialize_message(msg) for msg in messages]
            checkpoint_data["channel_values"]["messages"] = serialized_messages

        # Save complete checkpoint data including config and metadata
        # 保存完整的检查点数据，包括配置和元数据
        export_data = {
            "checkpoint": checkpoint_data,
            "config": checkpoint_tuple.config,
            "metadata": checkpoint_tuple.metadata,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        logger.info("Checkpoint exported to %s for thread_id: %s", file_path, thread_id)
        return True

    except Exception as e:
        logger.error("Failed to export checkpoint: %s", e)
        return False


def validate_messages_for_ui(messages: list) -> tuple[bool, str, list[str]]:
    """
    Validate that messages can be correctly rendered by the UI.
    验证消息是否可以被 UI 正确渲染。

    Checks that all messages are proper LangChain message objects with
    required fields for UI rendering (chat.py compatibility).
    检查所有消息是否是具有 UI 渲染所需字段的正确 LangChain 消息对象
    （chat.py 兼容性）。

    Args:
        messages: List of message objects to validate. 要验证的消息对象列表。

    Returns:
        tuple: (is_valid, error_message, validation_errors)
               - is_valid: True if all messages are valid for UI
                           如果所有消息对 UI 有效则为 True
               - error_message: Summary error message 摘要错误消息
               - validation_errors: List of specific validation errors per message
                                    每条消息的具体验证错误列表
    """
    validation_errors = []

    if not messages:
        return True, "", []

    for idx, msg in enumerate(messages):
        msg_error = f"Message {idx}: "

        # Check if message is a recognized type
        # 检查消息是否为已识别的类型
        if isinstance(msg, HumanMessage):
            # HumanMessage requires content
            # HumanMessage 需要 content
            if not hasattr(msg, "content") or msg.content is None:
                validation_errors.append(msg_error + "Missing content field")
            continue
        elif isinstance(msg, AIMessage):
            # AIMessage should have content and tool_calls
            # AIMessage 应该有 content 和 tool_calls
            if not hasattr(msg, "content"):
                validation_errors.append(msg_error + "Missing content field")

            # Validate tool_calls if present
            # 如果存在 tool_calls 则验证
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_idx, tool_call in enumerate(msg.tool_calls):
                    required_fields = ["id", "name", "args"]
                    missing = [f for f in required_fields if f not in tool_call]
                    if missing:
                        validation_errors.append(
                            f"{msg_error} Tool call {tool_idx} missing: {', '.join(missing)}"
                        )
            continue
        elif isinstance(msg, ToolMessage):
            # ToolMessage requires content, tool_call_id, and name
            # ToolMessage 需要 content、tool_call_id 和 name
            if not hasattr(msg, "content"):
                validation_errors.append(msg_error + "Missing content field")
            if not hasattr(msg, "tool_call_id") or not msg.tool_call_id:
                validation_errors.append(msg_error + "Missing or empty tool_call_id")
            if not hasattr(msg, "name") or not msg.name:
                validation_errors.append(msg_error + "Missing or empty name")
            continue
        else:
            validation_errors.append(
                f"{msg_error} Unknown message type: {type(msg).__name__}"
            )
            continue

    is_valid = len(validation_errors) == 0
    error_message = "; ".join(validation_errors) if validation_errors else ""

    return is_valid, error_message, validation_errors


def inspect_session(
    thread_id: str, graph: Pregel, verbose: bool = False
) -> dict[str, Any]:
    """
    Inspect and return human-readable session state using graph.get_state().
    使用 graph.get_state() 检查并返回人类可读的会话状态。

    Provides detailed information about a session including message statistics,
    UI compatibility, and current execution state.
    提供关于会话的详细信息，包括消息统计、UI 兼容性和当前执行状态。

    Args:
        thread_id: Thread ID to inspect. 要检查的线程 ID。
        graph: Compiled LangGraph agent instance. 编译后的 LangGraph 代理实例。
        verbose: If True, include detailed message contents in output.
                 如果为 True，则在输出中包含详细的消息内容。

    Returns:
        dict: Human-readable session information including:
              人类可读的会话信息，包括：
            - next: Next action to be executed 下一个要执行的操作
            - message_count: Number of messages 消息数量
            - message_types: Dictionary counting message types 消息类型计数字典
            - latest_message: Content of latest message 最新消息的内容
            - step: Current step number 当前步骤号
            - pending_tasks: Number of pending tasks 待处理任务数量
            - has_interrupts: Whether there are interrupts 是否有中断
            - conversation_title: Session title 会话标题
            - selected_project: Currently selected GNS3 project 当前选中的 GNS3 项目
            - ui_compatible: Whether messages are compatible with UI 消息是否与 UI 兼容
            - validation_errors: List of validation errors (if any) 验证错误列表（如果有）
            - messages_preview: Preview of messages (if verbose=True) 消息预览（如果 verbose=True）
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        snapshot = graph.get_state(config)

        # Extract message information
        # 提取消息信息
        messages = snapshot.values.get("messages", [])
        message_count = len(messages)

        # Count message types
        # 统计消息类型
        message_types = {"human": 0, "ai": 0, "tool": 0, "unknown": 0}
        for msg in messages:
            if isinstance(msg, HumanMessage):
                message_types["human"] += 1
            elif isinstance(msg, AIMessage):
                message_types["ai"] += 1
            elif isinstance(msg, ToolMessage):
                message_types["tool"] += 1
            else:
                message_types["unknown"] += 1

        # Get latest message content
        # 获取最新消息内容
        latest_message = None
        if messages:
            latest_msg = messages[-1]
            if hasattr(latest_msg, "content"):
                if isinstance(latest_msg.content, str):
                    latest_message = latest_msg.content
                elif isinstance(latest_msg.content, list) and latest_msg.content:
                    # Handle Gemini format (list with text field)
                    # 处理 Gemini 格式（包含 text 字段的列表）
                    if isinstance(latest_msg.content[0], dict):
                        latest_message = latest_msg.content[0].get(
                            "text", str(latest_msg.content)
                        )
                    else:
                        latest_message = str(latest_msg.content)
                else:
                    latest_message = str(latest_msg.content)

        # Validate UI compatibility
        # 验证 UI 兼容性
        is_valid, error_msg, validation_errors = validate_messages_for_ui(messages)

        # Build result dictionary
        # 构建结果字典
        result = {
            "thread_id": thread_id,
            "next": snapshot.next,
            "message_count": message_count,
            "message_types": message_types,
            "latest_message": latest_message,
            "step": snapshot.metadata.get("step", "N/A")
            if snapshot.metadata
            else "N/A",
            "pending_tasks": len(snapshot.tasks),
            "has_interrupts": len(snapshot.interrupts) > 0,
            "conversation_title": snapshot.values.get("conversation_title"),
            "selected_project": snapshot.values.get("selected_project"),
            "ui_compatible": is_valid,
            "validation_error": error_msg,
            "validation_errors": validation_errors,
        }

        # Add verbose details if requested
        # 如果请求则添加详细信息
        if verbose:
            messages_preview = []
            for idx, msg in enumerate(messages):
                msg_preview = {
                    "index": idx,
                    "type": type(msg).__name__,
                }
                if hasattr(msg, "content"):
                    msg_preview["content"] = str(msg.content)[
                        :200
                    ]  # Truncate long content 截断过长内容
                if (
                    isinstance(msg, AIMessage)
                    and hasattr(msg, "tool_calls")
                    and msg.tool_calls
                ):
                    msg_preview["tool_calls_count"] = len(msg.tool_calls)
                messages_preview.append(msg_preview)
            result["messages_preview"] = messages_preview

        return result

    except Exception as e:
        logger.error("Failed to inspect session %s: %s", thread_id, e)
        return {
            "thread_id": thread_id,
            "error": str(e),
            "message_count": 0,
            "message_types": {"human": 0, "ai": 0, "tool": 0, "unknown": 0},
            "ui_compatible": False,
            "validation_error": f"Failed to get state: {e}",
        }


def import_checkpoint_from_file(
    checkpointer: Any, file_path: str, new_thread_id: str | None = None
) -> tuple[bool, str]:
    """
    Import checkpoint data from a .txt file to a new thread.
    从 .txt 文件导入检查点数据到新线程。

    Reads checkpoint data from a JSON-formatted .txt file and imports it
    into a new thread in the LangGraph checkpointer. The imported data is
    validated and messages are deserialized before insertion.
    从 JSON 格式的 .txt 文件读取检查点数据并将其导入到 LangGraph 检查点的新线程中。
    导入的数据在插入前会被验证并反序列化消息。

    Args:
        checkpointer: LangGraph checkpointer instance. LangGraph 检查点实例。
        file_path: Path to .txt file containing checkpoint data.
                   包含检查点数据的 .txt 文件路径。
        new_thread_id: Optional thread ID for the new thread.
                      If None, a new UUID will be generated.
                      新线程的可选线程 ID。如果为 None，将生成新的 UUID。

    Returns:
        tuple: (success, result)
               - success: True if import succeeded, False otherwise
                          如果导入成功则为 True，否则为 False
               - result: New thread ID if success, error message if failed
                         如果成功则为新线程 ID，如果失败则为错误消息
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Validate checkpoint data structure
        # 验证检查点数据结构
        is_valid, error_msg = validate_checkpoint_data(data)
        if not is_valid:
            logger.error("Invalid checkpoint data: %s", error_msg)
            return False, error_msg

        # Generate new thread ID if not provided
        # 如果未提供则生成新的线程 ID
        if new_thread_id is None:
            new_thread_id = generate_thread_id()

        # Create a copy of checkpoint data to avoid modifying original
        # 创建检查点数据的副本以避免修改原始数据
        checkpoint_data = dict(data["checkpoint"])

        # Deserialize messages if they are in serialized format
        # 如果消息是序列化格式则反序列化
        if (
            "channel_values" in checkpoint_data
            and "messages" in checkpoint_data["channel_values"]
        ):
            messages = checkpoint_data["channel_values"]["messages"]

            # Check if messages are in serialized format (have 'type' field)
            # 检查消息是否为序列化格式（具有 'type' 字段）
            if messages and isinstance(messages[0], dict) and "type" in messages[0]:
                deserialized_messages = []
                for msg_dict in messages:
                    try:
                        deserialized_msg = deserialize_message(msg_dict)
                        deserialized_messages.append(deserialized_msg)
                    except Exception as e:
                        logger.error(
                            "Failed to deserialize message: %s. Error: %s",
                            msg_dict.get("type", "unknown"),
                            e,
                        )
                        # Skip invalid messages or add as dict
                        # 跳过无效消息或作为字典添加
                        deserialized_messages.append(msg_dict)
                checkpoint_data["channel_values"]["messages"] = deserialized_messages

        # Rebuild complete config with all required keys
        # 使用所有必需的键重建完整配置
        saved_config = data.get("config", {})
        new_config = {
            **saved_config,
            "configurable": {
                **saved_config.get("configurable", {}),
                "thread_id": new_thread_id,
                "checkpoint_ns": "",  # Required: checkpoint namespace (empty string)
                                       # 必需：检查点命名空间（空字符串）
                "checkpoint_id": str(uuid.uuid4()),  # Required: new checkpoint ID
                                                      # 必需：新的检查点 ID
            },
        }

        # Use saved metadata if available, otherwise create new
        # 如果可用则使用保存的元数据，否则创建新的
        metadata = data.get("metadata", {"source": "import"})
        if "source" not in metadata:
            metadata["source"] = "import"

        new_versions = checkpoint_data["channel_versions"]

        checkpointer.put(
            config=new_config,
            checkpoint=checkpoint_data,
            metadata=metadata,
            new_versions=new_versions,
        )

        logger.info(
            "Checkpoint imported from %s to new thread_id: %s", file_path, new_thread_id
        )
        return True, new_thread_id

    except FileNotFoundError:
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return False, error_msg
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format in file: {e}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to import checkpoint: {e}"
        logger.error(error_msg)
        return False, error_msg
