"""
GNS3 Connector Factory Module
GNS3 连接器工厂模块

This module provides factory functions for creating Gns3Connector instances
based on environment configuration. It encapsulates the logic for reading
GNS3 server settings and creating appropriately configured connectors.
此模块提供基于环境配置创建 Gns3Connector 实例的工厂函数。
它封装了读取 GNS3 服务器设置和创建适当配置的连接器的逻辑。

Main Functions: 主要函数：
    get_gns3_connector: Create a Gns3Connector from environment variables
                        从环境变量创建 Gns3Connector

Example: 示例：
    from gns3_copilot.gns3_client import get_gns3_connector

    connector = get_gns3_connector()
    if connector:
        # Use connector to interact with GNS3 server
        # 使用连接器与 GNS3 服务器交互
        projects = connector.projects
"""

from gns3_copilot.gns3_client.custom_gns3fy import Gns3Connector
from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils import get_config

logger = setup_logger("connector_factory")


def get_gns3_connector() -> Gns3Connector | None:
    """Create and return a Gns3Connector instance from environment variables.
    从环境变量创建并返回 Gns3Connector 实例。

    This factory function reads GNS3 server configuration from environment
    variables and creates an appropriate Gns3Connector instance based on
    the API version. It handles both API v2 (no authentication) and
    API v3 (with username/password authentication).
    此工厂函数从环境变量读取 GNS3 服务器配置，并根据 API 版本创建适当的
    Gns3Connector 实例。它处理 API v2（无需认证）和 API v3（需要用户名/密码认证）。

    The function reads the following environment variables:
    此函数读取以下环境变量：
        - API_VERSION: GNS3 API version ("2" or "3") GNS3 API 版本
        - GNS3_SERVER_URL: GNS3 server URL GNS3 服务器 URL
        - GNS3_SERVER_USERNAME: Username for API v3 authentication API v3 认证用户名
        - GNS3_SERVER_PASSWORD: Password for API v3 authentication API v3 认证密码

    Returns: 返回：
        Gns3Connector instance if configuration is valid, None otherwise
        如果配置有效则返回 Gns3Connector 实例，否则返回 None

    Example: 示例：
        # Create connector from environment 从环境创建连接器
        connector = get_gns3_connector()
        if connector:
            projects = connector.projects
        else:
            logger.error("Failed to create GNS3 connector")
    """
    try:
        # Get GNS3 server configuration from SQLite database
        api_version_str = get_config("API_VERSION")
        server_url = get_config("GNS3_SERVER_URL")

        if not api_version_str:
            logger.error("API_VERSION not configured")
            return None

        if not server_url:
            logger.error("GNS3_SERVER_URL not configured")
            return None

        # Create connector based on API version
        if api_version_str == "2":
            # API v2 does not require authentication
            connector = Gns3Connector(
                url=server_url,
                api_version=int(api_version_str),
            )
            logger.debug("Created Gns3Connector for API v2")
        elif api_version_str == "3":
            # API v3 requires username and password
            username = get_config("GNS3_SERVER_USERNAME")
            password = get_config("GNS3_SERVER_PASSWORD")

            connector = Gns3Connector(
                url=server_url,
                user=username,
                cred=password,
                api_version=int(api_version_str),
            )
            logger.debug("Created Gns3Connector for API v3")
        else:
            logger.error("Unsupported API_VERSION: %s", api_version_str)
            return None

        logger.info("Successfully created Gns3Connector")
        return connector

    except Exception as e:
        logger.error("Failed to create Gns3Connector: %s", str(e))
        return None
