# GNS3 Copilot Agent Call Flow Complete Guide

## Overview

This document details the complete call chain from when a user enters a command in the GNS3 Copilot interface to when execution completes. We use "Generate a topology with 2 PCs connected through 1 FortiGate" as an example to explain the detailed flow.

---

## Complete Call Flow

### Stage 1: User Input Triggered

**Location**: `src/gns3_copilot/ui_model/chat.py` Line 493

```python
for chunk in agent.stream(
    {
        "messages": [HumanMessage(content=user_text)],
    },
    config=config,
    stream_mode="messages",
):
```

**Steps**:
1. User enters in Streamlit interface: `"Generate a topology with 2 PCs connected through 1 FortiGate"`
2. Message is wrapped in `HumanMessage` object
3. Submitted to compiled LangGraph Agent via `agent.stream()` method

**Input Data**:
```python
{
    "messages": [HumanMessage(content="Generate a topology with 2 PCs connected through 1 FortiGate")],
    "selected_project": ("Project1", "project_id_1", 5, 10, "opened"),
    "llm_calls": 0,
    "conversation_title": None,
    "remaining_steps": 28,
}
```

---

### Stage 2: START → llm_call Node

**Location**: `src/gns3_copilot/agent/gns3_copilot.py` Line 537

```python
agent_builder.add_edge(START, "llm_call")
```

**Executes**: `llm_call()` function (Lines 176-243)

#### 2.1 Load System Prompt

```python
current_prompt = load_system_prompt()
```
Loads system prompt from `src/gns3_copilot/prompts/`, defining assistant behavior and available tools.

#### 2.2 Build Context Messages

**Step A**: Get selected project information
```python
selected_p = state.get("selected_project")
# Result: ("Project1", "project_id_1", 5, 10, "opened")
```

**Step B**: Attempt to retrieve existing topology
```python
topology_tool = GNS3TopologyTool()
topology = topology_tool._run(project_id="project_id_1")
# Returns all existing nodes and links in the GNS3 project
```

**Step C**: Generate context system message
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

#### 2.3 Merge Complete Message List

```python
full_messages = [
    SystemMessage(content=current_prompt),           # System prompt
    SystemMessage(content="Current Context: ..."),   # Project and topology context
    HumanMessage(content="Generate a topology...")   # User input
]
```

#### 2.4 Create Model with Tools

```python
model_with_tools = create_base_model_with_tools(tools)
```

Calls factory function in `model_factory.py` to bind the following tools to LLM:
- `GNS3TemplateTool()` - Get node templates
- `GNS3TopologyTool()` - Read topology
- `GNS3CreateNodeTool()` - Create nodes ✓ (needed)
- `GNS3LinkTool()` - Create links ✓ (needed)
- `GNS3StartNodeTool()` - Start nodes
- Other tools...

#### 2.5 Call LLM (First Call)

```python
result = model_with_tools.invoke(full_messages)
```

**LLM Analysis**:
- Input: "Generate a topology with 2 PCs connected through 1 FortiGate"
- Context: Existing topology info + available tools
- Analysis result: Need to execute:
  1. Create PC1 node
  2. Create PC2 node
  3. Create FortiGate node
  4. Create link between PC1 and FortiGate
  5. Create link between PC2 and FortiGate

**LLM Return**:
```python
AIMessage(
    content="I'll generate a topology with 2 PCs and 1 FortiGate for you. Let me create the required nodes and connections now.",
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

**Added to state["messages"]**:
```
state["messages"] = [
    HumanMessage("Generate a topology..."),
    AIMessage(...with tool_calls)  # ← New
]
```

**Return result to stream()**:
```python
{
    "messages": [AIMessage(...)],
    "llm_calls": 1,
    "topology_info": {...}
}
```

---

### Stage 3: Routing Decision - should_continue()

**Location**: `src/gns3_copilot/agent/gns3_copilot.py` Lines 445-468

**Routing Logic**:
```python
def should_continue(state) -> Literal["tool_node", "title_generator_node", END]:
    last_message = state["messages"][-1]
    
    if last_message.tool_calls:  # ← AIMessage has tool_calls
        return "tool_node"        # ✓ Return this
    
    if current_title in [None, "GNS3 Session"]:
        return "title_generator_node"
    
    return END
```

**Decision Result**: Since `last_message.tool_calls` is not empty → **Route to `tool_node`**

---

### Stage 4: tool_node Node Executes All Tools

**Location**: `src/gns3_copilot/agent/gns3_copilot.py` Lines 392-424

```python
def tool_node(state: dict):
    result = []
    
    for tool_call in state["messages"][-1].tool_calls:  # Iterate 5 tool calls
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

#### Tool Call Sequence

**Tool Calls 1, 2 & 3: Create Nodes**

| Call | Tool | Input Args | Execution | Output |
|------|------|-----------|-----------|--------|
| 1 | GNS3CreateNodeTool | name="PC1", template="VPCS" | Call GNS3 API to create PC1 | `{"node_id": "abc123", "status": "created", "x": 100, "y": 100}` |
| 2 | GNS3CreateNodeTool | name="PC2", template="VPCS" | Call GNS3 API to create PC2 | `{"node_id": "def456", "status": "created", "x": 300, "y": 100}` |
| 3 | GNS3CreateNodeTool | name="FortiGate", template="FortiGate" | Call GNS3 API to create FortiGate | `{"node_id": "ghi789", "status": "created", "x": 200, "y": 250}` |

**Tool Calls 4 & 5: Create Links**

| Call | Tool | Input Args | Execution | Output |
|------|------|-----------|-----------|--------|
| 4 | GNS3LinkTool | from_node_id="abc123", to_node_id="ghi789" | Create link between PC1 and FortiGate | `{"link_id": "link_001", "status": "created"}` |
| 5 | GNS3LinkTool | from_node_id="def456", to_node_id="ghi789" | Create link between PC2 and FortiGate | `{"link_id": "link_002", "status": "created"}` |

#### tool_node Return Value

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

**Updated in state["messages"]**:
```
state["messages"] = [
    HumanMessage("Generate a topology..."),
    AIMessage(...with tool_calls),
    ToolMessage(...node_id: abc123),      # ← New
    ToolMessage(...node_id: def456),      # ← New
    ToolMessage(...node_id: ghi789),      # ← New
    ToolMessage(...link_id: link_001),    # ← New
    ToolMessage(...link_id: link_002),    # ← New
]
```

---

### Stage 5: Routing Decision - recursion_limit_continue()

**Location**: `src/gns3_copilot/agent/gns3_copilot.py` Lines 489-517

```python
def recursion_limit_continue(state: MessagesState) -> Literal["llm_call", END]:
    last_message = state["messages"][-1]
    
    if isinstance(last_message, ToolMessage):  # ← Last is ToolMessage
        if state["remaining_steps"] < 4:
            return END
        return "llm_call"  # ✓ Return this (steps remaining)
    
    return END
```

**Decision Result**: Since `last_message` is `ToolMessage` and `remaining_steps >= 4` → **Route back to `llm_call`**

---

### Stage 6: Second LLM Call

**Location**: Enter `llm_call()` function again

**Difference from First Call**:
- Message list now contains results from all tool executions
- LLM sees all tools executed successfully
- LLM needs to generate final summary response

**LLM Analysis**:
```
User: "Generate a topology..."
AI Assistant has already:
  ✓ Created PC1 (node_id: abc123)
  ✓ Created PC2 (node_id: def456)
  ✓ Created FortiGate (node_id: ghi789)
  ✓ Created link PC1-FortiGate (link_id: link_001)
  ✓ Created link PC2-FortiGate (link_id: link_002)

So now should generate final response without calling tools again.
```

**LLM Return** (Second Call):
```python
AIMessage(
    content="""Successfully generated the required network topology!

Topology consists of:
- PC1 and PC2: Two virtual PCs
- FortiGate: Central firewall
- Both PC1 and PC2 connected to FortiGate via one link each

Topology is now saved in the project, you can see this network configuration in GNS3.
I recommend starting the nodes and checking network connectivity.""",
    tool_calls=[],  # ← No tool calls
    response_metadata={"finish_reason": "stop"}
)
```

---

### Stage 7: Routing Decision - should_continue() (Second Time)

**Check condition**:
```python
if last_message.tool_calls:  # ← tool_calls is empty []
    return "tool_node"       # ✗ Not returning
```

**Routing logic**:
```python
if current_title in [None, "GNS3 Session"]:  # ← conversation_title still None
    return "title_generator_node"             # ✓ Return this
```

**Decision Result**: → **Route to `title_generator_node`**

---

### Stage 8: generate_title() Node

**Location**: `src/gns3_copilot/agent/gns3_copilot.py` Lines 258-313

```python
def generate_title(state: MessagesState) -> dict:
    if state.get("conversation_title") in [None, "New Session"]:
        messages = state["messages"]
        
        title_prompt_messages = [
            SystemMessage(content=TITLE_PROMPT),
            messages[0],    # User's first message
            messages[-1],   # Last AI response
        ]
        
        title_model = create_title_model()
        response = title_model.invoke(title_prompt_messages)
        
        new_title = response.content.strip()[:38] + "..."
        
        return {"conversation_title": new_title}
    
    return {}
```

**Title Generation Process**:
- Lightweight LLM analyzes user message and AI's final response
- Generates concise title
- Truncates to 38 characters + "..."

**Generated Title**: `"Generate network topology with PC ..."`

**Return Result**:
```python
{"conversation_title": "Generate network topology with PC ..."}
```

---

### Stage 9: Final Edge - Go to END

**Location**: `src/gns3_copilot/agent/gns3_copilot.py` Lines 560-561

```python
agent_builder.add_edge("title_generator_node", END)
```

stream() flow ends, returns control to chat.py

---

## Streamlit Display Layer Processing

**Location**: `src/gns3_copilot/ui_model/chat.py` Lines 493-710

```python
for chunk in agent.stream(...):
    for msg in chunk:
        if isinstance(msg, AIMessage):
            # First AIMessage (with tool_calls):
            # Display text + show tool call details (expandable)
            
        if isinstance(msg, ToolMessage):
            # 5 ToolMessages:
            # Display tool execution results (expandable)
            
        if isinstance(msg, AIMessage):
            # Second AIMessage (no tool_calls):
            # Display final reply text
```

**Final Display Effect**:
```
👤 User:
Generate a topology with 2 PCs connected through 1 FortiGate

🤖 Assistant:
I'll generate a topology with 2 PCs and 1 FortiGate for you. Let me create the required nodes and connections now.

[Tool Call: gns3_create_node] ▼
  Node: PC1

[Tool Call: gns3_create_node] ▼
  Node: PC2

[Tool Call: gns3_create_node] ▼
  Node: FortiGate

[Tool Call: gns3_link] ▼
  Link: PC1 - FortiGate

[Tool Call: gns3_link] ▼
  Link: PC2 - FortiGate

Successfully generated the required network topology!
...
```

---

## Data Persistence

**Location**: `src/gns3_copilot/ui_model/chat.py` Lines 683-688

```python
state_history = agent.get_state(config)

if not state_history[0]:
    pass
else:
    st.session_state["state_history"] = state_history
```

Complete `state` is saved to SQLite database:
- Database file: `gns3_langgraph.db`
- Thread ID: Used as key for querying and recovering conversations
- Stored content: All messages, project info, topology data, conversation title

---

## State Changes Summary

| Stage | state.messages Count | state.llm_calls | state.conversation_title | Next Node |
|-------|--------|--------|--------|--------|
| Initial | 1 | 0 | None | START |
| Stage 2 | 2 | 1 | None | should_continue |
| Stage 4 | 7 | 1 | None | recursion_limit_continue |
| Stage 6 | 8 | 2 | None | should_continue |
| Stage 8 | 8 | 2 | "Generate network topology ..." | END |

---

## Key Configuration Parameters

```python
config = {
    "configurable": {
        "thread_id": "current_thread_id",  # Unique identifier for conversation session
        "max_iterations": 50,               # Maximum number of LLM calls
    },
    "recursion_limit": 28,                  # Maximum graph execution steps
}
```

- `recursion_limit=28`: Prevents infinite loops
- `stream_mode="messages"`: Returns messages streaming one-by-one
- `thread_id`: Enables session persistence

---

## Error Handling Mechanism

### Tool Execution Failure

If a tool call fails (e.g., GNS3 API connection exception):

```python
try:
    observation, simulated_topology = execute_dry_run_tool(...)
except Exception as exc:
    observation = {
        "error": f"Dry-run execution failed for {tool_name}: {exc}"
    }
    logger.exception("Dry-run tool execution failed for %s", tool_name)
```

`ToolMessage` includes error information. LLM on second call will see it and may:
1. Retry
2. Adjust parameters and call again
3. Generate error message for user

### Recursion Depth Control

```python
def recursion_limit_continue(state: MessagesState):
    if isinstance(last_message, ToolMessage):
        if state["remaining_steps"] < 4:
            return END  # ← Prevents infinite loops
        return "llm_call"
```

Automatically stops when approaching recursion limit to prevent resource exhaustion.

---

## Performance Optimization

### Caching Mechanism

```python
@st.cache_resource(show_spinner="Compiling LangGraph agent...")
def get_agent():
    return agent_builder.compile(checkpointer=get_checkpointer())

agent = get_agent()  # Compiled only once, then reused
```

### Streaming Processing

```python
for chunk in agent.stream(..., stream_mode="messages"):
    # Each message chunk is processed and displayed immediately
    # Rather than waiting for entire stream to complete
```

Benefits:
- Users see real-time progress
- Memory usage is efficient
- Better user experience

---

## Complete Flow Diagram

```
User Input
  ↓
agent.stream() Start
  ↓
START
  ↓
[1st LLM Call] → AIMessage + tool_calls
  ↓
[Tool Execution] → 5 x ToolMessage
  ↓
[2nd LLM Call] → AIMessage (Final response)
  ↓
[Title Generation] → conversation_title
  ↓
END
  ↓
Save to Database
  ↓
Streamlit Display
  ↓
Complete
```

---

## Further Reading

- [LangGraph Official Documentation](https://langchain-ai.github.io/langgraph/)
- [Streamlit Official Documentation](https://docs.streamlit.io/)
- GNS3 Copilot Project Structure Guide
- Tool Development Guide

