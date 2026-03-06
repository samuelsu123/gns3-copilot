# 拓扑部署请求 - 程序处理流程（渐进式披露）

## 示例用户输入

> "我想做"总部 FortiGate + 分支 FortiGate"的站点互联拓扑：总部有办公网和服务器网，分支有一个办公网，通过 IPsec VPN 互通。请生成两台 FortiGate 的完整配置，要求两边内网可以互访，同时各自本地上网仍走本地WAN。"

注意：本流程适用于**任何拓扑部署请求**（Cisco、FortiGate、Linux 等），FortiGate 相关步骤仅在检测到 FortiGate 关键词时条件触发。

---

## 流程总览

```
用户输入 (chat.py)
    |
    v
agent.stream() 发送 HumanMessage
    |
    v
LangGraph StateGraph 进入 llm_call 节点
    |
    +--> 1. 构建上下文 (系统 prompt + 项目信息 + 拓扑信息)
    +--> 2. [条件] FortiGate 检测 -> 注入 FortiGate 专用 prompt
    +--> 3. 拓扑意图检测 (内部 LLM 调用, 置信度 >= 0.55)
    +--> 4. 用户确认是否生成拓扑 prompt
    +--> 5. 渐进式拓扑技能会话：
    |       Phase 1: 拓扑概要 -> 用户确认/修改
    |       Phase 2: 节点与链路清单 -> 用户确认/修改
    |       Phase 3: 执行步骤+规则+检查清单 -> 用户确认/修改
    |       Phase 4: 合并最终 prompt
    +--> 6. LLM 调用工具创建节点/链路
    +--> 7. [条件] LLM 生成设备配置命令
    +--> 8. [条件] FortiGate 配置拦截 -> 质量审查 -> 执行确认
    +--> 9. 工具执行配置下发
    |
    v
流式响应返回 chat.py 显示
```

---

## 第一步：UI 层捕获用户输入

**文件**: `src/gns3_copilot/ui_model/chat.py`

1. 用户在 Streamlit 聊天输入框中输入文本
2. 生成唯一 `trace_request_id`（UUID），用于全链路追踪
3. 调用 `_build_request_config()` 构建 LangGraph 运行配置（`thread_id`、`recursion_limit=28`）
4. 消息以 `HumanMessage` 形式通过 `agent.stream()` 发送到 LangGraph Agent

---

## 第二步：消息进入 Agent 层（LangGraph StateGraph）

**文件**: `src/gns3_copilot/agent/gns3_copilot.py`

### 2.1 State 定义

`MessagesState` TypedDict 关键字段：
- `messages`：累积的消息列表
- `pending_topology_skill_session`：拓扑技能会话状态（含 `phase`、`confirmed_layers`）
- `pending_topology_prompt_request`：等待用户确认的拓扑 prompt 生成请求
- `pending_fortigate_config_call`：待确认的 FortiGate 配置执行
- `simulated_topology`：干运行模拟状态

### 2.2 图结构

```
START --> llm_call --> [决策点]
                       |-- tool_calls 存在 --> tool_node --> [递归检查] --> llm_call (循环)
                       |-- 首次调用 --> title_generator_node --> END
                       |-- 无 tool_calls --> END
```

---

## 第三步：llm_call 节点 - 上下文构建

**文件**: `src/gns3_copilot/agent/gns3_copilot.py`

### 3.1 基础系统 Prompt + 上下文消息

依次添加：系统 Prompt、项目信息、拓扑信息、澄清选项 Prompt。

### 3.2 FortiGate 条件检测

调用 `should_inject_fortigate_prompt()`：
- 扫描关键词：`"fortigate"`, `"forti"`, `"fgt"`, `"防火墙"`
- **仅当命中时**注入 Fortinet Baseline Prompt 和 FortiGate Strategy Prompt
- 非 FortiGate 请求不触发此步骤

---

## 第四步：拓扑意图检测

**文件**: `src/gns3_copilot/agent/gns3_copilot.py`

1. 使用内部 LLM 调用 + `build_topology_intent_detection_prompt()`
2. LLM 返回置信度分数（0-1），**阈值** >= 0.55 判定为拓扑部署意图
3. 检测通过后，向用户发送确认消息：`build_topology_prompt_confirmation_message()`
4. 用户回复"是" → 启动渐进式技能会话

---

## 第五步：渐进式拓扑技能会话

**文件**: `src/gns3_copilot/agent/gns3_copilot.py`（`_invoke_topology_skill_session_llm()`）
**Skill 文档**: `src/gns3_copilot/prompts/skills/`

### 5.0 Session 初始化

```python
session = {
    "user_request": request_text,
    "active_skill_names": ["topology-prompt-orchestrator", ...],  # 条件加载 fortigate-topology
    "draft_spec": draft_spec,  # 含 fortigate_count、fortigates 列表等结构化字段
    "round": 0,
    "phase": "topology_overview",       # 当前阶段
    "confirmed_layers": {},             # 已确认的各层输出
}
```

技能文档选择：
- **始终加载**：`topology-prompt-orchestrator`（通用编排器）
- **条件加载**：`fortigate-topology`（仅 `is_fortigate_request()` 为 True 时）

### 5.0.1 Prompt 注入优化

为降低 Token 消耗，不同 Phase 注入的上下文量不同：

| 内容 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| 风格参考 (`simple_fgt.txt`) | 完整注入 | 不注入 | 不注入 | 不注入 |
| SKILL.md 文档 | 完整注入 | 仅 Phase 2 片段 | 仅 Phase 3 片段 | 仅 Phase 4 片段 |
| `[已确认 - xxx]` 前序输出 | 无 | Phase 1 输出 | Phase 1+2 输出 | Phase 1+2+3 输出 |

裁剪通过 `_extract_skill_section_for_phase()` 实现，按 `## Phase N` / `### Phase N` 标题切分，保留 preamble + 当前阶段段落。

### 5.1 Phase 1: 拓扑概要（`topology_overview`）

LLM 基于 `build_topology_skill_phase_prompt(phase="topology_overview", ...)` 生成：
- 站点数量与角色
- 设备类型与数量
- 业务网段概要（用户未指定时自动分配默认网段）
- 互联方式与上网策略

**此阶段注入完整风格参考和完整 SKILL 文档**，为 LLM 提供全貌。

校验：`validate_phase_output(phase="topology_overview")` — 检查 `## 拓扑概要` 章节存在。

输出展示给用户，通过 `build_phase_confirmation_message()` 提示确认或修改：
- 用户回复"确认" → 存入 `confirmed_layers["topology_overview"]`，推进到 Phase 2
- 用户回复修改意见 → 留在 Phase 1 重新生成

### 5.2 Phase 2: 节点与链路清单（`node_and_link_plan`）

LLM 基于已确认的 Phase 1 概要生成：
- `## 节点清单`（名称、模板、站点）
- `## 链路清单`（两端节点与端口）

校验：`validate_phase_output(phase="node_and_link_plan")` — 检查两个章节存在。

同样展示给用户确认或修改。

### 5.3 Phase 3: 执行步骤与规则（`execution_steps`）

LLM 基于已确认的 Phase 1+2 内容生成：
- `## 执行步骤`（含完整设备配置 CLI 命令块）
- `## 执行规则`
- `## CRITICAL: 部署完成检查清单`

**SKILL 文档仅注入 Phase 3 相关片段**（含澄清规则段），风格参考不再注入。

校验：`validate_phase_output(phase="execution_steps")` — 检查三个章节存在。
**条件校验**（仅 FortiGate 场景）：
- 检查 `config system interface`、`config router static`、`config firewall policy` 等关键标记
- **VPN 场景额外检查**（仅 `is_vpn_request()` 为 True 时）：`config vpn ipsec phase1-interface`、`phase2-interface`、`set psksecret`
- **IKE 版本约束**：当拓扑概要指定 IKEv2 时，FortiGate Skill 要求显式设置 `set ike-version 2`

校验失败时自动触发修复循环（最多 `TOPOLOGY_PROMPT_MAX_REPAIR_ATTEMPTS` 次）。

同样展示给用户确认或修改。

### 5.4 Phase 4: 合并最终输出（`completed`）

自动将所有已确认层合并为完整可执行 prompt，校验通过后返回 `status="completed"`。

### 5.5 每个阶段的状态流转

```python
# _invoke_topology_skill_session_llm() 返回值
{
    "status": "need_clarification",   # LLM 需要澄清 → 向用户提问
    "status": "phase_completed",      # 当前阶段完成 → 展示给用户确认
    "status": "completed",            # 最终阶段完成 → 输出完整 prompt
    "status": "invalid",              # 修复失败 → 兜底提问
}
```

```
Phase 1 ──确认──> Phase 2 ──确认──> Phase 3 ──确认──> Phase 4 (自动合并)
   ^                  ^                  ^
   |                  |                  |
 修改意见          修改意见          修改意见
 (重新生成)       (重新生成)       (重新生成)
```

---

## 第六步：LLM 调用工具创建拓扑

**文件**: `src/gns3_copilot/agent/gns3_copilot.py`

完整 prompt 注入对话后，LLM 按执行步骤依次调用工具：

| 工具 | 用途 |
|------|------|
| `GNS3CreateNodeTool` | 创建节点 |
| `GNS3LinkTool` | 创建链路 |
| `GNS3StartNodeTool` | 启动节点 |
| `ExecuteMultipleDeviceConfigCommands` | 下发配置命令 |
| `ExecuteMultipleDeviceCommands` | 执行 show/display 命令 |
| `VPCSMultiCommands` | VPCS 命令 |
| `LinuxTelnetBatchTool` | Linux telnet 批量命令 |
| `GNS3CreateAreaDrawingTool` | 创建拓扑区域绘图 |

每次工具调用后进入 `tool_node` 执行，然后返回 `llm_call` 继续下一步。

**干运行模式**：工具调用被拦截到 `topology_dry_run.py` 进行模拟执行。

---

## 第七步：FortiGate 配置生成与拦截（条件触发）

**仅当 LLM 调用 `execute_multiple_device_config_commands` 且检测到 FortiGate 设备时触发。**

### 7.1 配置拦截

1. 提取配置命令块
2. 渲染人类可读的 CLI 预览

### 7.2 质量审查（干运行模式）

- 向用户展示配置预览
- 用户审查："通过" → 执行确认 / "取消" → 清除 / "反馈" → 修改配置

### 7.3 执行确认

- 提示用户确认执行
- 确认通过 → 工具执行配置下发

---

## 第八步：工具执行配置下发

- **真实模式**：通过 Nornir 框架连接设备，下发 CLI 配置
- **干运行模式**：模拟执行，存入 `simulated_topology.config_previews`

---

## 第九步：响应流式返回 UI

**文件**: `src/gns3_copilot/ui_model/chat.py`

- AIMessage chunk 实时渲染 Markdown
- ToolMessage 显示为可折叠面板
- 状态持久化到 `st.session_state`
- 追踪记录到 Prompt Trace 数据库
- 检测澄清问题 → `st.rerun()` 刷新界面

---

## 完整时序图

```
用户                     chat.py                  LangGraph Agent              LLM                    工具层
 |                         |                          |                        |                       |
 |-- 输入请求 ------------>|                          |                        |                       |
 |                         |-- stream(HumanMsg) ----->|                        |                       |
 |                         |                          |-- llm_call ----------->|                       |
 |                         |                          |   (构建上下文)          |                       |
 |                         |                          |   [条件]FortiGate检测   |                       |
 |                         |                          |                        |                       |
 |                         |                          |-- 拓扑意图检测 ------->|                       |
 |                         |                          |<-- 置信度 >= 0.55 -----|                       |
 |<-- "是否生成prompt?" ---|<-- stream chunk ----------|                        |                       |
 |-- "是" ---------------->|-- stream(HumanMsg) ----->|                        |                       |
 |                         |                          |                        |                       |
 |                         |              === Phase 1: 拓扑概要 ===            |                       |
 |                         |                          |-- skill LLM Phase1 --->|                       |
 |<-- 拓扑概要+确认提示 ---|<-- stream chunk ----------|<-- 概要输出 -----------|                       |
 |-- "确认" / 修改意见 --->|-- stream(HumanMsg) ----->|                        |                       |
 |                         |                          |                        |                       |
 |                         |            === Phase 2: 节点与链路清单 ===         |                       |
 |                         |                          |-- skill LLM Phase2 --->|                       |
 |<-- 节点链路+确认提示 ---|<-- stream chunk ----------|<-- 清单输出 -----------|                       |
 |-- "确认" / 修改意见 --->|-- stream(HumanMsg) ----->|                        |                       |
 |                         |                          |                        |                       |
 |                         |         === Phase 3: 执行步骤+规则+检查清单 ===    |                       |
 |                         |                          |-- skill LLM Phase3 --->|                       |
 |<-- 步骤规则+确认提示 ---|<-- stream chunk ----------|<-- 步骤输出 -----------|                       |
 |-- "确认" / 修改意见 --->|-- stream(HumanMsg) ----->|                        |                       |
 |                         |                          |                        |                       |
 |                         |              === Phase 4: 合并最终 prompt ===      |                       |
 |                         |                          |-- skill LLM Phase4 --->|                       |
 |<-- 完整拓扑 prompt -----|<-- stream chunk ----------|<-- 最终 prompt --------|                       |
 |                         |                          |                        |                       |
 |                         |                   === LLM 执行拓扑 ===             |                       |
 |                         |                          |-- LLM执行拓扑 -------->|                       |
 |                         |                          |                        |-- CreateNode -------->|
 |                         |                          |                        |<-- node created ------|
 |                         |                          |                        |-- CreateLink -------->|
 |                         |                          |                        |<-- link created ------|
 |                         |                          |                        |-- StartNode --------->|
 |                         |                          |                        |<-- node started ------|
 |                         |                          |                        |                       |
 |                         |                          |-- LLM生成配置 -------->|                       |
 |                         |                          |   [条件]配置拦截        |                       |
 |<-- CLI预览+审查提示 ----|<-- stream chunk ----------|                        |                       |
 |-- "通过" ------------->|-- stream(HumanMsg) ----->|                        |                       |
 |<-- 执行确认提示 --------|<-- stream chunk ----------|                        |                       |
 |-- "确认执行" ---------->|-- stream(HumanMsg) ----->|                        |                       |
 |                         |                          |-- tool_node ---------->|-- ConfigCommands ---->|
 |                         |                          |                        |<-- 配置完成 ----------|
 |                         |                          |                        |                       |
 |<-- "配置已成功应用" ----|<-- stream chunk ----------|<-- 总结响应 -----------|                       |
 |                         |                          |                        |                       |
 |                         |-- get_state() ---------->|                        |                       |
 |                         |<-- final state -----------|                        |                       |
 |                         |-- 记录追踪 ------------->|                        |                       |
```

---

## 关键设计特点

1. **渐进式披露**：拓扑生成按 4 阶段逐层输出，用户可在每个阶段确认或修改，避免一次性输出过多信息
2. **通用 + 条件扩展**：编排器 skill 适用于任何拓扑，FortiGate skill 仅在检测到关键词时条件加载
3. **双重确认机制**：FortiGate 配置需经过质量审查 + 执行确认两道关卡
4. **阶段校验与修复**：每阶段输出经过 `validate_phase_output()` 校验，失败自动触发修复
5. **干运行模式**：支持全流程模拟，不实际调用 GNS3 API
6. **全链路追踪**：request_id 贯穿 UI → Agent → LLM → 工具
7. **流式响应**：实时显示 LLM 输出和工具调用过程
8. **状态持久化**：LangGraph SQLite checkpointer 保存对话状态，支持断点续接
9. **按阶段裁剪上下文**：风格参考仅 Phase 1 注入，SKILL 文档按阶段裁剪（Phase 2+ 节省 40-70% token），避免重复传输
10. **port1 管理口规范**：风格参考模板、FortiGate Baseline Rules、FortiGate Skill 三处一致：port1 仅管理用途，业务口从 port2 起
11. **多设备 spec 提取**：`topology_spec_model` 支持 `fortigate_count` 和 `fortigates` 列表，适配多 FortiGate 站点互联场景
