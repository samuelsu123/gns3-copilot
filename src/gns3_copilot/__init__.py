"""
GNS3 Copilot - AI-powered network automation assistant for GNS3.
GNS3 Copilot - 用于 GNS3 的 AI 驱动网络自动化助手。

This package provides a command-line interface for launching the GNS3 Copilot
Streamlit application with support for Streamlit parameter passthrough.
此包提供命令行界面，用于启动 GNS3 Copilot Streamlit 应用程序，
支持 Streamlit 参数透传。
"""

# Dynamic version management
# 动态版本管理
__version__: str = "unknown"
try:
    from importlib.metadata import version

    __version__ = str(version("gns3-copilot"))
except Exception:
    __version__ = "unknown"

__author__ = "Guobin Yue"
__description__ = "AI-powered network automation assistant for GNS3"
__url__ = "https://github.com/yueguobin/gns3-copilot"
