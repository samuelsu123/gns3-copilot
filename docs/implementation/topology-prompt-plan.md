## jzs_test：将拓扑设计请求改为输出“原生 gns3-copilot 可执行 prompt”

### 摘要
- 目标：在 `jzs_test` 中实现“用户在 `chat.py` 输入自然语言拓扑需求时，返回完整的原生 gns3-copilot 可执行拓扑描述”，格式对齐 `prompts/simple_fgt.txt` 风格。
- 范围：仅对“拓扑设计类请求”触发新行为；排障/普通问答保持现有流程。
- 生成方式：动态填充固定结构模板（不是固定文案直出，不是自由散文输出）。
- 分支约束：只改 `jzs_test`，不改 `master`。
- 意图触发策略：由 LLM 识别意图，并先询问用户是否需要生成完整 prompt。

### 公开接口/类型变更
- 不引入外部 API 变更；仅新增内部函数与路由分支。
- 新增内部能力（函数级）：
  - LLM 意图识别函数：`detect_topology_prompt_intent_via_llm(...) -> bool`
  - 生成确认提问函数：`build_topology_prompt_confirmation_message(...) -> str`
  - 原生拓扑 prompt 生成函数：`generate_native_topology_prompt(...) -> str`
  - 输出结构校验函数：`is_native_topology_prompt_format(text: str) -> bool`
- `MessagesState` 增加一组待确认字段（或复用同类模式）以支持“是否生成完整 prompt”的交互状态管理：
  - 例如：`pending_topology_prompt_request: dict | None`
  - 例如：`pending_topology_prompt_context: dict | None`

### 实施步骤
1. 新增一个专用 prompt 模块（建议放在 `src/gns3_copilot/prompts/`），负责加载 `simple_fgt.txt` 示例、构造“原生 gns3-copilot 拓扑描述生成”系统提示词，并定义输出必备章节（节点清单、链路清单、执行步骤、执行规则、完成检查清单）。
2. 新增 LLM 意图识别流程（替代关键词匹配）：
   - 输入用户最新消息与必要上下文；
   - 输出结构化判定（`is_topology_design_intent: true/false`）；
   - 不直接生成最终 prompt，仅用于是否进入确认提问环节。
3. 在 `src/gns3_copilot/agent/gns3_copilot.py` 的 `llm_call` 中加入“确认提问分支”，位置放在工具调用与 RAG/FortiGate gate 之前：
   - 若 LLM 判定为拓扑设计意图，先返回提问：是否生成完整可执行 prompt。
   - 将该请求上下文保存到 `pending_topology_prompt_*` 状态。
4. 处理用户确认回复：
   - 用户确认“是”时，调用 `create_base_model`（不绑定工具）生成结构化 prompt 并返回；
   - 用户确认“否”时，清理 `pending_topology_prompt_*`，回到常规代理流程；
   - 非明确“是/否”时，继续提示用户二选一确认。
5. 新分支返回时清理 `pending_fortigate_config_call/pending_fortigate_quality_call` 与 `pending_topology_prompt_*`，避免旧会话遗留状态干扰；同时不触发工具调用，确保 `chat.py` 最终呈现就是可复制的 prompt 文本。
6. 对生成结果做结构校验；若缺失关键章节，执行一次“同轮重写”纠正（仍不绑定工具），保证输出稳定为可执行描述格式。
7. 保留原有非拓扑请求链路不变（RAG、FortiGate gate、dry-run、工具执行等逻辑继续工作）。
8. 将 `src/gns3_copilot/prompts/simple_fgt.txt` 纳入可追踪资源并确保运行时可读取；如需安装包兼容，在 `pyproject.toml` 的 package-data 中补充 prompts 文本资源。

### 测试用例与验收场景
1. 新增 `tests/agent/test_gns3_copilot_topology_intent_confirm.py`：
   - LLM 判定为拓扑设计时，先返回确认提问；
   - 用户确认“是”后进入 prompt 生成分支；
   - 用户确认“否”后回到常规流程；
   - 模糊回复时维持确认状态。
2. 新增 `tests/agent/test_gns3_copilot_topology_prompt_mode.py`：
   - 确认“是”后，`llm_call` 走“无工具模型”分支；
   - 返回 `AIMessage` 无 `tool_calls`；
   - 返回文本包含固定章节标题；
   - `create_base_model_with_tools` 不应被调用。
3. 新增 `tests/prompts/test_native_topology_prompt.py`：
   - 输出格式校验函数正例/反例；
   - 示例模板加载与缺失时的兜底行为。
4. 调整 `tests/agent/test_gns3_copilot_fortigate_gate.py`：
   - 显式让测试输入落在“非拓扑设计确认流程”语义，确保该文件继续只验证 FortiGate gate 本身。
5. 保持 `tests/agent/test_gns3_copilot_rag_gate.py` 预期不变并回归通过。
6. 手工验收（chat 页面）：
   - 输入示例“我想用一台 FortiGate 搭一个有两个内网和一个外网的小网络...”时，先收到确认提问；
   - 用户确认后，得到完整可复制 prompt；
   - 输入排障类句子（如“FortiGate 策略为什么不通”）不进入确认提问或生成分支；
   - 不出现工具调用中间输出，最终文本可直接用于原生 `master` 流程。

### 假设与默认值
- 默认按用户输入语言输出（中文输入输出中文）。
- 默认不新增 UI 开关，行为由 LLM 意图识别 + 用户确认自动触发。
- 默认“拓扑设计类请求”才会进入确认提问与生成分支（最终以你锁定范围为准）。
- `master` 仅作为参考，不改动其代码；所有改动在 `jzs_test` 完成。
