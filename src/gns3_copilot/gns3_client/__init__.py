"""
GNS3 Client Package
GNS3 客户端包

This package provides a Python interface for interacting with GNS3 servers.
It's adapted from the upstream gns3fy project with modifications for compatibility
with langchain and reduced dependency conflicts.
此包提供用于与 GNS3 服务器交互的 Python 接口。
它改编自上游 gns3fy 项目，并进行了修改以兼容 langchain 并减少依赖冲突。

Main classes: 主要类：
- Gns3Connector: Connector for GNS3 server API interaction
                 用于 GNS3 服务器 API 交互的连接器
- Project: GNS3 Project management GNS3 项目管理
- Node: GNS3 Node management GNS3 节点管理
- Link: GNS3 Link management GNS3 链路管理
- GNS3TopologyTool: GNS3 topology reading tool GNS3 拓扑读取工具
- GNS3ProjectReadFileTool: LangChain tool for reading project files
                           用于读取项目文件的 LangChain 工具
- GNS3ProjectWriteFileTool: LangChain tool for writing project files
                            用于写入项目文件的 LangChain 工具
- GNS3ProjectListFilesTool: LangChain tool for listing project files
                            用于列出项目文件的 LangChain 工具
- GNS3ProjectLock: LangChain tool for locking/unlocking GNS3 projects
                   用于锁定/解锁 GNS3 项目的 LangChain 工具

File Manager Modules: 文件管理模块：
- gns3_project_read_file: GNS3ProjectReadFileTool implementation
                          GNS3ProjectReadFileTool 实现
- gns3_project_write_file: GNS3ProjectWriteFileTool implementation
                           GNS3ProjectWriteFileTool 实现
- gns3_project_list_files: GNS3ProjectListFilesTool implementation
                           GNS3ProjectListFilesTool 实现
- gns3_file_index: File index management utilities 文件索引管理工具

Main functions: 主要函数：
- get_gns3_connector: Factory function to create Gns3Connector from environment
                      从环境创建 Gns3Connector 的工厂函数
"""

from .connector_factory import get_gns3_connector
from .custom_gns3fy import (
    CONSOLE_TYPES,
    LINK_TYPES,
    NODE_TYPES,
    Gns3Connector,
    Link,
    Node,
    Project,
)
from .gns3_create_drawing import GNS3CreateDrawingTool
from .gns3_delete_drawing import GNS3DeleteDrawingTool
from .gns3_file_index import add_file_to_index, get_file_list
from .gns3_get_drawings import GNS3GetDrawingsTool
from .gns3_get_nodes import GNS3GetNodesTool
from .gns3_project_create import GNS3ProjectCreate
from .gns3_project_delete import GNS3ProjectDelete
from .gns3_project_list_files import GNS3ProjectListFilesTool
from .gns3_project_lock import GNS3ProjectLock
from .gns3_project_open import GNS3ProjectOpen
from .gns3_project_path import GNS3ProjectPath
from .gns3_project_read_file import GNS3ProjectReadFileTool
from .gns3_project_update import GNS3ProjectUpdate
from .gns3_project_write_file import GNS3ProjectWriteFileTool
from .gns3_projects_list import GNS3ProjectList
from .gns3_topology_reader import GNS3TopologyTool
from .gns3_update_drawing import GNS3UpdateDrawingTool

# Dynamic version management
try:
    from importlib.metadata import version

    __version__ = version("gns3-copilot")
except Exception:
    __version__ = "unknown"

__author__ = "Guobin Yue"
__description__ = "AI-powered network automation assistant for GNS3"
__url__ = "https://github.com/yueguobin/gns3-copilot"

__all__ = [
    "Gns3Connector",
    "Project",
    "Node",
    "Link",
    "NODE_TYPES",
    "CONSOLE_TYPES",
    "LINK_TYPES",
    "GNS3TopologyTool",
    "GNS3ProjectList",
    "GNS3ProjectOpen",
    "GNS3ProjectPath",
    "GNS3ProjectCreate",
    "GNS3ProjectDelete",
    "GNS3ProjectLock",
    "GNS3ProjectUpdate",
    "GNS3ProjectReadFileTool",
    "GNS3ProjectWriteFileTool",
    "GNS3ProjectListFilesTool",
    "GNS3CreateDrawingTool",
    "GNS3DeleteDrawingTool",
    "GNS3GetDrawingsTool",
    "GNS3GetNodesTool",
    "GNS3UpdateDrawingTool",
    "get_gns3_connector",
    "add_file_to_index",
    "get_file_list",
]
