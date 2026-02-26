# GNS3 Copilot Agent 调用流程完全指南

## 概述

本文档详细说明了当用户在 GNS3 Copilot 界面输入命令到执行完成的整个调用链流程。以"生成一个拓扑，2个PC通过1个FortiGate相连"为例进行详细讲解。

---

## 完整调用流程

### 阶段 1: 用户输入触发

**位置**: `src/gns3_copilot/ui_model/chat.py` 第 493 行

```python
for chunk in agent.stream(
    {
        "messages": [HumanMessage(content=user_text)],
    },
    config=config,
    stream_mode="messages",
):
```

**步骤**:
1. 用户在 Streamlit 界面输入: `"生成一个拓扑，2个PC通过1个FortiGate相连"`
2. 消息被包装成 `HumanMessage` 对象
3. 通过 `agent.stream()` 方法提交到编译后的 LangGraph Agent

**输入数据**:
```python
{
    "messages": [HumanMessage(content="生成一个拓扑，2个PC通过1个FortiGate相连")],
    "selected_project": ("Project1", "project_id_1", 5, 10, "opened"),
    "llm_calls": 0,
    "conversation_title": None,
    "remaining_steps": 28,
}
```

---

### 阶段 2: START → llm_call 节点

**位置**: `src/gns3_copilot/agent/gns3_copilot.py` 第 537 行

```python
agent_builder.add_edge(START, "llm_call")
```

**执行内容**: 进入 `llm_call()` 函数 (第 176-243 行)

#### 2.1 加载系统提示词

```python
current_prompt = load_system_prompt()
```
从 `src/gns3_copilot/prompts/` 加载系统提示词，定义 AI 助手的行为和可用工具。

#### 2.2 构建上下文消息

**步骤 A**: 获取已选择的项目信息
```python
selected_p = state.get("selected_project")
# 结果: ("Project1", "project_id_1", 5, 10, "opened")
```

**步骤 B**: 尝试获取现有拓扑信息
```python
topology_tool = GNS3TopologyTool()
topology = topology_tool._run(project_id="project_id_1")
# 返回当前 GNS3 项目中所有现存的节点和链路信息
```

**步骤 C**: 生成上下文系统消息
```python
context_messages.append(
    SystemMessage(
        content=f"""Current Context: 
        User has selected project: 
        Project_Name=Project1, 
        Project_ID=project_id_1, 
        Device_Number=5, 
        Link_Number=10, 
        Status=opened
        
        Topology:
        {existing_topology_info}"""
    )
)
```

#### 2.3 合并完整消息列表

```python
full_messages = [
    SystemMessage(content=current_prompt),           # 系统提示词
    SystemMessage(content="Current Context: ..."),   # 项目和拓扑上下文
    HumanMessage(content="生成一个拓扑...")           # 用户输入
]
```

#### 2.4 创建带工具的模型

```python
model_with_tools = create_base_model_with_tools(tools)
```

此时调用 `model_factory.py` 中的工厂函数，为 LLM 绑定以下工具:
- `GNS3TemplateTool()` - 获取节点模板
- `GNS3TopologyTool()` - 读取拓扑
- `GNS3CreateNodeTool()` - 创建节点 ✓ (需要使用)
- `GNS3LinkTool()` - 创建链路 ✓ (需要使用)
- `GNS3StartNodeTool()` - 启动节点
- 等其他工具...

#### 2.5 调用 LLM (第一次)

```python
result = model_with_tools.invoke(full_messages)
```

**LLM 分析**:
- 输入: "生成一个拓扑，2个PC通过1个FortiGate相连"
- 上下文: 现有拓扑信息 + 可用工具
- 分析结果: 需要执行以下操作：
  1. 创建 PC1 节点
  2. 创建 PC2 节点
  3. 创建 FortiGate 节点
  4. 创建 PC1-FortiGate 之间的链路
  5. 创建 PC2-FortiGate 之间的链路

**LLM 返回**:
```python
AIMessage(
    content="我将为您生成包含2个PC和1个FortiGate的拓扑。让我现在创建所需的节点和连接。",
    tool_calls=[
        {
            "id": "call_123_1",
            "name": "gns3_create_node",
            "args": {"name": "PC1", "template": "VPCS", "x": 100, "y": 100}
        },
        {
            "id": "call_123_2",
            "name": "gns3_create_node",
            "args": {"name": "PC2", "template": "VPCS", "x": 300, "y": 100}
        },
        {
            "id": "call_123_3",
            "name": "gns3_create_node",
            "args": {"name": "FortiGate", "template": "FortiGate", "x": 200, "y": 250}
        },
        {
            "id": "call_123_4",
            "name": "gns3_link",
            "args": {"from_node_id": "node_pc1", "to_node_id": "node_fg"}
        },
        {
            "id": "call_123_5",
            "name": "gns3_link",
            "args": {"from_node_id": "node_pc2", "to_node_id": "node_fg"}
        },
    ],
    response_metadata={"finish_reason": "tool_calls"}
)
```

**加入 state["messages"] 消息列表**:
```
state["messages"] = [
    HumanMessage("生成一个拓扑..."),
    AIMessage(...with tool_calls)  # ← 新增
]
```

**返回结果到 stream()**:
```python
{
    "messages": [AIMessage(...)],
    "llm_calls": 1,
    "topology_info": {...}
}
```

---

### 阶段 3: 路由判断 - should_continue()

**位置**: `src/gns3_copilot/agent/gns3_copilot.py` 第 445-468 行

**路由逻辑**:
```python
def should_continue(state) -> Literal["tool_node", "title_generator_node", END]:
    last_message = state["messages"][-1]
    
    if last_message.tool_calls:  # ← AIMessage 有 tool_calls
        return "tool_node"        # ✓ 返回此值
    
    if current_title in [None, "GNS3 Session"]:
        return "title_generator_node"
    
    return END
```

**判断结果**: 因为 `last_message.tool_calls` 不为空 → **路由到 `tool_node`**

---

### 阶段 4: tool_node 节点执行所有工具

**位置**: `src/gns3_copilot/agent/gns3_copilot.py` 第 392-424 行

```python
def tool_node(state: dict):
    result = []
    
    for tool_call in state["messages"][-1].tool_calls:  # 遍历5个工具调用
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        
        tool = tools_by_name[tool_name]
        observation = tool.invoke(tool_args)
        
        result.append(
            ToolMessage(
                content=observation,
                tool_call_id=tool_call["id"],
                name=tool_name,
            )
        )
    
    return {"messages": result}
```

#### 工具调用序列

**工具调用 1 & 2 & 3: 创建节点**

| 调用 | 工具 | 输入参数 | 执行 | 输出 |
|------|------|---------|------|------|
| 1 | GNS3CreateNodeTool | name="PC1", template="VPCS" | 调用 GNS3 API 创建 PC1 | `{"node_id": "abc123", "status": "created", "x": 100, "y": 100}` |
| 2 | GNS3CreateNodeTool | name="PC2", template="VPCS" | 调用 GNS3 API 创建 PC2 | `{"node_id": "def456", "status": "created", "x": 300, "y": 100}` |
| 3 | GNS3CreateNodeTool | name="FortiGate", template="FortiGate" | 调用 GNS3 API 创建 FortiGate | `{"node_id": "ghi789", "status": "created", "x": 200, "y": 250}` |

**工具调用 4 & 5: 创建链路**

| 调用 | 工具 | 输入参数 | 执行 | 输出 |
|------|------|---------|------|------|
| 4 | GNS3LinkTool | from_node_id="abc123", to_node_id="ghi789" | 在 PC1 和 FortiGate 之间创建链路 | `{"link_id": "link_001", "status": "created"}` |
| 5 | GNS3LinkTool | from_node_id="def456", to_node_id="ghi789" | 在 PC2 和 FortiGate 之间创建链路 | `{"link_id": "link_002", "status": "created"}` |

#### tool_node 返回值

```python
{
    "messages": [
        ToolMessage(content={"node_id": "abc123", ...}, tool_call_id="call_123_1", name="gns3_create_node"),
        ToolMessage(content={"node_id": "def456", ...}, tool_call_id="call_123_2", name="gns3_create_node"),
        ToolMessage(content={"node_id": "ghi789", ...}, tool_call_id="call_123_3", name="gns3_create_node"),
        ToolMessage(content={"link_id": "link_001", ...}, tool_call_id="call_123_4", name="gns3_link"),
        ToolMessage(content={"link_id": "link_002", ...}, tool_call_id="call_123_5", name="gns3_link"),
    ]
}
```

**更新到 state["messages"]**:
```
state["messages"] = [
    HumanMessage("生成一个拓扑..."),
    AIMessage(...with tool_calls),
    ToolMessage(...node_id: abc123),      # ← 新增
    ToolMessage(...node_id: def456),      # ← 新增
    ToolMessage(...node_id: ghi789),      # ← 新增
    ToolMessage(...link_id: link_001),    # ← 新增
    ToolMessage(...link_id: link_002),    # ← 新增
]
```

---

### 阶段 5: 路由判断 - recursion_limit_continue()

**位置**: `src/gns3_copilot/agent/gns3_copilot.py` 第 489-517 行

```python
def recursion_limit_continue(state: MessagesState) -> Literal["llm_call", END]:
    last_message = state["messages"][-1]
    
    if isinstance(last_message, ToolMessage):  # ← 最后是 ToolMessage
        if state["remaining_steps"] < 4:
            return END
        return "llm_call"  # ✓ 返回此值(还有步数剩余)
    
    return END
```

**判断结果**: 因为 `last_message` 是 `ToolMessage` 且 `remaining_steps >= 4` → **路由回 `llm_call`**

---

### 阶段 6: LLM 第二次调用

**位置**: 再次进入 `llm_call()` 函数

**与第一次的区别**: 
- 消息列表现在包含了所有工具执行的结果
- LLM 看到所有工具已成功执行
- LLM 需要生成最终的汇总响应

**LLM 分析**:
```
用户: "生成一个拓扱..."
AI助手已经:
  ✓ 创建了 PC1 (node_id: abc123)
  ✓ 创建了 PC2 (node_id: def456)
  ✓ 创建了 FortiGate (node_id: ghi789)
  ✓ 创建了 PC1-FortiGate 链路 (link_id: link_001)
  ✓ 创建了 PC2-FortiGate 链路 (link_id: link_002)

所以现在应该生成最终响应，不需要再调用工具。
```

**LLM 返回** (第二次):
```python
AIMessage(
    content="""已为您成功生成所需的网络拓扑！
    
拓扑构成:
- PC1 和 PC2: 两个虚拟 PC
- FortiGate: 中心防火墙
- PC1 和 PC2 均通过一条链路连接到 FortiGate

拓扑已保存到项目中，您可以在 GNS3 界面中看到这个网络配置。
建议您启动节点并检查网络连接。""",
    tool_calls=[],  # ← 无工具调用
    response_metadata={"finish_reason": "stop"}
)
```

---

### 阶段 7: 路由判断 - should_continue() (第二次)

**判断条件**:
```python
if last_message.tool_calls:  # ← tool_calls 为空数组 []
    return "tool_node"       # ✗ 不返回
```

**路由逻辑**:
```python
if current_title in [None, "GNS3 Session"]:  # ← conversation_title 仍为 None
    return "title_generator_node"             # ✓ 返回此值
```

**判断结果**: → **路由到 `title_generator_node`**

---

### 阶段 8: generate_title() 节点

**位置**: `src/gns3_copilot/agent/gns3_copilot.py` 第 258-313 行

```python
def generate_title(state: MessagesState) -> dict:
    if state.get("conversation_title") in [None, "New Session"]:
        messages = state["messages"]
        
        title_prompt_messages = [
            SystemMessage(content=TITLE_PROMPT),
            messages[0],    # 用户的第一条消息
            messages[-1],   # 最后的 AI 响应
        ]
        
        title_model = create_title_model()
        response = title_model.invoke(title_prompt_messages)
        
        new_title = response.content.strip()[:38] + "..."
        
        return {"conversation_title": new_title}
    
    return {}
```

**标题生成过程**:
- 轻量级 LLM 分析用户消息和 AI 的最终响应
- 生成简洁的标题
- 截断至 38 字符 + "..."

**生成的标题**: `"生成包含PC和FortiGate的网络拓..."`

**返回结果**:
```python
{"conversation_title": "生成包含PC和FortiGate的网络拓..."}
```

---

### 阶段 9: 最终边 - 转向 END

**位置**: `src/gns3_copilot/agent/gns3_copilot.py` 第 560-561 行

```python
agent_builder.add_edge("title_generator_node", END)
```

stream() 流结束，返回控制权给 chat.py

---

## Streamlit 显示层处理

**位置**: `src/gns3_copilot/ui_model/chat.py` 第 493-710 行

```python
for chunk in agent.stream(...):
    for msg in chunk:
        if isinstance(msg, AIMessage):
            # 第一个 AIMessage (带 tool_calls):
            # 显示文本 + 显示工具调用详情 (可展开)
            
        if isinstance(msg, ToolMessage):
            # 5 个 ToolMessage:
            # 显示工具执行结果 (可展开)
            
        if isinstance(msg, AIMessage):
            # 第二个 AIMessage (无 tool_calls):
            # 显示最终回复文本
```

**最终显示效果**:
```
👤 用户:
生成一个拓扑，2个PC通过1个FortiGate相连

🤖 助手:
我将为您生成包含2个PC和1个FortiGate的拓扑。让我现在创建所需的节点和连接。

[Tool Call: gns3_create_node] ▼
  节点: PC1

[Tool Call: gns3_create_node] ▼
  节点: PC2

[Tool Call: gns3_create_node] ▼
  节点: FortiGate

[Tool Call: gns3_link] ▼
  链路: PC1 - FortiGate

[Tool Call: gns3_link] ▼
  链路: PC2 - FortiGate

已为您成功生成所需的网络拓扑！
...
```

---

## 数据持久化

**位置**: `src/gns3_copilot/ui_model/chat.py` 第 683-688 行

```python
state_history = agent.get_state(config)

if not state_history[0]:
    pass
else:
    st.session_state["state_history"] = state_history
```

完整的 `state` 被保存到 SQLite 数据库:
- 数据库文件: `gns3_langgraph.db`
- 线程 ID: 用作查询和恢复对话的键
- 存储内容: 所有消息、项目信息、拓扑数据、对话标题

---

## 状态变化总结

| 阶段 | state.messages 数量 | state.llm_calls | state.conversation_title | 下一个节点 |
|------|--------|--------|--------|--------|
| 初始 | 1 | 0 | None | START |
| 阶段 2 | 2 | 1 | None | should_continue |
| 阶段 4 | 7 | 1 | None | recursion_limit_continue |
| 阶段 6 | 8 | 2 | None | should_continue |
| 阶段 8 | 8 | 2 | "生成包含PC和..." | END |

---

## 关键配置参数

```python
config = {
    "configurable": {
        "thread_id": "current_thread_id",  # 唯一标识对话会话
        "max_iterations": 50,               # 最多 LLM 调用次数
    },
    "recursion_limit": 28,                  # 最多图执行步数
}
```

- `recursion_limit=28`: 防止无限循环
- `stream_mode="messages"`: 逐条消息流式返回
- `thread_id`: 实现会话持久化

---

## 错误处理机制

### 工具执行失败

如果某个工具调用失败 (例如 GNS3 API 连接异常):

```python
try:
    observation, simulated_topology = execute_dry_run_tool(...)
except Exception as exc:
    observation = {
        "error": f"Dry-run execution failed for {tool_name}: {exc}"
    }
    logger.exception("Dry-run tool execution failed for %s", tool_name)
```

`ToolMessage` 会包含错误信息，LLM 在第二次调用时会看到并可能：
1. 重新尝试
2. 调整参数后重新调用
3. 生成错误提示给用户

### 递归深度控制

```python
def recursion_limit_continue(state: MessagesState):
    if isinstance(last_message, ToolMessage):
        if state["remaining_steps"] < 4:
            return END  # ← 防止无限循环
        return "llm_call"
```

当临近递归限制时自动停止，防止资源耗尽。

---

## 性能优化

### 缓存机制

```python
@st.cache_resource(show_spinner="Compiling LangGraph agent...")
def get_agent():
    return agent_builder.compile(checkpointer=get_checkpointer())

agent = get_agent()  # 只编译一次，复用
```

### 流式处理

```python
for chunk in agent.stream(..., stream_mode="messages"):
    # 每个消息块立即处理和显示
    # 而不是等待整个流完成
```

优点:
- 用户能看到实时进度
- 内存使用效率高
- 更好的交互体验

---

## 总结流程图

```
用户输入
  ↓
agent.stream() 启动
  ↓
START
  ↓
[1st LLM Call] → AIMessage + tool_calls
  ↓
[Tool Execution] → 5 x ToolMessage
  ↓
[2nd LLM Call] → AIMessage (最终响应)
  ↓
[Title Generation] → conversation_title
  ↓
END
  ↓
保存到数据库
  ↓
Streamlit 显示
  ↓
完成
```

---

## 扩展阅读

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [Streamlit 官方文档](https://docs.streamlit.io/)
- GNS3 Copilot 项目结构说明
- 工具开发指南

