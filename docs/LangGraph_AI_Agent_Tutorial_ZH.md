# LangGraph + Python 开发 AI Agent 教程

> 以 GNS3 Copilot 项目为例，手把手教你从零开始开发一个 AI Agent 应用

---

## 目录

1. [什么是 AI Agent？](#1-什么是-ai-agent)
2. [什么是 LangGraph？](#2-什么是-langgraph)
3. [核心概念解析](#3-核心概念解析)
4. [实战案例：生成网络拓扑](#4-实战案例生成网络拓扑)
5. [完整代码示例](#5-完整代码示例)
6. [运行流程详解](#6-运行流程详解)
7. [总结与进阶](#7-总结与进阶)

---

## 1. 什么是 AI Agent？

### 简单理解

想象你有一个**超级智能助手**：
- 你告诉它："帮我生成2个PC和1个FortiGate的网络拓扑"
- 它会**自己思考**需要做什么
- **自己调用工具**（比如创建节点、创建连接）
- **自己判断**下一步该做什么
- 最后给你一个完整的结果

这就是 AI Agent！它不是简单的问答，而是能**自主决策和执行任务**的智能体。

### Agent vs 普通聊天机器人

| 普通聊天机器人 | AI Agent |
|--------------|----------|
| 只能回答问题 | 能执行实际操作 |
| 一问一答 | 多步骤自主完成任务 |
| 不能调用外部工具 | 可以调用各种工具 |

---

## 2. 什么是 LangGraph？

### 简单理解

LangGraph 是一个帮你**搭建 AI Agent 的框架**。

把它想象成**乐高积木**：
- **节点（Node）**：每块积木，代表一个功能（比如"调用AI"、"执行工具"）
- **边（Edge）**：积木之间的连接，决定执行顺序
- **状态（State）**：一个"记事本"，记录整个过程中的信息

### 为什么用 LangGraph？

```
用户输入 → AI思考 → 需要工具？→ 是 → 执行工具 → AI再思考 → ... → 输出结果
              ↑                                    ↓
              └────────────────────────────────────┘
```

这种**循环决策**的流程，用 LangGraph 很容易实现！

---

## 3. 核心概念解析

### 3.1 状态（State）—— 记事本

状态就像一个**共享的记事本**，所有节点都可以读写它。

```python
from typing import Annotated
from typing_extensions import TypedDict
from langchain.messages import AnyMessage
import operator

class MessagesState(TypedDict):
    """对话状态 - 记录所有信息"""
    
    # 消息列表：记录所有对话历史
    # operator.add 表示新消息会追加到列表末尾
    messages: Annotated[list[AnyMessage], operator.add]
    
    # 可以添加其他需要记录的信息
    llm_calls: int  # 记录调用了多少次AI
```

**通俗解释**：
- `messages`：就像聊天记录，保存用户说的话、AI的回复、工具的结果
- `Annotated[..., operator.add]`：表示每次更新都是"追加"，不是"覆盖"

### 3.2 节点（Node）—— 功能模块

节点是**执行具体任务的函数**。

```python
def llm_call(state: dict):
    """节点1：调用AI大模型"""
    
    # 1. 从状态中获取消息历史
    messages = state["messages"]
    
    # 2. 调用AI模型
    response = model.invoke(messages)
    
    # 3. 返回更新（会自动合并到状态中）
    return {"messages": [response]}


def tool_node(state: dict):
    """节点2：执行工具"""
    
    # 1. 获取AI要求执行的工具
    tool_calls = state["messages"][-1].tool_calls
    
    # 2. 执行每个工具
    results = []
    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]
        result = tool.invoke(tool_call["args"])
        results.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
    
    # 3. 返回工具执行结果
    return {"messages": results}
```

### 3.3 边（Edge）—— 流程控制

边决定了**节点之间的执行顺序**。

```python
from langgraph.graph import StateGraph, START, END

# 创建图
graph = StateGraph(MessagesState)

# 添加节点
graph.add_node("llm_call", llm_call)
graph.add_node("tool_node", tool_node)

# 添加边：START → llm_call（程序开始时先调用AI）
graph.add_edge(START, "llm_call")

# 添加条件边：根据情况决定下一步
graph.add_conditional_edges(
    "llm_call",           # 从哪个节点出发
    should_continue,       # 判断函数
    {
        "tool_node": "tool_node",  # 如果需要工具 → 去执行工具
        END: END,                   # 如果不需要 → 结束
    }
)

# 工具执行完后，回到AI继续思考
graph.add_edge("tool_node", "llm_call")
```

### 3.4 条件路由 —— 智能决策

```python
def should_continue(state: dict):
    """决定下一步去哪里"""
    
    last_message = state["messages"][-1]
    
    # 如果AI要求调用工具
    if last_message.tool_calls:
        return "tool_node"  # 去执行工具
    
    # 否则任务完成
    return END
```

---

## 4. 实战案例：生成网络拓扑

### 用户需求
> "生成2个PC + 1个FortiGate网络拓扑"

### 执行流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户输入                                  │
│            "生成2个PC + 1个FortiGate网络拓扑"                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点1: llm_call                              │
│  AI分析：需要先获取可用的设备模板                                 │
│  决定调用：get_gns3_templates 工具                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点2: tool_node                             │
│  执行 get_gns3_templates                                         │
│  返回：[{name: "VPCS", id: "xxx"}, {name: "FortiGate", id:"yyy"}]│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点1: llm_call                              │
│  AI分析：有了模板，现在创建节点                                   │
│  决定调用：create_gns3_node 工具（创建2个PC + 1个FortiGate）      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点2: tool_node                             │
│  执行 create_gns3_node                                           │
│  返回：成功创建3个节点                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点1: llm_call                              │
│  AI分析：节点创建完成，需要创建连接                               │
│  决定调用：create_gns3_link 工具                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点2: tool_node                             │
│  执行 create_gns3_link                                           │
│  返回：成功创建连接                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     节点1: llm_call                              │
│  AI分析：任务完成！                                               │
│  生成最终回复给用户                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                            END
```

---

## 5. 完整代码示例

### 5.1 定义工具（Tool）

工具是 Agent 的"手"，让它能执行实际操作。

```python
# tools/create_node.py
import json
from langchain.tools import BaseTool

class GNS3CreateNodeTool(BaseTool):
    """创建GNS3节点的工具"""
    
    # 工具名称（AI通过这个名字调用）
    name: str = "create_gns3_node"
    
    # 工具描述（告诉AI这个工具能做什么、怎么用）
    description: str = """
    在GNS3项目中创建网络节点。
    
    输入格式（JSON）：
    {
        "project_id": "项目ID",
        "nodes": [
            {"template_id": "模板ID", "x": 100, "y": 200},
            {"template_id": "模板ID", "x": 300, "y": 200}
        ]
    }
    
    返回：创建结果，包含节点ID和名称
    """
    
    def _run(self, tool_input: str) -> dict:
        """实际执行创建节点的逻辑"""
        
        # 1. 解析输入
        data = json.loads(tool_input)
        project_id = data["project_id"]
        nodes = data["nodes"]
        
        # 2. 调用GNS3 API创建节点
        results = []
        for node_data in nodes:
            # 这里调用实际的GNS3 API
            node = create_node_via_api(
                project_id=project_id,
                template_id=node_data["template_id"],
                x=node_data["x"],
                y=node_data["y"]
            )
            results.append({
                "node_id": node.id,
                "name": node.name,
                "status": "success"
            })
        
        # 3. 返回结果
        return {"created_nodes": results}
```

**关键点**：
- 继承 `BaseTool` 类
- 定义 `name`：工具的唯一标识
- 定义 `description`：详细描述，AI靠这个理解怎么用
- 实现 `_run` 方法：实际执行逻辑

### 5.2 定义状态

```python
# agent/state.py
from typing import Annotated
from typing_extensions import TypedDict
from langchain.messages import AnyMessage
import operator

class AgentState(TypedDict):
    """Agent的状态定义"""
    
    # 消息历史
    messages: Annotated[list[AnyMessage], operator.add]
    
    # 当前项目信息
    project_id: str | None
```

### 5.3 定义节点

```python
# agent/nodes.py
from langchain.messages import SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

# 准备工具
tools = [GNS3CreateNodeTool(), GNS3LinkTool(), GNS3TemplateTool()]
tools_by_name = {tool.name: tool for tool in tools}

# 创建AI模型并绑定工具
model = ChatOpenAI(model="deepseek-chat")
model_with_tools = model.bind_tools(tools)

# 系统提示词
SYSTEM_PROMPT = """
你是一个网络自动化助手，可以帮助用户在GNS3中创建和管理网络拓扑。

你可以使用以下工具：
- get_gns3_templates: 获取可用的设备模板
- create_gns3_node: 创建网络节点
- create_gns3_link: 创建节点之间的连接

工作流程：
1. 先获取模板，了解有哪些设备可用
2. 根据用户需求创建节点
3. 创建节点之间的连接
"""

def llm_call(state: dict):
    """AI思考节点"""
    
    # 构建消息
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    
    # 调用AI
    response = model_with_tools.invoke(messages)
    
    return {"messages": [response]}


def tool_node(state: dict):
    """工具执行节点"""
    
    results = []
    
    # 获取AI要求执行的工具调用
    for tool_call in state["messages"][-1].tool_calls:
        # 找到对应的工具
        tool = tools_by_name[tool_call["name"]]
        
        # 执行工具
        result = tool.invoke(tool_call["args"])
        
        # 包装结果
        results.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )
    
    return {"messages": results}
```

### 5.4 定义路由逻辑

```python
# agent/routing.py
from langgraph.graph import END

def should_continue(state: dict):
    """决定下一步"""
    
    last_message = state["messages"][-1]
    
    # 如果AI要调用工具
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_node"
    
    # 否则结束
    return END
```

### 5.5 组装图

```python
# agent/graph.py
from langgraph.graph import StateGraph, START, END

# 创建图
builder = StateGraph(AgentState)

# 添加节点
builder.add_node("llm_call", llm_call)
builder.add_node("tool_node", tool_node)

# 添加边
builder.add_edge(START, "llm_call")  # 开始 → AI思考

builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node",
        END: END,
    }
)

builder.add_edge("tool_node", "llm_call")  # 工具执行完 → 回到AI

# 编译图
agent = builder.compile()
```

### 5.6 运行Agent

```python
# main.py
from langchain.messages import HumanMessage

# 用户输入
user_input = "生成2个PC + 1个FortiGate网络拓扑"

# 初始状态
initial_state = {
    "messages": [HumanMessage(content=user_input)],
    "project_id": "your-project-id"
}

# 运行Agent
result = agent.invoke(initial_state)

# 获取最终回复
final_response = result["messages"][-1].content
print(final_response)
```

---

## 6. 运行流程详解

### 第一轮：获取模板

```
用户: "生成2个PC + 1个FortiGate网络拓扑"
     ↓
AI思考: "我需要先知道有哪些设备模板可用"
     ↓
AI决定: 调用 get_gns3_templates 工具
     ↓
工具返回: [
    {"name": "VPCS", "template_id": "aaa-111"},
    {"name": "FortiGate", "template_id": "bbb-222"}
]
```

### 第二轮：创建节点

```
AI思考: "好的，我找到了VPCS和FortiGate模板，现在创建节点"
     ↓
AI决定: 调用 create_gns3_node 工具
        参数: {
            "project_id": "xxx",
            "nodes": [
                {"template_id": "aaa-111", "x": 0, "y": 0},    # PC1
                {"template_id": "aaa-111", "x": 300, "y": 0},  # PC2
                {"template_id": "bbb-222", "x": 150, "y": 200} # FortiGate
            ]
        }
     ↓
工具返回: {
    "created_nodes": [
        {"node_id": "node-1", "name": "PC1"},
        {"node_id": "node-2", "name": "PC2"},
        {"node_id": "node-3", "name": "FortiGate-1"}
    ]
}
```

### 第三轮：创建连接

```
AI思考: "节点创建好了，现在把PC连接到FortiGate"
     ↓
AI决定: 调用 create_gns3_link 工具
        参数: {
            "project_id": "xxx",
            "links": [
                {"node_id1": "node-1", "port1": "Ethernet0", 
                 "node_id2": "node-3", "port2": "port1"},
                {"node_id1": "node-2", "port1": "Ethernet0",
                 "node_id2": "node-3", "port2": "port2"}
            ]
        }
     ↓
工具返回: {"links_created": 2}
```

### 第四轮：完成

```
AI思考: "所有任务完成了！"
     ↓
AI回复: "我已经为您创建了网络拓扑：
        - 2个PC (PC1, PC2)
        - 1个FortiGate防火墙
        - PC1和PC2都已连接到FortiGate
        拓扑创建完成！"
     ↓
END
```

---

## 7. 总结与进阶

### 核心要点回顾

1. **状态（State）**：共享的记事本，记录所有信息
2. **节点（Node）**：执行具体任务的函数
3. **边（Edge）**：控制执行流程
4. **工具（Tool）**：Agent的"手"，执行实际操作
5. **条件路由**：让Agent能够智能决策

### 开发步骤总结

```
1. 定义状态 → 决定要记录哪些信息
2. 开发工具 → 实现具体功能
3. 编写节点 → AI调用 + 工具执行
4. 设计路由 → 决定流程走向
5. 组装图   → 把所有部分连接起来
6. 运行测试 → 验证功能
```

### 进阶学习

- **添加记忆**：使用 `SqliteSaver` 保存对话历史
- **人工介入**：在关键步骤添加人工确认
- **并行执行**：同时执行多个工具
- **错误处理**：优雅处理工具执行失败

### 参考资源

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 工具开发指南](https://python.langchain.com/docs/modules/tools/)
- [GNS3 Copilot 源码](https://github.com/yueguobin/gns3-copilot)

---

> 💡 **提示**：最好的学习方式是动手实践！建议你克隆 GNS3 Copilot 项目，阅读源码，然后尝试添加自己的工具。
