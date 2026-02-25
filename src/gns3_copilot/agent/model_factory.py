"""
Model Factory for GNS3 Copilot Agent
GNS3 Copilot 代理的模型工厂

This module provides factory functions to create fresh LLM model instances
on-demand from SQLite configuration. This allows configuration changes
to take effect without restarting the application.
此模块提供工厂函数，用于根据 SQLite 配置按需创建新的 LLM 模型实例。
这允许配置更改在不重启应用程序的情况下生效。
"""

from typing import Any

from langchain.chat_models import init_chat_model

from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils import get_config

logger = setup_logger("model_factory")


def _load_env_variables() -> dict[str, str]:
    """
    Load model configuration from SQLite database.
    从 SQLite 数据库加载模型配置。

    Returns:
        Dictionary containing model configuration.
        包含模型配置的字典。
    """
    return {
        "model_name": get_config("MODEL_NAME", ""),
        "model_provider": get_config("MODE_PROVIDER", ""),
        "api_key": get_config("MODEL_API_KEY", ""),
        "base_url": get_config("BASE_URL", ""),
        "temperature": get_config("TEMPERATURE", "0"),
    }


def create_base_model() -> Any:
    """
    Create a fresh base LLM model instance from current environment variables.
    从当前环境变量创建新的基础 LLM 模型实例。

    This function reads environment variables fresh every time it's called,
    allowing configuration changes to take effect immediately.
    此函数每次调用时都会重新读取环境变量，
    允许配置更改立即生效。

    Returns:
        Any: A new LLM model instance configured with current env vars.
              The actual type depends on the provider (e.g., ChatOpenAI, etc.).
             使用当前环境变量配置的新 LLM 模型实例。
             实际类型取决于提供者（例如 ChatOpenAI 等）。

    Raises:
        ValueError: If required environment variables are missing or invalid.
                    如果缺少或无效的必需环境变量。
    """
    env_vars = _load_env_variables()

    # Log the loaded configuration (mask sensitive data)
    # 记录加载的配置（隐藏敏感数据）
    logger.info(
        "Creating base model: name=%s, provider=%s, base_url=%s, temperature=%s",
        env_vars["model_name"],
        env_vars["model_provider"],
        env_vars["base_url"] if env_vars["base_url"] else "default",
        env_vars["temperature"],
    )

    # Validate required fields
    # 验证必需字段
    if not env_vars["model_name"]:
        raise ValueError("MODEL_NAME environment variable is required")

    if not env_vars["model_provider"]:
        raise ValueError("MODE_PROVIDER environment variable is required")

    try:
        model = init_chat_model(
            env_vars["model_name"],
            model_provider=env_vars["model_provider"],
            api_key=env_vars["api_key"],
            base_url=env_vars["base_url"],
            temperature=env_vars["temperature"],
            configurable_fields="any",
            config_prefix="foo",
        )

        logger.info("Base model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create base model: %s", e)
        raise RuntimeError(f"Failed to create base model: {e}") from e


def create_title_model() -> Any:
    """
    Create a fresh title generation model instance.
    创建新的标题生成模型实例。

    This creates a model instance suitable for generating conversation titles.
    It uses the same configuration as the base model but with a higher temperature
    for more creative output.
    这会创建一个适合生成对话标题的模型实例。
    它使用与基础模型相同的配置，但使用更高的温度以获得更有创意的输出。

    Returns:
        Any: A new LLM model instance for title generation.
              The actual type depends on the provider.
             用于标题生成的新 LLM 模型实例。实际类型取决于提供者。

    Raises:
        ValueError: If required environment variables are missing or invalid.
                    如果缺少或无效的必需环境变量。
    """
    env_vars = _load_env_variables()

    logger.info(
        "Creating title model: name=%s, provider=%s, base_url=%s, temperature=1.0",
        env_vars["model_name"],
        env_vars["model_provider"],
        env_vars["base_url"] if env_vars["base_url"] else "default",
    )

    # Validate required fields
    # 验证必需字段
    if not env_vars["model_name"]:
        raise ValueError("MODEL_NAME environment variable is required")

    if not env_vars["model_provider"]:
        raise ValueError("MODE_PROVIDER environment variable is required")

    try:
        model = init_chat_model(
            env_vars["model_name"],
            model_provider=env_vars["model_provider"],
            api_key=env_vars["api_key"],
            base_url=env_vars["base_url"],
            temperature="1.0",  # Higher temperature for more creative titles
                                 # 更高的温度以获得更有创意的标题
            configurable_fields="any",
            config_prefix="foo",
        )

        logger.info("Title model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create title model: %s", e)
        raise RuntimeError(f"Failed to create title model: {e}") from e


def create_model_with_tools(
    model: Any,
    tools: list[Any],
) -> Any:
    """
    Bind tools to a model instance.
    将工具绑定到模型实例。

    Args:
        model: The base model instance. 基础模型实例。
        tools: List of tools to bind to the model. 要绑定到模型的工具列表。

    Returns:
        Any: A model instance with tools bound (type varies by provider).
             绑定了工具的模型实例（类型因提供者而异）。

    Raises:
        RuntimeError: If tool binding fails. 如果工具绑定失败。
    """
    try:
        model_with_tools = model.bind_tools(tools)
        logger.info("Model bound with %d tools successfully", len(tools))
        return model_with_tools
    except Exception as e:
        logger.error("Failed to bind tools to model: %s", e)
        raise RuntimeError(f"Failed to bind tools to model: {e}") from e


def create_note_organizer_model() -> Any:
    """
    Create a fresh model instance for note organization.
    创建新的笔记组织模型实例。

    This creates a model instance suitable for organizing and formatting notes.
    It uses the same configuration as the base model but with a lower temperature
    for more consistent and predictable output.
    这会创建一个适合组织和格式化笔记的模型实例。
    它使用与基础模型相同的配置，但使用更低的温度以获得更一致和可预测的输出。

    Returns:
        Any: A new LLM model instance for note organization.
              The actual type depends on the provider.
             用于笔记组织的新 LLM 模型实例。实际类型取决于提供者。

    Raises:
        ValueError: If required environment variables are missing or invalid.
                    如果缺少或无效的必需环境变量。
    """
    env_vars = _load_env_variables()

    logger.info(
        "Creating note organizer model: name=%s, provider=%s, base_url=%s, temperature=0.3",
        env_vars["model_name"],
        env_vars["model_provider"],
        env_vars["base_url"] if env_vars["base_url"] else "default",
    )

    # Validate required fields
    # 验证必需字段
    if not env_vars["model_name"]:
        raise ValueError("MODEL_NAME environment variable is required")

    if not env_vars["model_provider"]:
        raise ValueError("MODE_PROVIDER environment variable is required")

    try:
        model = init_chat_model(
            env_vars["model_name"],
            model_provider=env_vars["model_provider"],
            api_key=env_vars["api_key"],
            base_url=env_vars["base_url"],
            temperature="0.3",  # Lower temperature for more consistent note organization
                                 # 更低的温度以获得更一致的笔记组织
            configurable_fields="any",
            config_prefix="foo",
        )

        logger.info("Note organizer model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create note organizer model: %s", e)
        raise RuntimeError(f"Failed to create note organizer model: {e}") from e


def create_base_model_with_tools(tools: list[Any]) -> Any:
    """
    Create a fresh base model instance with tools bound.
    创建新的绑定了工具的基础模型实例。

    This is a convenience function that combines creating the base model
    and binding tools to it.
    这是一个便捷函数，结合了创建基础模型和将工具绑定到它。

    Args:
        tools: List of tools to bind to the model. 要绑定到模型的工具列表。

    Returns:
        Any: A new model instance with tools bound (type varies by provider).
             绑定了工具的新模型实例（类型因提供者而异）。

    Raises:
        ValueError: If required environment variables are missing.
                    如果缺少必需的环境变量。
        RuntimeError: If model creation or tool binding fails.
                      如果模型创建或工具绑定失败。
    """
    base_model = create_base_model()
    return create_model_with_tools(base_model, tools)
