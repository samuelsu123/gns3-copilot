"""
GNS3 Copilot Streamlit application entry point.
GNS3 Copilot Streamlit 应用程序入口点。

Main application module that initializes and runs the Streamlit-based web interface
with navigation between settings, chat, and help pages.
主应用程序模块，初始化并运行基于 Streamlit 的 Web 界面，
支持在设置、聊天和帮助页面之间导航。
"""

import streamlit as st

from gns3_copilot.ui_model.sidebar import render_sidebar, render_sidebar_about
from gns3_copilot.ui_model.styles import get_styles
from gns3_copilot.ui_model.utils import (
    check_startup_updates,
    init_app_config,
    initialize_page_config,
    inject_chat_styles,
    load_config,
    render_startup_update_result,
)

NAV_PAGES = [
    "ui_model/reading.py",
    "ui_model/chat.py",
    "ui_model/settings.py",
    "ui_model/help.py",
]


def main() -> None:
    """Main application entry point. 主应用程序入口点。"""
    # Initialize page configuration early to ensure consistent layout
    # 尽早初始化页面配置以确保布局一致
    initialize_page_config()

    # Initialize configuration database with default values
    # 使用默认值初始化配置数据库
    init_app_config()

    # Load configuration from database into session state
    # This ensures all pages have access to the configuration
    # 从数据库加载配置到会话状态，确保所有页面都可以访问配置
    load_config()

    # Apply centralized CSS styles
    # 应用集中式 CSS 样式
    st.markdown(get_styles(), unsafe_allow_html=True)

    # Inject chat-specific styles
    # 注入聊天特定样式
    inject_chat_styles()

    # Check for updates on startup (blocking, runs once)
    # 启动时检查更新（阻塞式，只运行一次）
    check_startup_updates()

    # Prevent the app from crashing if a page path is missing
    # 防止应用程序在页面路径缺失时崩溃
    try:
        pg = st.navigation(NAV_PAGES, position="sidebar")

        # Render sidebar with current page information
        # 使用当前页面信息渲染侧边栏
        current_page = pg.script_path if hasattr(pg, "script_path") else ""
        selected_thread_id, title = render_sidebar(current_page=current_page)

        # Store selected thread ID and title in session state for chat page
        # 将选中的线程 ID 和标题存储到会话状态供聊天页面使用
        if selected_thread_id is not None:
            st.session_state["selected_thread_id"] = selected_thread_id
        if title is not None:
            st.session_state["session_title"] = title

        pg.run()
    except Exception as exc:
        st.error("Failed to initialize application navigation.")
        st.exception(exc)
        st.stop()

    # Display update result only on Settings page
    # 仅在设置页面显示更新结果
    if hasattr(pg, "script_path") and pg.script_path == "ui_model/settings.py":
        render_startup_update_result()

    # Render sidebar about section
    # 渲染侧边栏关于部分
    render_sidebar_about()


if __name__ == "__main__":
    main()
