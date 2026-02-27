"""
Model Factory for GNS3 Copilot Agent
GNS3 Copilot 代理的模型工厂

This module provides factory functions to create fresh LLM model instances
on-demand from SQLite configuration. This allows configuration changes
to take effect without restarting the application.
此模块提供工厂函数，用于根据 SQLite 配置按需创建新的 LLM 模型实例。
这允许配置更改在不重启应用程序的情况下生效。
"""

import json
import time
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

from gns3_copilot.agent.prompt_trace import append_http_trace_round
from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils import get_config

logger = setup_logger("model_factory")

_SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
}


def _redact_headers(headers: dict[str, Any]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        key_text = str(key)
        lower_key = key_text.lower()
        if lower_key in _SENSITIVE_HEADERS or "token" in lower_key:
            sanitized[key_text] = "***REDACTED***"
        else:
            sanitized[key_text] = str(value)
    return sanitized


def _decode_http_body(raw_body: bytes | None) -> Any:
    if not raw_body:
        return ""

    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return ""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _attach_http_trace_hooks(
    model: Any,
    trace_context: tuple[str, str] | None,
    model_tag: str,
) -> None:
    if not trace_context:
        return

    thread_id, request_id = trace_context
    if not thread_id or not request_id:
        return

    root_client = getattr(model, "root_client", None)
    http_client = getattr(root_client, "_client", None)
    if http_client is None:
        logger.warning("Skip HTTP trace hook: missing OpenAI http client")
        return

    event_hooks = getattr(http_client, "event_hooks", None)
    if not isinstance(event_hooks, dict):
        logger.warning("Skip HTTP trace hook: event_hooks is unavailable")
        return

    request_hooks = event_hooks.get("request")
    response_hooks = event_hooks.get("response")
    if not isinstance(request_hooks, list):
        request_hooks = list(request_hooks or [])
        event_hooks["request"] = request_hooks
    if not isinstance(response_hooks, list):
        response_hooks = list(response_hooks or [])
        event_hooks["response"] = response_hooks

    in_flight: dict[int, dict[str, Any]] = {}

    def _request_payload(request: Any) -> dict[str, Any]:
        body_bytes = getattr(request, "content", b"")
        return {
            "method": str(getattr(request, "method", "")),
            "url": str(getattr(request, "url", "")),
            "headers": _redact_headers(dict(getattr(request, "headers", {}))),
            "body": _decode_http_body(body_bytes),
        }

    def _response_payload(response: Any) -> dict[str, Any]:
        body_bytes = getattr(response, "content", b"")
        payload: dict[str, Any] = {
            "status_code": int(getattr(response, "status_code", 0)),
            "reason_phrase": str(getattr(response, "reason_phrase", "")),
            "headers": _redact_headers(dict(getattr(response, "headers", {}))),
            "body": _decode_http_body(body_bytes),
        }
        return payload

    def _on_request(request: Any) -> None:
        try:
            in_flight[id(request)] = {
                "started_at": time.perf_counter(),
                "request_payload": _request_payload(request),
            }
        except Exception as exc:
            logger.warning("HTTP trace request hook failed: %s", exc)

    def _on_response(response: Any) -> None:
        try:
            response.read()
        except Exception:
            pass

        try:
            request_obj = getattr(response, "request", None)
            request_key = id(request_obj) if request_obj is not None else -1
            entry = in_flight.pop(request_key, {})

            request_payload = entry.get("request_payload")
            if not isinstance(request_payload, dict) and request_obj is not None:
                request_payload = _request_payload(request_obj)
            if not isinstance(request_payload, dict):
                request_payload = {}

            response_payload = _response_payload(response)
            started_at = entry.get("started_at")
            if isinstance(started_at, float):
                response_payload["elapsed_ms"] = round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                )

            append_http_trace_round(
                thread_id=thread_id,
                request_id=request_id,
                model_tag=model_tag,
                request_payload=request_payload,
                response_payload=response_payload,
            )
        except Exception as exc:
            logger.warning("HTTP trace response hook failed: %s", exc)

    request_hooks.append(_on_request)
    response_hooks.append(_on_response)


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


def create_base_model(
    trace_context: tuple[str, str] | None = None,
    model_tag: str = "base_model",
) -> Runnable[LanguageModelInput, AIMessage]:
    """
    Create a fresh base LLM model instance from current environment variables.
    从当前环境变量创建新的基础 LLM 模型实例。

    This function reads environment variables fresh every time it's called,
    allowing configuration changes to take effect immediately.
    此函数每次调用时都会重新读取环境变量，
    允许配置更改立即生效。

    Returns:
        Runnable[LanguageModelInput, AIMessage]: A new chat model runnable
              configured with current env vars.
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
        provider = env_vars["model_provider"].strip().lower()
        model_kwargs: dict[str, Any] = {
            "model_provider": env_vars["model_provider"],
            "api_key": env_vars["api_key"],
            "base_url": env_vars["base_url"],
            "temperature": env_vars["temperature"],
            "configurable_fields": "any",
            "config_prefix": "foo",
        }

        model = init_chat_model(env_vars["model_name"], **model_kwargs)
        if provider == "openai":
            _attach_http_trace_hooks(
                model=model,
                trace_context=trace_context,
                model_tag=model_tag,
            )

        logger.info("Base model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create base model: %s", e)
        raise RuntimeError(f"Failed to create base model: {e}") from e


def create_title_model(
    trace_context: tuple[str, str] | None = None,
    model_tag: str = "title_model",
) -> Runnable[LanguageModelInput, AIMessage]:
    """
    Create a fresh title generation model instance.
    创建新的标题生成模型实例。

    This creates a model instance suitable for generating conversation titles.
    It uses the same configuration as the base model but with a higher temperature
    for more creative output.
    这会创建一个适合生成对话标题的模型实例。
    它使用与基础模型相同的配置，但使用更高的温度以获得更有创意的输出。

    Returns:
        Runnable[LanguageModelInput, AIMessage]: A new chat model runnable
              for title generation.
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
        provider = env_vars["model_provider"].strip().lower()
        model_kwargs: dict[str, Any] = {
            "model_provider": env_vars["model_provider"],
            "api_key": env_vars["api_key"],
            "base_url": env_vars["base_url"],
            "temperature": "1.0",  # Higher temperature for more creative titles
                                   # 更高的温度以获得更有创意的标题
            "configurable_fields": "any",
            "config_prefix": "foo",
        }

        model = init_chat_model(env_vars["model_name"], **model_kwargs)
        if provider == "openai":
            _attach_http_trace_hooks(
                model=model,
                trace_context=trace_context,
                model_tag=model_tag,
            )

        logger.info("Title model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create title model: %s", e)
        raise RuntimeError(f"Failed to create title model: {e}") from e


def create_model_with_tools(
    model: Any,
    tools: list[Any],
) -> Runnable[LanguageModelInput, AIMessage]:
    """
    Bind tools to a model instance.
    将工具绑定到模型实例。

    Args:
        model: The base model instance. 基础模型实例。
        tools: List of tools to bind to the model. 要绑定到模型的工具列表。

    Returns:
        Runnable[LanguageModelInput, AIMessage]: A model runnable with tools bound
             (exact runtime class varies by provider).
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


def create_note_organizer_model() -> Runnable[LanguageModelInput, AIMessage]:
    """
    Create a fresh model instance for note organization.
    创建新的笔记组织模型实例。

    This creates a model instance suitable for organizing and formatting notes.
    It uses the same configuration as the base model but with a lower temperature
    for more consistent and predictable output.
    这会创建一个适合组织和格式化笔记的模型实例。
    它使用与基础模型相同的配置，但使用更低的温度以获得更一致和可预测的输出。

    Returns:
        Runnable[LanguageModelInput, AIMessage]: A new chat model runnable
              for note organization.
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


def create_base_model_with_tools(
    tools: list[Any],
    trace_context: tuple[str, str] | None = None,
    model_tag: str = "base_model",
) -> Runnable[LanguageModelInput, AIMessage]:
    """
    Create a fresh base model instance with tools bound.
    创建新的绑定了工具的基础模型实例。

    This is a convenience function that combines creating the base model
    and binding tools to it.
    这是一个便捷函数，结合了创建基础模型和将工具绑定到它。

    Args:
        tools: List of tools to bind to the model. 要绑定到模型的工具列表。

    Returns:
        Runnable[LanguageModelInput, AIMessage]: A new model runnable with tools bound
             (exact runtime class varies by provider).
             绑定了工具的新模型实例（类型因提供者而异）。

    Raises:
        ValueError: If required environment variables are missing.
                    如果缺少必需的环境变量。
        RuntimeError: If model creation or tool binding fails.
                      如果模型创建或工具绑定失败。
    """
    base_model = create_base_model(trace_context=trace_context, model_tag=model_tag)
    return create_model_with_tools(base_model, tools)
