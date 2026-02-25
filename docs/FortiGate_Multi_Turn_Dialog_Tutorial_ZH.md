# 多轮对话与 FortiGate 配置验证流程教程

> 基于 LangGraph 实现 AI Agent 与用户交互式配置 FortiGate 防火墙

---

## 目录

1. [概述](#1-概述)
2. [项目计划](#2-项目计划)
3. [FortiGate API 工具开发](#3-fortigate-api-工具开发)
4. [多轮对话流程设计](#4-多轮对话流程设计)
5. [用户交互确认机制](#5-用户交互确认机制)
6. [配置验证流程](#6-配置验证流程)
7. [完整代码示例](#7-完整代码示例)
8. [总结](#8-总结)

---

## 1. 概述

### 场景描述

在网络自动化场景中，配置 FortiGate 防火墙通常需要：

1. **获取当前配置** - 了解设备现状
2. **分析拓扑结构** - 理解设备在网络中的位置
3. **与用户交互** - 确认配置意图，避免误操作
4. **下发配置** - 执行实际配置变更
5. **验证配置** - 确认配置已生效

本教程将详细讲解如何使用 LangGraph 实现这一完整流程。

### 核心特点

- **多轮对话**：Agent 可以向用户提问、确认意图
- **拓扑感知**：结合 GNS3 拓扑信息做出智能决策
- **配置验证**：下发配置后自动验证是否生效
- **安全确认**：关键操作前必须获得用户确认

---

## 2. 项目计划

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户输入                                │
│        "配置 FortiGate 的防火墙策略，允许 PC1 访问 PC2"       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Agent                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  llm_call   │→ │  tool_node  │→ │  confirm    │          │
│  │  (AI决策)   │  │  (执行工具) │  │  (用户确认) │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FortiGate API 工具                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │ get_config   │ │ apply_config │ │verify_config │         │
│  │ (获取配置)   │ │ (下发配置)   │ │ (验证配置)   │         │
│  └──────────────┘ └──────────────┘ └──────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 开发计划详细步骤

#### 阶段一：FortiGate API 工具开发

| 步骤 | 任务 | 说明 |
|------|------|------|
| 1.1 | 创建 `FortiGateGetConfigTool` | 获取 FortiGate 当前配置（接口、路由、策略等） |
| 1.2 | 创建 `FortiGateApplyConfigTool` | 下发配置到 FortiGate |
| 1.3 | 创建 `FortiGateVerifyConfigTool` | 验证配置是否生效 |
| 1.4 | 工具注册与绑定 | 将工具注册到 Agent |

#### 阶段二：多轮对话流程设计

| 步骤 | 任务 | 说明 |
|------|------|------|
| 2.1 | 扩展状态定义 | 添加 `pending_config`、`user_confirmed` 等字段 |
| 2.2 | 设计对话流程 | 定义何时提问、何时确认、何时执行 |
| 2.3 | 实现条件路由 | 根据用户回复决定下一步 |

#### 阶段三：用户交互确认机制

| 步骤 | 任务 | 说明 |
|------|------|------|
| 3.1 | 设计确认提示 | 清晰展示待执行的配置变更 |
| 3.2 | 解析用户确认 | 识别"是"、"确认"、"取消"等意图 |
| 3.3 | 处理取消操作 | 用户拒绝时的优雅退出 |

#### 阶段四：配置验证流程

| 步骤 | 任务 | 说明 |
|------|------|------|
| 4.1 | 定义验证逻辑 | 配置下发后如何验证 |
| 4.2 | 实现重试机制 | 验证失败时的处理 |
| 4.3 | 生成验证报告 | 向用户展示验证结果 |

---

## 3. FortiGate API 工具开发

### 3.1 工具一：获取当前配置

```python
# tools/fortigate_get_config.py
import json
import requests
from langchain.tools import BaseTool

class FortiGateGetConfigTool(BaseTool):
    """获取 FortiGate 当前配置的工具"""
    
    name: str = "fortigate_get_config"
    description: str = """
    获取 FortiGate 防火墙的当前配置信息。
    
    输入格式（JSON）：
    {
        "host": "FortiGate管理IP地址",
        "config_type": "配置类型，可选值：interface/route/policy/all"
    }
    
    返回：当前配置的详细信息
    """
    
    def _run(self, tool_input: str) -> dict:
        """获取 FortiGate 配置"""
        
        data = json.loads(tool_input)
        host = data.get("host")
        config_type = data.get("config_type", "all")
        
        # FortiGate REST API 调用
        # 注意：实际使用时需要配置 API Token
        api_token = "your-api-token"
        headers = {"Authorization": f"Bearer {api_token}"}
        
        results = {}
        
        if config_type in ["interface", "all"]:
            # 获取接口配置
            resp = requests.get(
                f"https://{host}/api/v2/cmdb/system/interface",
                headers=headers,
                verify=False
            )
            results["interfaces"] = resp.json().get("results", [])
        
        if config_type in ["route", "all"]:
            # 获取路由配置
            resp = requests.get(
                f"https://{host}/api/v2/cmdb/router/static",
                headers=headers,
                verify=False
            )
            results["routes"] = resp.json().get("results", [])
        
        if config_type in ["policy", "all"]:
            # 获取防火墙策略
            resp = requests.get(
                f"https://{host}/api/v2/cmdb/firewall/policy",
                headers=headers,
                verify=False
            )
            results["policies"] = resp.json().get("results", [])
        
        return {
            "host": host,
            "config_type": config_type,
            "config": results,
            "status": "success"
        }
```

### 3.2 工具二：下发配置

```python
# tools/fortigate_apply_config.py
import json
import requests
from langchain.tools import BaseTool

class FortiGateApplyConfigTool(BaseTool):
    """下发配置到 FortiGate 的工具"""
    
    name: str = "fortigate_apply_config"
    description: str = """
    向 FortiGate 防火墙下发配置。
    
    输入格式（JSON）：
    {
        "host": "FortiGate管理IP地址",
        "config_type": "配置类型：interface/route/policy",
        "config_data": {
            // 具体配置内容，根据 config_type 不同而不同
        }
    }
    
    示例 - 创建防火墙策略：
    {
        "host": "192.168.1.1",
        "config_type": "policy",
        "config_data": {
            "name": "allow-pc1-to-pc2",
            "srcintf": [{"name": "port1"}],
            "dstintf": [{"name": "port2"}],
            "srcaddr": [{"name": "all"}],
            "dstaddr": [{"name": "all"}],
            "action": "accept",
            "status": "enable"
        }
    }
    
    返回：配置下发结果
    """
    
    def _run(self, tool_input: str) -> dict:
        """下发配置到 FortiGate"""
        
        data = json.loads(tool_input)
        host = data.get("host")
        config_type = data.get("config_type")
        config_data = data.get("config_data")
        
        api_token = "your-api-token"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        # 根据配置类型选择 API 端点
        endpoints = {
            "interface": "/api/v2/cmdb/system/interface",
            "route": "/api/v2/cmdb/router/static",
            "policy": "/api/v2/cmdb/firewall/policy"
        }
        
        endpoint = endpoints.get(config_type)
        if not endpoint:
            return {"error": f"不支持的配置类型: {config_type}"}
        
        # 发送配置
        resp = requests.post(
            f"https://{host}{endpoint}",
            headers=headers,
            json=config_data,
            verify=False
        )
        
        if resp.status_code in [200, 201]:
            return {
                "host": host,
                "config_type": config_type,
                "status": "success",
                "message": "配置下发成功"
            }
        else:
            return {
                "host": host,
                "config_type": config_type,
                "status": "failed",
                "error": resp.text
            }
```

### 3.3 工具三：验证配置

```python
# tools/fortigate_verify_config.py
import json
import requests
from langchain.tools import BaseTool

class FortiGateVerifyConfigTool(BaseTool):
    """验证 FortiGate 配置是否生效的工具"""
    
    name: str = "fortigate_verify_config"
    description: str = """
    验证 FortiGate 防火墙配置是否已生效。
    
    输入格式（JSON）：
    {
        "host": "FortiGate管理IP地址",
        "verify_type": "验证类型：policy/route/interface",
        "expected": {
            // 期望的配置状态
        }
    }
    
    示例 - 验证策略是否存在：
    {
        "host": "192.168.1.1",
        "verify_type": "policy",
        "expected": {
            "name": "allow-pc1-to-pc2",
            "action": "accept",
            "status": "enable"
        }
    }
    
    返回：验证结果（通过/失败）
    """
    
    def _run(self, tool_input: str) -> dict:
        """验证配置是否生效"""
        
        data = json.loads(tool_input)
        host = data.get("host")
        verify_type = data.get("verify_type")
        expected = data.get("expected")
        
        api_token = "your-api-token"
        headers = {"Authorization": f"Bearer {api_token}"}
        
        # 获取当前配置
        endpoints = {
            "interface": "/api/v2/cmdb/system/interface",
            "route": "/api/v2/cmdb/router/static",
            "policy": "/api/v2/cmdb/firewall/policy"
        }
        
        endpoint = endpoints.get(verify_type)
        resp = requests.get(
            f"https://{host}{endpoint}",
            headers=headers,
            verify=False
        )
        
        current_configs = resp.json().get("results", [])
        
        # 查找匹配的配置
        found = False
        matched_config = None
        
        for config in current_configs:
            if self._match_config(config, expected):
                found = True
                matched_config = config
                break
        
        if found:
            return {
                "host": host,
                "verify_type": verify_type,
                "status": "verified",
                "message": "配置验证通过，已生效",
                "matched_config": matched_config
            }
        else:
            return {
                "host": host,
                "verify_type": verify_type,
                "status": "not_found",
                "message": "配置验证失败，未找到匹配的配置",
                "expected": expected
            }
    
    def _match_config(self, actual: dict, expected: dict) -> bool:
        """检查实际配置是否匹配期望配置"""
        for key, value in expected.items():
            if key not in actual:
                return False
            if actual[key] != value:
                return False
        return True
```

---

## 4. 多轮对话流程设计

### 4.1 扩展状态定义

```python
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langchain.messages import AnyMessage
import operator

class FortiGateConfigState(TypedDict):
    """FortiGate 配置对话状态"""
    
    # 消息历史
    messages: Annotated[list[AnyMessage], operator.add]
    
    # LLM 调用次数
    llm_calls: int
    
    # 当前拓扑信息（从 GNS3 获取）
    topology_info: dict | None
    
    # 待执行的配置（等待用户确认）
    pending_config: dict | None
    
    # 用户是否已确认
    user_confirmed: bool
    
    # 配置执行状态
    config_status: Literal["pending", "confirmed", "applied", "verified", "cancelled"] | None
    
    # FortiGate 设备信息
    fortigate_info: dict | None
```

### 4.2 对话流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户输入                                  │
│          "配置 FortiGate 允许 PC1 访问 PC2"                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     llm_call 节点                                │
│  1. 分析用户意图                                                 │
│  2. 获取拓扑信息（已在上下文中）                                  │
│  3. 决定调用 fortigate_get_config 获取当前配置                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     tool_node 节点                               │
│  执行 fortigate_get_config                                       │
│  返回当前防火墙策略列表                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     llm_call 节点                                │
│  1. 分析当前配置                                                 │
│  2. 结合拓扑确定 PC1 和 PC2 的接口                               │
│  3. 生成配置方案                                                 │
│  4. 向用户提问确认                                               │
│     "我将创建以下策略：... 是否确认执行？"                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     等待用户确认                                  │
│  用户回复："是" / "确认" / "取消"                                │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│      用户确认执行        │     │      用户取消操作        │
│  调用 apply_config      │     │  返回取消消息            │
│  调用 verify_config     │     │  END                     │
└─────────────────────────┘     └─────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     验证并报告结果                                │
│  "配置已成功下发并验证生效：                                      │
│   - 策略名称：allow-pc1-to-pc2                                   │
│   - 源接口：port1                                                │
│   - 目标接口：port2                                              │
│   - 动作：允许"                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                            END
```

### 4.3 条件路由实现

```python
from langgraph.graph import END

def should_continue_fortigate(state: FortiGateConfigState) -> str:
    """决定下一步流程"""
    
    last_message = state["messages"][-1]
    config_status = state.get("config_status")
    
    # 如果 AI 请求调用工具
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_node"
    
    # 如果有待确认的配置且用户已确认
    if config_status == "confirmed":
        return "apply_config_node"
    
    # 如果配置已应用，进入验证
    if config_status == "applied":
        return "verify_config_node"
    
    # 如果用户取消
    if config_status == "cancelled":
        return END
    
    # 如果验证完成
    if config_status == "verified":
        return END
    
    # 默认结束
    return END
```

---

## 5. 用户交互确认机制

### 5.1 生成确认提示

```python
def generate_confirmation_prompt(pending_config: dict, topology_info: dict) -> str:
    """生成用户确认提示"""
    
    config_type = pending_config.get("config_type")
    config_data = pending_config.get("config_data")
    
    prompt = "📋 **配置确认**\n\n"
    prompt += "我将执行以下配置变更：\n\n"
    
    if config_type == "policy":
        prompt += f"**防火墙策略**\n"
        prompt += f"- 策略名称：{config_data.get('name')}\n"
        prompt += f"- 源接口：{config_data.get('srcintf')}\n"
        prompt += f"- 目标接口：{config_data.get('dstintf')}\n"
        prompt += f"- 动作：{config_data.get('action')}\n"
    
    prompt += "\n**拓扑上下文**\n"
    prompt += f"- FortiGate 连接的设备：{topology_info.get('connected_nodes', [])}\n"
    
    prompt += "\n⚠️ 请确认是否执行此配置？（回复 '是' 或 '取消'）"
    
    return prompt
```

### 5.2 解析用户确认意图

```python
def parse_user_confirmation(user_message: str) -> Literal["confirmed", "cancelled", "unclear"]:
    """解析用户的确认意图"""
    
    message_lower = user_message.lower().strip()
    
    # 确认关键词
    confirm_keywords = ["是", "yes", "确认", "确定", "执行", "同意", "ok", "好的", "可以"]
    
    # 取消关键词
    cancel_keywords = ["否", "no", "取消", "不", "算了", "停止", "cancel"]
    
    for keyword in confirm_keywords:
        if keyword in message_lower:
            return "confirmed"
    
    for keyword in cancel_keywords:
        if keyword in message_lower:
            return "cancelled"
    
    return "unclear"
```

### 5.3 处理不明确的回复

```python
def handle_unclear_response(state: FortiGateConfigState) -> dict:
    """处理用户不明确的回复"""
    
    clarification_message = """
    抱歉，我没有理解您的意图。请明确回复：
    
    - 回复 **"是"** 或 **"确认"** 执行配置
    - 回复 **"取消"** 放弃此次配置
    """
    
    return {
        "messages": [AIMessage(content=clarification_message)],
        "config_status": "pending"
    }
```

---

## 6. 配置验证流程

### 6.1 验证节点实现

```python
def verify_config_node(state: FortiGateConfigState) -> dict:
    """验证配置是否生效"""
    
    pending_config = state.get("pending_config")
    fortigate_info = state.get("fortigate_info")
    
    # 构建验证参数
    verify_input = json.dumps({
        "host": fortigate_info.get("host"),
        "verify_type": pending_config.get("config_type"),
        "expected": pending_config.get("config_data")
    })
    
    # 调用验证工具
    verify_tool = FortiGateVerifyConfigTool()
    result = verify_tool._run(verify_input)
    
    if result.get("status") == "verified":
        message = f"""
        ✅ **配置验证成功**
        
        配置已生效：
        - 类型：{pending_config.get('config_type')}
        - 名称：{pending_config.get('config_data', {}).get('name')}
        - 状态：已启用
        
        您现在可以测试 PC1 到 PC2 的连通性。
        """
        return {
            "messages": [AIMessage(content=message)],
            "config_status": "verified"
        }
    else:
        message = f"""
        ❌ **配置验证失败**
        
        未能确认配置生效，可能原因：
        - 配置下发延迟
        - 配置参数错误
        
        建议：请手动检查 FortiGate 配置。
        """
        return {
            "messages": [AIMessage(content=message)],
            "config_status": "verify_failed"
        }
```

### 6.2 完整验证流程

```
配置下发成功
      │
      ▼
┌─────────────────┐
│  等待 2 秒      │  ← 给设备时间应用配置
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  调用验证工具   │
└─────────────────┘
      │
      ├─── 验证通过 ──→ 报告成功，END
      │
      └─── 验证失败 ──→ 重试（最多3次）
                              │
                              ├─── 重试成功 ──→ 报告成功，END
                              │
                              └─── 重试失败 ──→ 报告失败，建议手动检查
```

---

## 7. 完整代码示例

### 7.1 工具注册

```python
# agent/fortigate_agent.py
from langchain.tools import BaseTool
from langgraph.graph import StateGraph, START, END

# 导入工具
from tools.fortigate_get_config import FortiGateGetConfigTool
from tools.fortigate_apply_config import FortiGateApplyConfigTool
from tools.fortigate_verify_config import FortiGateVerifyConfigTool

# 定义所有工具
fortigate_tools = [
    FortiGateGetConfigTool(),
    FortiGateApplyConfigTool(),
    FortiGateVerifyConfigTool(),
]

# 工具名称映射
tools_by_name = {tool.name: tool for tool in fortigate_tools}
```

### 7.2 构建 Agent 图

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

# 创建模型并绑定工具
model = ChatOpenAI(model="deepseek-chat")
model_with_tools = model.bind_tools(fortigate_tools)

# 定义节点
def llm_call(state: FortiGateConfigState) -> dict:
    """AI 决策节点"""
    
    # 构建系统提示
    system_prompt = """
    你是一个 FortiGate 防火墙配置助手。
    
    工作流程：
    1. 首先获取当前配置，了解设备状态
    2. 分析用户需求，结合拓扑信息
    3. 生成配置方案，向用户确认
    4. 用户确认后执行配置
    5. 验证配置是否生效
    
    重要：在执行任何配置变更前，必须向用户确认！
    """
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = model_with_tools.invoke(messages)
    
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

def tool_node(state: FortiGateConfigState) -> dict:
    """工具执行节点"""
    
    results = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        result = tool.invoke(tool_call["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    
    return {"messages": results}

def user_confirmation_node(state: FortiGateConfigState) -> dict:
    """处理用户确认"""
    
    last_user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    if last_user_message:
        confirmation = parse_user_confirmation(last_user_message)
        return {"config_status": confirmation}
    
    return {"config_status": "pending"}

# 构建图
graph = StateGraph(FortiGateConfigState)

# 添加节点
graph.add_node("llm_call", llm_call)
graph.add_node("tool_node", tool_node)
graph.add_node("user_confirmation", user_confirmation_node)
graph.add_node("verify_config", verify_config_node)

# 添加边
graph.add_edge(START, "llm_call")
graph.add_conditional_edges(
    "llm_call",
    should_continue_fortigate,
    {
        "tool_node": "tool_node",
        "apply_config_node": "tool_node",
        "verify_config_node": "verify_config",
        END: END
    }
)
graph.add_edge("tool_node", "llm_call")
graph.add_edge("verify_config", END)

# 编译
agent = graph.compile()
```

### 7.3 运行示例

```python
# 运行 Agent
from langchain.messages import HumanMessage

# 初始状态
initial_state = {
    "messages": [HumanMessage(content="配置 FortiGate 允许 PC1 访问 PC2")],
    "llm_calls": 0,
    "topology_info": {
        "nodes": [
            {"name": "PC1", "connected_to": "FortiGate-port1"},
            {"name": "PC2", "connected_to": "FortiGate-port2"},
            {"name": "FortiGate", "ports": ["port1", "port2"]}
        ]
    },
    "fortigate_info": {
        "host": "192.168.1.1"
    },
    "pending_config": None,
    "user_confirmed": False,
    "config_status": None
}

# 运行
result = agent.invoke(initial_state)

# 输出对话
for msg in result["messages"]:
    print(f"{msg.type}: {msg.content}")
```

---

## 8. 总结

### 核心要点

1. **工具开发**：创建获取配置、下发配置、验证配置三个工具
2. **状态扩展**：添加 `pending_config`、`user_confirmed`、`config_status` 等字段
3. **多轮对话**：Agent 可以向用户提问、等待确认
4. **安全机制**：关键操作前必须获得用户确认
5. **验证闭环**：配置下发后自动验证是否生效

### 最佳实践

- ✅ 始终在配置变更前获取当前状态
- ✅ 结合拓扑信息做出智能决策
- ✅ 关键操作前向用户确认
- ✅ 配置后验证是否生效
- ✅ 提供清晰的操作反馈

### 进阶方向

- 添加配置回滚功能
- 支持批量配置多台 FortiGate
- 集成配置审计日志
- 实现配置模板管理

---

## 9. 使用 Streamlit 开发交互页面

### 9.1 为什么使用 Streamlit？

Streamlit 是一个快速构建数据应用和 AI 应用的 Python 框架，特别适合：

- **快速原型开发**：几行代码即可创建交互界面
- **聊天界面支持**：内置 `st.chat_input` 和 `st.chat_message` 组件
- **状态管理**：`st.session_state` 轻松管理对话历史
- **实时更新**：用户输入后界面自动刷新

### 9.2 基础聊天界面

```python
import streamlit as st
from langchain.messages import HumanMessage, AIMessage

# 页面配置
st.set_page_config(
    page_title="FortiGate 配置助手",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 FortiGate 配置助手")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    # 初始化 Agent（使用前面定义的 agent）
    st.session_state.agent = agent

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 用户输入
if prompt := st.chat_input("请输入您的配置需求..."):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 调用 Agent
    with st.chat_message("assistant"):
        with st.spinner("正在处理..."):
            result = st.session_state.agent.invoke({
                "messages": [HumanMessage(content=prompt)],
                "llm_calls": 0,
                "topology_info": st.session_state.get("topology_info"),
                "fortigate_info": st.session_state.get("fortigate_info"),
                "pending_config": None,
                "user_confirmed": False,
                "config_status": None
            })
            
            # 获取 AI 回复
            response = result["messages"][-1].content
            st.markdown(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
```

### 9.3 添加配置确认对话框

```python
import streamlit as st

def show_config_confirmation(pending_config: dict):
    """显示配置确认对话框"""
    
    st.warning("⚠️ 即将执行以下配置变更：")
    
    # 显示配置详情
    with st.expander("📋 配置详情", expanded=True):
        st.json(pending_config)
    
    # 确认按钮
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ 确认执行", type="primary", use_container_width=True):
            st.session_state.user_confirmed = True
            st.rerun()
    
    with col2:
        if st.button("❌ 取消", type="secondary", use_container_width=True):
            st.session_state.user_confirmed = False
            st.session_state.pending_config = None
            st.info("已取消配置操作")
            st.rerun()
```

### 9.4 完整的 Streamlit 应用

```python
# fortigate_streamlit_app.py

import streamlit as st
from langchain.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END

# ============ 页面配置 ============
st.set_page_config(
    page_title="FortiGate 配置助手",
    page_icon="🔥",
    layout="wide"
)

# ============ 侧边栏配置 ============
with st.sidebar:
    st.header("⚙️ FortiGate 连接配置")
    
    fortigate_host = st.text_input(
        "FortiGate IP 地址",
        value="192.168.1.1",
        help="FortiGate 防火墙的管理 IP 地址"
    )
    
    auth_method = st.radio(
        "认证方式",
        ["API Token", "用户名/密码"],
        help="选择 FortiGate API 认证方式"
    )
    
    if auth_method == "API Token":
        api_token = st.text_input(
            "API Token",
            type="password",
            help="在 FortiGate 上创建的 REST API Token"
        )
    else:
        username = st.text_input("用户名", value="admin")
        password = st.text_input("密码", type="password")
    
    st.divider()
    
    # 连接测试按钮
    if st.button("🔗 测试连接", use_container_width=True):
        with st.spinner("正在连接..."):
            # 这里调用实际的连接测试逻辑
            # connected = test_fortigate_connection(fortigate_host, api_token)
            connected = True  # 示例
            
            if connected:
                st.success("✅ 连接成功！")
                st.session_state.fortigate_connected = True
            else:
                st.error("❌ 连接失败，请检查配置")

# ============ 主界面 ============
st.title("🔥 FortiGate 配置助手")
st.caption("基于 AI 的 FortiGate 防火墙配置管理工具")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_config" not in st.session_state:
    st.session_state.pending_config = None

if "user_confirmed" not in st.session_state:
    st.session_state.user_confirmed = None

# ============ 显示历史消息 ============
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # 如果是工具调用结果，显示详情
        if message.get("tool_results"):
            with st.expander("🔧 工具执行详情"):
                st.json(message["tool_results"])

# ============ 配置确认对话框 ============
if st.session_state.pending_config and st.session_state.user_confirmed is None:
    st.warning("⚠️ 即将执行以下配置变更，请确认：")
    
    with st.expander("📋 配置详情", expanded=True):
        st.json(st.session_state.pending_config)
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("✅ 确认执行", type="primary", use_container_width=True):
            st.session_state.user_confirmed = True
            st.rerun()
    
    with col2:
        if st.button("❌ 取消", type="secondary", use_container_width=True):
            st.session_state.user_confirmed = False
            st.session_state.pending_config = None
            st.session_state.messages.append({
                "role": "assistant",
                "content": "已取消配置操作。如需其他帮助，请继续提问。"
            })
            st.rerun()

# ============ 用户输入处理 ============
if prompt := st.chat_input("请输入您的配置需求，例如：配置防火墙策略允许 PC1 访问 PC2"):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 调用 Agent
    with st.chat_message("assistant"):
        with st.spinner("🤔 正在分析您的需求..."):
            try:
                # 构建 Agent 输入状态
                agent_input = {
                    "messages": [HumanMessage(content=prompt)],
                    "llm_calls": 0,
                    "fortigate_info": {
                        "host": fortigate_host,
                        "api_token": api_token if auth_method == "API Token" else None,
                        "username": username if auth_method != "API Token" else None,
                        "password": password if auth_method != "API Token" else None,
                    },
                    "pending_config": st.session_state.pending_config,
                    "user_confirmed": st.session_state.user_confirmed,
                    "config_status": None
                }
                
                # 调用 Agent（使用前面定义的 agent）
                result = agent.invoke(agent_input)
                
                # 获取 AI 回复
                response = result["messages"][-1].content
                st.markdown(response)
                
                # 检查是否有待确认的配置
                if result.get("pending_config"):
                    st.session_state.pending_config = result["pending_config"]
                    st.session_state.user_confirmed = None
                
                # 保存消息
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
                
            except Exception as e:
                st.error(f"处理请求时出错：{str(e)}")

# ============ 页脚 ============
st.divider()
st.caption("💡 提示：您可以询问当前配置、创建防火墙策略、配置路由等操作。")
```

### 9.5 运行 Streamlit 应用

```bash
# 安装依赖
pip install streamlit

# 运行应用
streamlit run fortigate_streamlit_app.py
```

### 9.6 界面效果说明

运行后，您将看到：

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚙️ FortiGate 连接配置    │    🔥 FortiGate 配置助手            │
│  ─────────────────────    │    ─────────────────────────────    │
│  FortiGate IP: [192.168.1.1]  │                                 │
│  认证方式: ○ API Token    │    👤 用户: 配置防火墙策略允许      │
│           ● 用户名/密码   │           PC1 访问 PC2              │
│  用户名: [admin]          │                                     │
│  密码: [********]         │    🤖 助手: 我已获取当前配置，      │
│                           │           检测到以下信息：          │
│  [🔗 测试连接]            │           - PC1 连接到 port1        │
│                           │           - PC2 连接到 port2        │
│                           │                                     │
│                           │    ⚠️ 即将执行以下配置变更：        │
│                           │    ┌─────────────────────────┐      │
│                           │    │ 📋 配置详情             │      │
│                           │    │ {                       │      │
│                           │    │   "action": "accept",   │      │
│                           │    │   "srcintf": "port1",   │      │
│                           │    │   "dstintf": "port2"    │      │
│                           │    │ }                       │      │
│                           │    └─────────────────────────┘      │
│                           │    [✅ 确认执行] [❌ 取消]           │
│                           │                                     │
│                           │    ─────────────────────────────    │
│                           │    [请输入您的配置需求...]          │
└─────────────────────────────────────────────────────────────────┘
```

### 9.7 关键 Streamlit 组件说明

| 组件 | 用途 | 示例 |
|------|------|------|
| `st.chat_input()` | 聊天输入框 | 用户输入配置需求 |
| `st.chat_message()` | 聊天气泡 | 显示用户和 AI 的对话 |
| `st.session_state` | 会话状态 | 保存对话历史、配置状态 |
| `st.sidebar` | 侧边栏 | 放置连接配置 |
| `st.expander()` | 可折叠区域 | 显示配置详情 |
| `st.button()` | 按钮 | 确认/取消操作 |
| `st.spinner()` | 加载动画 | 等待 AI 响应时显示 |

### 9.8 与 GNS3 Copilot 集成

如果要将 FortiGate 配置功能集成到现有的 GNS3 Copilot 项目中，可以参考 `src/gns3_copilot/agent/gns3_copilot.py` 的实现方式：

```python
# 在现有的 tools 列表中添加 FortiGate 工具
tools = [
    GNS3TemplateTool(),
    GNS3TopologyTool(),
    GNS3CreateNodeTool(),
    # ... 其他 GNS3 工具
    
    # 添加 FortiGate 工具
    FortiGateGetConfigTool(),
    FortiGateApplyConfigTool(),
    FortiGateVerifyConfigTool(),
]

# 工具会自动绑定到 LLM，Agent 可以根据用户需求调用
```

---

> 💡 **提示**：本教程的代码示例需要根据实际的 FortiGate API 版本和认证方式进行调整。建议先在测试环境中验证。
