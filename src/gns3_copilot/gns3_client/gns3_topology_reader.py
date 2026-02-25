"""
This module provides a LangChain BaseTool to retrieve the topology of a
 specific GNS3 project by project ID.
此模块提供 LangChain BaseTool，用于通过项目 ID 检索特定 GNS3 项目的拓扑。
"""

import copy
from typing import Any

from langchain.tools import BaseTool

from gns3_copilot.gns3_client import Project, get_gns3_connector
from gns3_copilot.log_config import setup_tool_logger

# Configure logging
# 配置日志
logger = setup_tool_logger("gns3_topology_reader")


# Define LangChain tool class
# 定义 LangChain 工具类
class GNS3TopologyTool(BaseTool):
    """LangChain tool for retrieving GNS3 project topology information.
    用于检索 GNS3 项目拓扑信息的 LangChain 工具。"""

    name: str = "gns3_topology_reader"
    description: str = """
    Retrieves the topology of a GNS3 project including nodes and links.

    Input: `project_id` (str, required): UUID of the GNS3 project.

    Output: Dictionary with:
    - `project_id`, `name`, `status`: Project metadata
    - `nodes`: Dict of node details (node_id, name, ports, console_port, type, etc.)
    - `links`: List of link connections

    Use this to understand network structure before making changes.
    """

    def _run(
        self,
        tool_input: Any = None,
        run_manager: Any = None,
        project_id: str | None = None,
    ) -> dict:
        """
        Synchronous method to retrieve the topology of a specific GNS3 project.
        同步方法，用于检索特定 GNS3 项目的拓扑。

        Args: 参数：
            tool_input : Input parameters, typically a dict or Pydantic model containing server_url.
                         输入参数，通常是包含 server_url 的字典或 Pydantic 模型。
            run_manager : Callback manager for tool run. 工具运行的回调管理器。
            project_id : The UUID of the specific GNS3 project to retrieve topology from.
                         要检索拓扑的特定 GNS3 项目的 UUID。

        Returns: 返回：
            dict: A dictionary containing the project ID, name, status, nodes, and links,
                  or an error dictionary if an exception occurs or project_id is not provided.
                  包含项目 ID、名称、状态、节点和链路的字典，
                  如果发生异常或未提供 project_id 则返回错误字典。
        """

        # Log received input
        # 记录接收到的输入
        logger.info("Received tool_input: %s, project_id: %s", tool_input, project_id)

        try:
            # Validate project_id parameter
            # 验证 project_id 参数
            if not project_id:
                logger.error("project_id parameter is required.")
                return {
                    "error": "project_id parameter is required. Please provide a valid project UUID."
                }

            # Initialize Gns3Connector using factory function
            # 使用工厂函数初始化 Gns3Connector
            logger.info("Connecting to GNS3 server...")
            server = get_gns3_connector()

            if server is None:
                logger.error("Failed to create GNS3 connector")
                return {
                    "error": "Failed to connect to GNS3 server. Please check your configuration."
                }

            # Use the provided project_id directly
            # 直接使用提供的 project_id
            logger.info(f"Retrieving topology for project_id: {project_id}")
            project = Project(project_id=project_id, connector=server)
            project.get()  # Load project details

            # Get topology JSON: includes nodes (devices), links, etc.
            # 获取拓扑 JSON：包括节点（设备）、链路等
            topology = {
                "project_id": project.project_id,
                "name": project.name,
                "status": project.status,
                "nodes": self._clean_nodes_ports(
                    copy.deepcopy(project.nodes_inventory())
                ),
                "links": project.links_summary(is_print=False),
            }

            # Log topology result
            # 记录拓扑结果
            logger.info("Topology retrieved: %s", topology)

            return topology

        except Exception as e:
            logger.error("Error retrieving GNS3 topology: %s", str(e))
            return {"error": f"Failed to retrieve topology: {str(e)}"}

    def _clean_nodes_ports(self, data: dict) -> dict:
        """
        Clean and simplify the nodes data structure.
        Simplify each node's ports list to only keep name and short_name fields.
        清理并简化节点数据结构。
        简化每个节点的端口列表，只保留 name 和 short_name 字段。
        """
        for node in data.values():  # Iterate through R-1, R-2, R-3, R-4
            if "ports" in node and isinstance(node["ports"], list):
                node["ports"] = [
                    {"name": port["name"], "short_name": port["short_name"]}
                    for port in node["ports"]
                ]
        return data


if __name__ == "__main__":
    from pprint import pprint

    # Test the tool
    # 测试工具
    tool = GNS3TopologyTool()

    # Example usage with project_id
    # Replace with an actual project UUID from your GNS3 server
    # 使用 project_id 的示例用法
    # 替换为您 GNS3 服务器上的实际项目 UUID
    example_project_id = "0c0fde25-6ead-4413-a283-ea8fd2324291"

    print("Testing GNS3TopologyTool with project_id...")
    result = tool._run(project_id=example_project_id)
    pprint(result)

    # Test without project_id (should return error)
    # 不带 project_id 测试（应返回错误）
    print("\nTesting without project_id (should return error)...")
    error_result = tool._run()
    pprint(error_result)
