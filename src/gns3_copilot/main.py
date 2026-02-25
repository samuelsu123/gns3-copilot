#!/usr/bin/env python3
"""
GNS3 Copilot main entry point.
GNS3 Copilot 主入口点。

This module provides a command-line interface for launching the GNS3 Copilot
Streamlit application with support for Streamlit parameter passthrough.
此模块提供命令行界面，用于启动 GNS3 Copilot Streamlit 应用程序，
支持 Streamlit 参数透传。
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import types

# Conditional imports at top level
# 顶层条件导入
# Check if streamlit exists without actually importing it
# 检查 streamlit 是否存在而不实际导入它
STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None

if STREAMLIT_AVAILABLE:
    # If streamlit is needed later, it can be imported inside functions or keep current logic
    # 如果以后需要 streamlit，可以在函数内部导入或保持当前逻辑
    pass

# Global variables with proper typing
# 具有正确类型标注的全局变量
gns3_copilot: Optional["types.ModuleType"] = None
__version__: str = "unknown"
GNS3_COPILOT_AVAILABLE: bool = False

try:
    import gns3_copilot as gns3_copilot_import
    from gns3_copilot import __version__ as version_import

    gns3_copilot = gns3_copilot_import
    __version__ = version_import
    GNS3_COPILOT_AVAILABLE = True
except ImportError:
    pass


def get_app_path() -> str | None:
    """Get the path to the app.py file. 获取 app.py 文件的路径。"""
    # Try to find app.py in the current directory first
    # 首先尝试在当前目录中查找 app.py
    current_dir = Path.cwd()
    app_path = current_dir / "app.py"

    if app_path.exists():
        return str(app_path)

    # If not found, try to find it relative to this script
    # 如果未找到，尝试相对于此脚本查找
    script_dir = Path(__file__).parent.parent
    app_path = script_dir / "app.py"

    if app_path.exists():
        return str(app_path)

    # As a last resort, try to find it in the package installation
    # 作为最后的手段，尝试在包安装目录中查找
    if gns3_copilot is not None:
        try:
            module_file = gns3_copilot.__file__
            if module_file is not None:
                package_dir = Path(module_file).parent
                app_path = package_dir / "app.py"
                if app_path.exists():
                    return str(app_path)
        except (AttributeError, ImportError):
            pass

    return None


def check_streamlit() -> bool:
    """Check if streamlit is available. 检查 streamlit 是否可用。"""
    return STREAMLIT_AVAILABLE


def print_help() -> None:
    """Print help information. 打印帮助信息。"""
    help_text = """
GNS3 Copilot - AI-powered network automation assistant for GNS3

USAGE:
    gns3-copilot [STREAMLIT_OPTIONS]

EXAMPLES:
    # Basic startup
    gns3-copilot

    # Specify custom port
    gns3-copilot --server.port 8080

    # Specify address and port
    gns3-copilot --server.address 0.0.0.0 --server.port 8080

    # Run in headless mode
    gns3-copilot --server.headless true

    # Set log level
    gns3-copilot --logger.level debug

    # Disable usage statistics
    gns3-copilot --browser.gatherUsageStats false

COMMON STREAMLIT OPTIONS:
    --server.port PORT           Port to run on (default: 8501)
    --server.address ADDRESS     Address to bind to (default: localhost)
    --server.headless true/false Run in headless mode
    --logger.level LEVEL         Log level (error, warning, info, debug)
    --browser.gatherUsageStats true/false
                                Gather usage statistics
    --theme.base light/dark      Set base theme

For a complete list of Streamlit options, run:
    streamlit run --help

ALTERNATIVE USAGE:
    You can also run the app directly with streamlit:
    streamlit run app.py [STREAMLIT_OPTIONS]
"""
    print(help_text)


def print_version() -> None:
    """Print version information. 打印版本信息。"""
    if GNS3_COPILOT_AVAILABLE:
        print(f"GNS3 Copilot version {__version__}")
    else:
        print("GNS3 Copilot version unknown")


def main() -> int:
    """Main entry point. 主入口点。"""
    parser = argparse.ArgumentParser(
        prog="gns3-copilot",
        description="GNS3 Copilot - AI-powered network automation assistant for GNS3",
        add_help=False,  # We'll handle help ourselves to allow unknown args
                         # 我们自己处理帮助以允许未知参数
    )

    # Add our custom arguments
    # 添加我们的自定义参数
    parser.add_argument(
        "--help", "-h", action="store_true", help="Show this help message and exit"
    )
    parser.add_argument(
        "--version", "-v", action="store_true", help="Show version information and exit"
    )

    # Parse known args, leaving unknown args for streamlit
    # 解析已知参数，将未知参数留给 streamlit
    args, unknown_args = parser.parse_known_args()

    # Handle our custom arguments
    # 处理我们的自定义参数
    if args.help:
        print_help()
        return 0

    if args.version:
        print_version()
        return 0

    # Check if streamlit is available
    # 检查 streamlit 是否可用
    if not check_streamlit():
        print("Error: Streamlit is not installed. Please install it with:")
        print("  pip install streamlit")
        return 1

    # Find the app.py file
    # 查找 app.py 文件
    app_path = get_app_path()
    if not app_path:
        print("Error: Could not find app.py file.")
        print(
            "Please ensure you're running this from the project directory "
            "or that the package is properly installed."
        )
        return 1

    # Build the streamlit command
    # 构建 streamlit 命令
    cmd = ["streamlit", "run", app_path] + unknown_args

    # Print startup information
    # 打印启动信息
    print("Starting GNS3 Copilot...")
    print(f"App file: {app_path}")
    if unknown_args:
        print(f"Additional arguments: {' '.join(unknown_args)}")
    print()

    exit_code = 0
    try:
        # Run streamlit
        # 运行 streamlit
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
        exit_code = 1
    except KeyboardInterrupt:
        print("\nGNS3 Copilot stopped by user.")
        exit_code = 0
    except FileNotFoundError:
        print(
            "Error: 'streamlit' command not found. "
            "Please ensure Streamlit is installed and in your PATH."
        )
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
