"""GNS3 Copilot 应用配置管理器。

Application Configuration Manager for GNS3 Copilot.

本模块提供了统一的接口来管理存储在SQLite数据库中的应用配置。
它包括所有配置项的默认值和用于读取和保存配置的辅助函数。

This module provides a unified interface for managing application configuration
stored in SQLite database. It includes default values for all configuration
items and helper functions for reading and saving configuration.

Functions/函数:
    get_config(key, default=None): 获取配置值 | Retrieve a configuration value with default
    set_config(key, value): 保存配置值到数据库 | Save a configuration value to database
    get_all_config(): 获取所有配置值 | Retrieve all configuration values
    init_config(): 初始化数据库默认值 | Initialize database with default values

Constants/常量:
    DEFAULT_CONFIG: 包含所有配置键和默认值的字典 | Dictionary containing all configuration keys and their defaults
"""

from typing import Any

from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils.config_db import (
    clear_all,
    get_all_values,
    get_value,
    init_db,
    set_value,
)

logger = setup_logger("app_config")

# GNS3 Copilot 所有应用设置的默认配置值
# Default configuration values for all application settings
DEFAULT_CONFIG: dict[str, str] = {
    # GNS3 服务器配置 | GNS3 Server Configuration
    "GNS3_SERVER_HOST": "",  # GNS3 服务器主机
    "GNS3_SERVER_URL": "http://127.0.0.1:3080/",  # GNS3 服务器 URL
    "API_VERSION": "2",  # GNS3 API 版本
    "GNS3_SERVER_USERNAME": "",  # GNS3 服务器用户名
    "GNS3_SERVER_PASSWORD": "",  # GNS3 服务器密码
    # 模型配置 | Model Configuration
    "MODE_PROVIDER": "openai",  # 模型提供商
    "MODEL_NAME": "gpt-4",  # 模型名称
    "MODEL_API_KEY": "",  # 模型 API 密钥
    "BASE_URL": "",  # 模型 API 基础 URL
    "TEMPERATURE": "0.0",  # 模型温度参数
    # 语音配置 | Voice Configuration
    "VOICE": "False",  # 是否启用语音
    # 语音文字转语音(TTS)配置 | Voice TTS Configuration
    "TTS_API_KEY": "",  # TTS API 密钥
    "TTS_BASE_URL": "",  # TTS API 基础 URL
    "TTS_MODEL": "tts-1",  # TTS 模型名称
    "TTS_VOICE": "alloy",  # TTS 语音选择
    "TTS_SPEED": "1.0",  # TTS 语速
    # 语音语音转文字(STT)配置 | Voice STT Configuration
    "STT_API_KEY": "",  # STT API 密钥
    "STT_BASE_URL": "",  # STT API 基础 URL
    "STT_MODEL": "whisper-1",  # STT 模型名称
    "STT_LANGUAGE": "en",  # STT 语言
    "STT_TEMPERATURE": "0.0",  # STT 温度参数
    "STT_RESPONSE_FORMAT": "json",  # STT 响应格式
    # Linux Telnet 配置 | Linux Telnet Configuration
    "LINUX_TELNET_USERNAME": "",  # Linux Telnet 用户名
    "LINUX_TELNET_PASSWORD": "",  # Linux Telnet 密码
    # 提示词配置 | Prompt Configuration
    "ENGLISH_LEVEL": "Normal Prompt",  # 英文提示词级别
    # 阅读页面配置 | Reading Page Configuration
    "CALIBRE_SERVER_URL": "",  # Calibre 服务器 URL
    "READING_NOTES_DIR": "notes",  # 阅读笔记目录
    # UI 配置 | UI Configuration
    "CONTAINER_HEIGHT": "1200",  # 容器高度
    "ZOOM_SCALE_TOPOLOGY": "0.8",  # 拓扑缩放比例
    "TOPOLOGY_DRY_RUN": "True",  # 拓扑生成 dry-run 模式（不调用 GNS3 写操作）
    "FORTIGATE_CONFIG_STRATEGY": "hybrid_min_constraints",  # FortiGate dry-run 策略
    "FORTIGATE_NON_BASELINE_POST_VALIDATION": "False",  # 非 baseline 模式是否启用后校验
    # RAG 配置 | RAG Configuration
    "RAG_ENABLED": "False",  # RAG 功能总开关 | RAG feature toggle
    "RAG_CHROMA_PATH": "",  # ChromaDB 路径（空=data/chroma_db）| ChromaDB path (empty=data/chroma_db)
    "RAG_COLLECTION_NAME": "fortinet_docs",  # 集合名称 | Collection name
    "RAG_EMBEDDING_PROVIDER": "openai",  # 嵌入提供商 | Embedding provider
    "RAG_EMBEDDING_MODEL": "text-embedding-3-small",  # 嵌入模型 | Embedding model
    "RAG_EMBEDDING_API_KEY": "",  # 嵌入 API Key（空=复用 MODEL_API_KEY）| Embedding API key
    "RAG_EMBEDDING_BASE_URL": "",  # 嵌入 Base URL（空=复用 BASE_URL）| Embedding base URL
    "RAG_TOP_K": "5",  # 返回文档块数量 | Number of document chunks to return
    "RAG_CLI_CHUNK_SIZE": "800",  # CLI 文档块大小 | CLI doc chunk size
    "RAG_CLI_CHUNK_OVERLAP": "100",  # CLI 文档块重叠 | CLI doc chunk overlap
    "RAG_GUIDE_CHUNK_SIZE": "1500",  # 指南文档块大小 | Guide doc chunk size
    "RAG_GUIDE_CHUNK_OVERLAP": "200",  # 指南文档块重叠 | Guide doc chunk overlap
    # 其他设置 | Other Settings
    "LANGUAGE": "zh",  # 应用界面语言
    "TTS_HTTP_REFERER": "",  # TTS HTTP 参考来源
    "TTS_X_TITLE": "",  # TTS X-Title 标头
}


def _get_default(key: str) -> str | None:
    """获取配置键的默认值。
    
    Get the default value for a configuration key.

    Args/参数:
        key: 配置键 | Configuration key

    Returns/返回:
        如果键存在返回默认值，否则返回 None | Default value if key exists, None otherwise
    """
    # 从默认配置字典中获取值
    return DEFAULT_CONFIG.get(key)


def get_config(key: str, default: str | None = None) -> str:
    """从数据库中检索配置值。
    
    Retrieve a configuration value from the database.

    如果键不存在于数据库中，将使用来自DEFAULT_CONFIG的默认值。
    如果键也不在DEFAULT_CONFIG中，将使用提供的default参数。

    If the key doesn't exist in the database, it will use the default value
    from DEFAULT_CONFIG. If the key is not in DEFAULT_CONFIG either, it will
    use the provided default parameter.

    Args/参数:
        key: 要检索的配置键 | The configuration key to retrieve
        default: 如果键不在DEFAULT_CONFIG中的备用默认值 | Fallback default value if key not in DEFAULT_CONFIG

    Returns/返回:
        作为字符串的配置值 | The configuration value as a string

    Example/示例:
        >>> get_config("GNS3_SERVER_URL")
        'http://127.0.0.1:3080/'

        >>> get_config("CUSTOM_KEY", "default_value")
        'default_value'
    """
    # 从DEFAULT_CONFIG获取默认值或使用提供的默认值
    # Get default value from DEFAULT_CONFIG or use provided default
    default_value = default if default is not None else _get_default(key)

    # 从数据库中检索值
    # Retrieve value from database
    value = get_value(key, default_value)

    # 如果值为 None，返回默认值
    if value is None:
        logger.debug("Config key '%s' not found, using default: %s", key, default_value)
        return default_value if default_value is not None else ""

    # 确保返回值是字符串类型
    # Ensure value is a string
    return str(value) if value else default_value if default_value else ""


def set_config(key: str, value: str) -> bool:
    """将配置值保存到数据库。
    
    Save a configuration value to the database.

    Args/参数:
        key: 要保存的配置键 | The configuration key to save
        value: 要存储的配置值 | The configuration value to store

    Returns/返回:
        如果保存成功返回 True，否则返回 False | True if save was successful, False otherwise

    Example/示例:
        >>> set_config("GNS3_SERVER_URL", "http://192.168.1.100:3080")
        True
    """
    # 调用底层数据库函数保存值
    return set_value(key, value)


def get_all_config() -> dict[str, str]:
    """从数据库中检索所有配置值。
    
    Retrieve all configuration values from the database.

    Returns/返回:
        包含所有配置键值对的字典 | Dictionary with all configuration key-value pairs

    Example/示例:
        >>> config = get_all_config()
        >>> print(config["GNS3_SERVER_URL"])
        'http://127.0.0.1:3080/'
    """
    # 调用底层数据库函数获取所有值
    return get_all_values()


def init_config() -> None:
    """使用默认值初始化配置数据库。
    
    Initialize the configuration database with default values.

    此函数初始化数据库并使用所有配置键的默认值填充它。
    如果数据库中已存在某个键，其值不会被覆盖。
    
    This function initializes the database and populates it with default
    values for all configuration keys. If a key already exists in the
    database, its value will not be overwritten.

    应在应用程序启动时调用一次。
    This should be called once at application startup.

    Example/示例:
        >>> init_config()
        # 数据库现已初始化为默认值 | Database is now initialized with default values
    """
    try:
        # 初始化数据库并创建表
        # Initialize database and create tables
        init_db()

        # 为所有键设置默认值（仅在未设置时）
        # Set default values for all keys (only if not already set)
        for key, default_value in DEFAULT_CONFIG.items():
            # 检查键是否已存在
            existing_value = get_value(key)
            if existing_value is None:
                # 设置新的默认值
                set_value(key, default_value)
                logger.debug("Initialized default config: %s = %s", key, default_value)
            else:
                # 键已存在，跳过
                logger.debug("Config key '%s' already exists, skipping", key)

        logger.info(
            "Configuration database initialized with %d keys", len(DEFAULT_CONFIG)
        )
    except Exception as e:
        logger.error("Failed to initialize configuration: %s", e)
        raise


def reset_config() -> None:
    """将所有配置重置为默认值。
    
    Reset all configuration to default values.

    此函数清除所有现有配置值并将其恢复为DEFAULT_CONFIG中定义的默认值。

    This function clears all existing configuration values and
    restores them to defaults defined in DEFAULT_CONFIG.

    Example/示例:
        >>> reset_config()
        # 所有配置值现已设置为默认值 | All configuration values are now set to defaults
    """
    try:
        # 清除所有现有值
        # Clear all existing values
        clear_all()

        # 使用默认值重新初始化
        # Re-initialize with defaults
        init_config()

        logger.info("Configuration reset to defaults")
    except Exception as e:
        logger.error("Failed to reset configuration: %s", e)
        raise


def get_nornir_defaults() -> dict[str, Any]:
    """获取 Nornir 默认配置。
    
    Get Nornir default configuration.

    Returns/返回:
        包含 Nornir 默认配置的字典 | Dictionary containing Nornir defaults

    Example/示例:
        >>> defaults = get_nornir_defaults()
        >>> print(defaults)
        {'data': {'location': 'gns3'}}
    """
    # 返回 Nornir 默认配置，指定位置为 gns3
    return {"data": {"location": "gns3"}}


def get_nornir_all_groups_config() -> dict[str, dict[str, Any]]:
    """获取网络设备的所有 Nornir 组配置。
    
    Get all Nornir groups configuration for network devices.

    Returns/返回:
        包含所有 Nornir 组配置的字典 | Dictionary containing all Nornir group configurations

    Example/示例:
        >>> groups = get_nornir_all_groups_config()
        >>> print(groups['linux_telnet'])
        {'platform': 'linux', 'hostname': '127.0.0.1', ...}
    """
    # 返回包含两个网络设备组的配置：Cisco IOSv 和 Linux
    # Return configuration for two device groups: Cisco IOSv and Linux
    return {
        # Cisco IOSv Telnet 配置
        "cisco_IOSv_telnet": {
            "platform": "cisco_ios",
            "hostname": get_config("GNS3_SERVER_HOST"),
            "timeout": 120,
            "username": get_config("GNS3_SERVER_USERNAME"),
            "password": get_config("GNS3_SERVER_PASSWORD"),
            "connection_options": {
                "netmiko": {"extras": {"device_type": "cisco_ios_telnet"}}
            },
        },
        # Linux Telnet 配置
        "linux_telnet": {
            "platform": "linux",
            "hostname": get_config("GNS3_SERVER_HOST"),
            "timeout": 120,
            "username": get_config("LINUX_TELNET_USERNAME"),
            "password": get_config("LINUX_TELNET_PASSWORD"),
            "connection_options": {
                "netmiko": {
                    "platform": "linux",
                    "extras": {
                        "device_type": "generic_telnet",
                        "global_delay_factor": 3,
                        "timeout": 120,
                        "fast_cli": False,
                    },
                }
            },
        },
    }


def get_nornir_groups_config(group_name: str = "cisco_IOSv_telnet") -> dict[str, Any]:
    """获取网络设备的 Nornir 组配置。
    
    Get Nornir groups configuration for network devices.

    Args/参数:
        group_name: 组配置的名称 (默认: "cisco_IOSv_telnet") | Name of group configuration (default: "cisco_IOSv_telnet")

    Returns/返回:
        包含 Nornir 组配置的字典 | Dictionary containing Nornir group configuration

    Example/示例:
        >>> linux_config = get_nornir_groups_config("linux_telnet")
        >>> print(linux_config['platform'])
        'linux'
    """
    # 获取所有组配置
    all_groups = get_nornir_all_groups_config()
    # 根据组名获取对应的配置，如果不存在则返回空字典
    result = all_groups.get(group_name, {})
    return result
