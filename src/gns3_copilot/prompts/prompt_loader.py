"""
GNS3 网络自动化助手的动态提示词加载器

Dynamic prompt loader for GNS3 Network Automation Assistant

本模块提供基于英文水平等级动态加载系统提示词的功能。
它支持从环境变量加载不同的提示词，用于 A1、A2、B1、B2、C1 和 C2 英文等级。
此外，当启用 VOICE 模式时，它还可以附加语音优化的提示词。

This module provides functionality to dynamically load system prompts based on English proficiency levels.
It supports loading different prompts for A1, A2, B1, B2, C1, and C2 English levels from environment variables.
Additionally, it can append voice-optimized prompts when VOICE mode is enabled.
"""

import importlib
import os
from typing import cast

from gns3_copilot.log_config import setup_logger

logger = setup_logger("prompt_loader")

# 英文水平等级到对应提示词模块的映射
# Mapping of English levels to their corresponding prompt modules
ENGLISH_LEVEL_PROMPT_MAP = {
    "NORMAL PROMPT": "base_prompt",
    "A1": "english_level_prompt_a1",
    "A2": "english_level_prompt_a2",
    "B1": "english_level_prompt_b1",
    "B2": "english_level_prompt_b2",
    "C1": "english_level_prompt_c1",
    "C2": "english_level_prompt_c2",
}

# 英文水平等级到对应语音提示词模块的映射
# Mapping of English levels to their corresponding voice prompt modules
VOICE_LEVEL_PROMPT_MAP = {
    "A1": "voice_prompt_english_level_a1",
    "A2": "voice_prompt_english_level_a2",
    "B1": "voice_prompt_english_level_b1",
    "B2": "voice_prompt_english_level_b2",
    "C1": "voice_prompt_english_level_c1",
    "C2": "voice_prompt_english_level_c2",
}


def _load_base_prompt() -> str:
    """
    加载基础提示词系统提示。
    
    Load the base_prompt system prompt.

    Returns/返回:
        str: 基础提示词系统提示内容 | The base_prompt system prompt content.

    Raises/异常:
        ImportError: 如果导入 base_prompt 模块时出错 | If there's an error importing the base_prompt module.
        AttributeError: 如果在 base_prompt 模块中未找到 SYSTEM_PROMPT | If the SYSTEM_PROMPT is not found in the base_prompt module.
    """
    try:
        # 导入 base_prompt 模块
        # Import the base_prompt module
        base_prompt_module = importlib.import_module("gns3_copilot.prompts.base_prompt")

        # 从模块获取 SYSTEM_PROMPT
        # Get the SYSTEM_PROMPT from the module
        if hasattr(base_prompt_module, "SYSTEM_PROMPT"):
            system_prompt = cast(str, base_prompt_module.SYSTEM_PROMPT)
            logger.info("Successfully loaded base_prompt")
            return system_prompt
        else:
            raise AttributeError("SYSTEM_PROMPT not found in base_prompt module")

    except ImportError as e:
        logger.error("Failed to import base_prompt module: %s", e)
        raise ImportError(f"Failed to import base_prompt module: {e}") from e

    except AttributeError as e:
        logger.error("Error accessing SYSTEM_PROMPT in base_prompt module: %s", e)
        raise AttributeError(
            f"Error accessing SYSTEM_PROMPT in base_prompt module: {e}"
        ) from e


def _load_regular_level_prompt(level: str | None = None) -> str:
    """
    根据英文水平等级加载常规提示词。
    
    Load regular prompt based on English proficiency level.

    Args/参数:
        level (str, optional): 英文水平等级 (A1, A2, B1, B2, C1, C2)。
                              未提供时将使用基础提示词。
                              English proficiency level (A1, A2, B1, B2, C1, C2).
                              If not provided, will use base_prompt.

    Returns/返回:
        str: 指定英文水平的常规系统提示内容 | The regular system prompt content for the specified English level.
    """
    # 如果提供了等级，则转换为大写
    # Normalize level to uppercase if provided
    if level:
        level = level.upper().strip()

    # 如果未指定有效的英文水平，则使用基础提示词
    # If no valid English level is specified, use base_prompt
    if not level or level not in ENGLISH_LEVEL_PROMPT_MAP:
        logger.info(
            "No valid English level specified (got '%s'), using base_prompt", level
        )
        return _load_base_prompt()

    # 获取该等级对应的模块名称
    # Get the module name for the level
    module_name = ENGLISH_LEVEL_PROMPT_MAP[level]

    try:
        # 动态导入模块
        # Import the module dynamically
        prompt_module = importlib.import_module(f"gns3_copilot.prompts.{module_name}")

        # 从模块获取 SYSTEM_PROMPT
        # Get the SYSTEM_PROMPT from the module
        if hasattr(prompt_module, "SYSTEM_PROMPT"):
            base_prompt = cast(str, prompt_module.SYSTEM_PROMPT)
            logger.info(
                "Successfully loaded regular system prompt for English level: %s", level
            )
            return base_prompt
        else:
            raise AttributeError(f"SYSTEM_PROMPT not found in module {module_name}")

    except ImportError as e:
        logger.error("Failed to import regular prompt module '%s': %s", module_name, e)
        # 导入失败时回退到基础提示词
        # Fallback to base_prompt
        logger.info("Falling back to base_prompt due to import error")
        return _load_base_prompt()

    except AttributeError as e:
        logger.error(
            "Error accessing SYSTEM_PROMPT in regular prompt module '%s': %s",
            module_name,
            e,
        )
        # 属性不存在时回退到基础提示词
        # Fallback to base_prompt
        logger.info("Falling back to base_prompt due to attribute error")
        return _load_base_prompt()


def _load_voice_level_prompt(level: str | None = None) -> str:
    """
    根据英文水平等级加载语音提示词。
    
    Load voice prompt based on English proficiency level.

    Args/参数:
        level (str, optional): 英文水平等级 (A1, A2, B1, B2, C1, C2)。
                              未提供时将使用通用语音提示词。
                              English proficiency level (A1, A2, B1, B2, C1, C2).
                              If not provided, will use generic voice_prompt.

    Returns/返回:
        str: 指定英文水平的语音系统提示内容 | The voice system prompt content for the specified English level.
    """
    # 如果提供了等级，则转换为大写
    # Normalize level to uppercase if provided
    if level:
        level = level.upper().strip()

    # 首先尝试加载针对等级的语音提示词
    # Try to load level-specific voice prompt first
    if level and level in VOICE_LEVEL_PROMPT_MAP:
        module_name = VOICE_LEVEL_PROMPT_MAP[level]
        try:
            # 导入针对等级的语音提示词模块
            # Import the level-specific voice prompt module
            voice_prompt_module = importlib.import_module(
                f"gns3_copilot.prompts.{module_name}"
            )

            # 从模块获取 SYSTEM_PROMPT
            # Get the SYSTEM_PROMPT from the module
            if hasattr(voice_prompt_module, "SYSTEM_PROMPT"):
                voice_prompt = cast(str, voice_prompt_module.SYSTEM_PROMPT)
                logger.info(
                    "Successfully loaded voice prompt for English level: %s", level
                )
                return voice_prompt
            else:
                raise AttributeError(
                    f"SYSTEM_PROMPT not found in voice prompt module {module_name}"
                )

        except ImportError as e:
            logger.error(
                "Failed to import level-specific voice prompt module '%s': %s",
                module_name,
                e,
            )
            logger.info("Falling back to generic voice prompt")
        except AttributeError as e:
            logger.error(
                "Error accessing SYSTEM_PROMPT in level-specific voice prompt module '%s': %s",
                module_name,
                e,
            )
            logger.info("Falling back to generic voice prompt")

    # 回退到通用语音提示词
    # Fallback to generic voice prompt
    try:
        # 导入通用语音提示词模块
        # Import the generic voice prompt module
        voice_prompt_module = importlib.import_module(
            "gns3_copilot.prompts.voice_prompt"
        )

        # 从模块获取 SYSTEM_PROMPT
        # Get the SYSTEM_PROMPT from the module
        if hasattr(voice_prompt_module, "SYSTEM_PROMPT"):
            voice_prompt = cast(str, voice_prompt_module.SYSTEM_PROMPT)
            logger.info("Successfully loaded generic voice prompt")
            return voice_prompt
        else:
            raise AttributeError(
                "SYSTEM_PROMPT not found in generic voice prompt module"
            )

    except ImportError as e:
        logger.error("Failed to import generic voice prompt module: %s", e)
        # 最终回退到基础提示词
        # Return base_prompt as ultimate fallback
        logger.warning("Voice prompt not available, falling back to base_prompt")
        return _load_base_prompt()

    except AttributeError as e:
        logger.error(
            "Error accessing SYSTEM_PROMPT in generic voice prompt module: %s", e
        )
        # 最终回退到基础提示词
        # Return base_prompt as ultimate fallback
        logger.warning("Voice prompt not found, falling back to base_prompt")
        return _load_base_prompt()


def _is_voice_enabled() -> bool:
    """
    检查环境变量中是否启用了语音模式。
    
    Check if voice mode is enabled in environment variables.

    Returns/返回:
        bool: 如果启用语音模式返回 True，否则返回 False | True if voice mode is enabled, False otherwise.
    """
    # 从环境变量获取 VOICE 值，默认为 "False"，并转换为小写
    # Get VOICE environment variable value, default to "False", and convert to lowercase
    voice_value = os.getenv("VOICE", "False").lower().strip()
    # 检查值是否表示启用状态
    # Return True if value indicates enabled state
    return voice_value in ("true", "1", "yes", "on")


def load_system_prompt(level: str | None = None) -> str:
    """
    根据英文水平等级和语音模式设置加载系统提示词。
    
    Load system prompt based on English proficiency level and voice mode settings.

    本函数使用替换策略而非拼接策略：
    - 如果禁用语音模式：使用 ENGLISH_LEVEL_PROMPT_MAP
    - 如果启用语音模式：使用 VOICE_LEVEL_PROMPT_MAP
    
    This function uses a replacement strategy rather than concatenation:
    - If voice mode is disabled: uses ENGLISH_LEVEL_PROMPT_MAP
    - If voice mode is enabled: uses VOICE_LEVEL_PROMPT_MAP

    Args/参数:
        level (str, optional): 英文水平等级 (A1, A2, B1, B2, C1, C2)。
                              未提供时将从 ENGLISH_LEVEL 环境变量读取。
                              English proficiency level (A1, A2, B1, B2, C1, C2).
                              If not provided, will read from ENGLISH_LEVEL environment variable.

    Returns/返回:
        str: 指定英文水平和模式的系统提示内容 | The system prompt content for the specified English level and mode.

    Raises/异常:
        ImportError: 如果导入提示词模块时出错 | If there's an error importing the prompt module.
        AttributeError: 如果模块中未找到 SYSTEM_PROMPT | If the SYSTEM_PROMPT is not found in the module.
    """
    # 确定要使用的英文水平
    # Determine the English level to use
    if not level:
        level = os.getenv("ENGLISH_LEVEL", "")

    # 将等级转换为大写
    # Normalize level to uppercase
    level = level.upper().strip()

    # 检查是否启用语音模式，并选择相应的提示词集合
    # Check if voice mode is enabled and choose the appropriate prompt set
    if _is_voice_enabled():
        logger.info("Voice mode is enabled, using voice prompts")
        return _load_voice_level_prompt(level)
    else:
        logger.info("Voice mode is disabled, using regular prompts")
        return _load_regular_level_prompt(level)
