"""
GNS3 Copilot Agent Package
GNS3 Copilot 代理包

This package contains the main GNS3 Copilot agent implementation for network automation tasks.
此包包含用于网络自动化任务的主要 GNS3 Copilot 代理实现。
"""

from .checkpoint_utils import (
    export_checkpoint_to_file,
    generate_thread_id,
    import_checkpoint_from_file,
    list_thread_ids,
    validate_checkpoint_data,
)
from .gns3_copilot import agent, langgraph_checkpointer

# Dynamic version management
# 动态版本管理
try:
    from importlib.metadata import version

    __version__ = version("gns3-copilot")
except Exception:
    __version__ = "unknown"

__author__ = "Guobin Yue"
__description__ = "AI-powered network automation assistant for GNS3"
__url__ = "https://github.com/yueguobin/gns3-copilot"

__all__ = [
    "agent",
    "langgraph_checkpointer",
    "list_thread_ids",
    "generate_thread_id",
    "validate_checkpoint_data",
    "export_checkpoint_to_file",
    "import_checkpoint_from_file",
]
