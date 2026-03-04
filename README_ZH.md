# GNS3 Copilot

[![CI - QA & Testing](https://github.com/yueguobin/gns3-copilot/actions/workflows/ci.yaml/badge.svg)](https://github.com/yueguobin/gns3-copilot/actions/workflows/ci.yaml)
[![CD - Production Release](https://github.com/yueguobin/gns3-copilot/actions/workflows/cd.yaml/badge.svg)](https://github.com/yueguobin/gns3-copilot/actions/workflows/cd.yaml)
[![codecov](https://codecov.io/gh/yueguobin/gns3-copilot/branch/Development/graph/badge.svg?token=7FDUCM547W)](https://codecov.io/gh/yueguobin/gns3-copilot)
[![PyPI version](https://img.shields.io/pypi/v/gns3-copilot)](https://pypi.org/project/gns3-copilot/)
[![PyPI downloads](https://img.shields.io/pypi/dm/gns3-copilot)](https://pypi.org/project/gns3-copilot/)
![License](https://img.shields.io/badge/license-MIT-green.svg) 
[![platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macOS-lightgrey)](https://shields.io/)


<div align="center">

[🇺🇸 English](README.md) | [🇨🇳 中文](README_ZH.md)

</div>


一个基于AI的网络自动化助手，专为GNS3网络模拟器设计，提供智能化的网络设备管理和自动化操作。

## 项目简介

GNS3 Copilot 是一个强大的网络自动化工具，集成了多种AI模型和网络自动化框架，能够通过自然语言与用户交互，执行网络设备配置、拓扑管理和故障诊断等任务。

<img src="https://raw.githubusercontent.com/yueguobin/gns3-copilot/refs/heads/Development/docs/media/demo.gif" alt="GNS3 Copilot Function demonstration" width="1280"/>

### 核心功能

- 🤖 **AI驱动的对话界面**: 支持自然语言交互，理解网络自动化需求
- 🔧 **设备配置管理**: 批量配置网络设备，支持多种厂商设备（目前仅测试了Cisco IOSv镜像）
- 📊 **拓扑管理**: 自动创建、修改和管理GNS3网络拓扑
- 🎨 **拓扑可视化**: SVG 绘图支持，自动生成网络拓扑图形，支持区域标注和连接线绘制
- 🔍 **网络诊断**: 智能网络故障排查和性能监控
- 🌐 **LLM支持**: 集成DeepSeek AI模型进行自然语言处理

## 安装指南

### 环境要求

- Python 3.10+
- GNS3 Server (运行在 http://localhost:3080或远程主机)
- 支持的操作系统: Windows, macOS, Linux

### 安装步骤

1. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

2. **安装 GNS3 Copilot**
```bash
pip install gns3-copilot
```

3. **启动 GNS3 Server**
确保 GNS3 Server 运行并可以通过网络访问其 API 接口：`http://x.x.x.x:3080`

4. **启动应用程序**
```bash
gns3-copilot
```

## 使用指南

### 配置参数详解

GNS3 Copilot 通过 Streamlit 界面进行配置管理，所有设置持久化保存在 SQLite 数据库中，提供可靠的数据存储。

#### 🔧 主要配置内容

##### 1. GNS3 服务器配置
- **GNS3 Server Host**: GNS3 服务器主机地址（如：127.0.0.1）
- **GNS3 Server URL**: GNS3 服务器完整 URL（如：http://127.0.0.1:3080）
- **API Version**: GNS3 API 版本（支持 v2 和 v3）
- **GNS3 Server Username**: GNS3 服务器用户名（仅 API v3 需要）
- **GNS3 Server Password**: GNS3 服务器密码（仅 API v3 需要）

##### 2. LLM 模型配置

**🌟 推荐模型：**
- **最佳选择：** `deepseek-chat`（通过 DeepSeek API）或 `deepseek/deepseek-v3.2`（通过 OpenRouter）
- **其他推荐：** `x-ai/grok-3`、`anthropic/claude-sonnet-4`、`z-ai/glm-4.7`

**注意：** 这些模型已经过测试验证，在网络自动化任务中表现优异。

- **Model Provider**: 模型提供商（支持：openai, anthropic, deepseek, xai, openrouter 等）
- **Model Name**: 具体模型名称（如：deepseek-chat, gpt-4o-mini 等）
- **Model API Key**: 模型 API 密钥
- **Base URL**: 模型服务的基础 URL（使用 OpenRouter 等第三方平台时必需）
- **Temperature**: 模型温度参数（控制输出随机性，范围 0.0-1.0）

##### 3. Calibre 与阅读设置
- **Calibre Server URL**: Calibre 内容服务器 URL（如：http://localhost:8080）
  - 通过 Calibre GUI 启动：首选项 → 网络共享 → 启动服务器
  - 或通过命令行启动：`calibre-server --port 8080`

##### 4. 其他设置
- **Linux Console Username**: Linux 控制台用户名（用于 GNS3 中的 Debian 设备）
- **Linux Console Password**: Linux 控制台密码

## 📚 阅读与笔记

GNS3 Copilot 集成了 Calibre 内容服务器，提供专门的阅读界面：

- **Calibre 电子书查看器**：嵌入式 iframe 查看器，可直接访问和阅读 Calibre 电子书库中的书籍
- **多笔记管理**：创建、选择和删除阅读笔记，方便整理您的想法
- **Markdown 笔记**：所有笔记均以 Markdown 格式保存，支持下载功能
- **🤖 AI 智能笔记整理**：使用 AI 自动润色和整理您的笔记
  - 点击 "AI Organize" 按钮，让 AI 自动格式化和结构化您的笔记
  - 侧边对比原始内容与整理后的内容，确认前可预览
  - 可反复重新整理，直到满意为止

访问阅读界面的步骤：
1. 在设置中配置 Calibre 服务器 URL
2. 启动 Calibre 内容服务器（默认端口 8080）
3. 在应用中导航到阅读页面

<img src="https://raw.githubusercontent.com/yueguobin/gns3-copilot/refs/heads/Development/docs/media/reading_and_notes.gif" alt="GNS3 Copilot Function demonstration" width="1280"/>

## Fortinet 文档 RAG（Demo）

当前版本支持基于 ChromaDB 的 Fortinet 文档检索（RAG）Demo。

快速流程：

1. 入库 FortiGate 文档：

```bash
python scripts/ingest_fortinet_docs.py \
  --pdf /path/to/FortiGate_7.6.6_Admin_Guide.pdf \
  --product fortigate \
  --version 7.6.6 \
  --doc-type admin-guide \
  --language en \
  --recreate
```

2. 在 `Settings -> Fortinet Docs RAG (ChromaDB)` 启用 RAG。
3. 在聊天中提问 FortiGate 配置问题，系统会先检索文档再回答。

详细说明见：[docs/user/fortinet-rag-guide_ZH.md](docs/user/fortinet-rag-guide_ZH.md)


## 文档

详细文档请参见 [docs/](docs/) 目录，包括用户指南、开发指南和技术文档。

## 🤝 参与贡献

我们非常欢迎来自社区的贡献！为了保障项目代码的稳定性，请遵循以下分支管理策略：

- 目标分支：请始终将您的 Pull Request (PR) 提交至 Development 分支（切勿直接提交至 master）。

- 功能分支：为每个新功能或修复创建独立分支：git checkout -b feature/您的功能名称 Development。

- 协作流程：Fork 仓库 -> 创建分支 -> 提交改动 -> 推送代码 -> 发起指向 Development 分支的 Pull Request。

## 实战经验

在开发和使用 gns3-copilot 的过程中，我们发现 AI 接入网络仿真不仅仅是技术对接，更是一种思维方式的转变。以下是我们在实验室总结出的几条"金律"：

1. **把它当成"陪练"，而不是"代练"**

    **不要**直接问："帮我把 OSPF 调通"。

    **尝试问**： "我的 OSPF 邻居卡在 Exstart 状态，帮我梳理一下可能的排查思路？"

    **理由**： AI 最大的价值在于它不厌其烦的** 7x24 引导能力**。通过让它提供"故障树"，你自己动手验证，学习效率会提高数倍。

2. **警惕"厂商私有协议"与"版本幻觉"**
   
    AI 是基于公开语料训练的。对于标准的 RFC 协议（OSPF, BGP）它非常强；但对于某些厂商的**私有协议**或**最新版本特性**，它可能会产生"幻觉"。

   ** 建议**： 凡是涉及到具体厂商的特殊命令，务必查阅官方文档进行二次确认。

3. **复杂拓扑的"记忆瓶颈"**

    当拓扑超过 20 个节点时，LLM 可能会出现"顾头不顾尾"的情况，给出前后矛盾的建议。

    **最佳实践**： 采用**模块化思维**。先让 Copilot 辅助你搞定一个区域（Area）或一个自治系统（AS），再进行全局联调。

4. **模拟器 vs. 真实世界**
   
    记住：GNS3 模拟不出光纤弯折、硬件坏道或真实的 CPU 瓶颈。

    AI 可能会给出逻辑上完美的建议，但在物理现实中可能行不通。**验证、抓包、再验证**，是唯一的准则。

## 安全注意事项

**API密钥保护**:
   - API 密钥存储在 SQLite 数据库中（当前为明文存储）
   - 定期轮换API密钥
   - 使用最小权限原则
   - 不要将数据库文件提交到版本控制

**数据库安全**:
   - **重要**: 数据库当前以明文形式存储密码和 API 密钥
   - 配置数据库存储在本地机器上
   - 确保数据库目录设置适当的文件权限
   - 定期备份数据库以防数据丢失
   - 限制对数据库文件的访问，仅允许授权用户

**环境安全**:
   - 在受信任的环境中运行 GNS3 Copilot
   - 考虑使用加密文件系统存储敏感数据
   - 共享数据库备份时需谨慎

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 致谢

本项目受到以下资源的启发，它们为 Python 编程、网络自动化和 AI 应用提供了重要的技术基础：

- **《网络工程师的 Python 之路》** - 网络工程师 Python 自动化技术
- **《网络工程师的 AI 之路》** - 网络工程师 AI 应用技术

特别感谢这些资源提供的技术启发和指导。

## 联系方式

- 项目主页: https://github.com/yueguobin/gns3-copilot
- 问题反馈: https://github.com/yueguobin/gns3-copilot/issues

---
