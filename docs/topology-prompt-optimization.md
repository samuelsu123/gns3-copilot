# 拓扑 Prompt 生成流程优化方案

基于 session `4d3b19ef-20ac-40ec-8111-e9d0a23c585a` 的完整交互分析。

## 问题总结

### P0: 风格参考模板 port1 规范冲突

**现象**: `simple_fgt.txt` 中 port1 用于 WAN 业务口（`set device port1`），与 FortiGate Baseline Rules（port1 仅管理用）直接矛盾。LLM 在生成时需要自行"纠正"模板的错误示范。

**影响**: 增加 LLM 出错概率，模板本身就在误导。

### P1: Prompt 重复导致 Token 浪费

**现象**: 每个 Phase 的 `topology_prompt_model_*` 调用中，完整携带：
- Clarification Choice Protocol（~30 行，重复 5+ 次）
- 完整风格参考 `simple_fgt.txt`（~130 行，Phase 2-4 仍全量传入）
- 完整两份 SKILL.md（~140 行，每次全量传入）

**估算**: 风格参考在 Phase 2/3/4 中各多耗费约 1500 token，4 个 Phase 总计多耗约 4500 token。

### P2: 对话历史中已确认内容三重传递

**现象**: 到 Phase 4 时，已确认的阶段输出存在于三个位置：
1. System prompt 中的 `[已确认 - xxx]` 块
2. 对话历史 messages 中（AI 之前输出的原文）
3. `build_phase_confirmation_message` 包裹后又再传一遍

**影响**: Phase 3/4 时上下文膨胀显著。

### P3: topology_spec_model 不支持多设备

**现象**: Schema 只有单个 `fortigate_name` / `fortigate_template` 字段，无法表达"2 台 FortiGate"场景。提取结果为 null 且未被后续 Phase 引用。

### P4: FortiGate VPN 配置缺少 IKE 版本

**现象**: 生成的 `config vpn ipsec phase1-interface` 未显式设置 `set ike-version 2`，但拓扑概要明确写了 IKEv2。FortiGate 默认可能是 IKEv1。

---

## 改动计划

### 改动 1: 修复 simple_fgt.txt — port1 规范对齐 [P0]

**文件**: `src/gns3_copilot/prompts/simple_fgt.txt`

**内容**:
- port1 改为管理口（`set allowaccess ping https ssh http`），不配 IP、不用于默认路由
- WAN 口改为 port2（`set device port2`），业务口从 port3 起
- 默认路由 `set device` 指向 port2

### 改动 2: Phase 2+ 不再重复注入完整风格参考 [P1]

**文件**: `src/gns3_copilot/prompts/native_topology_prompt.py`

**函数**: `build_topology_skill_phase_prompt()`

**逻辑**: 仅在 Phase 1（topology_overview）时注入完整风格参考。Phase 2/3/4 已有 `[已确认 - xxx]` 的前序输出作为上下文，不需要风格参考。

### 改动 3: Phase 2+ 仅注入当前阶段相关的 SKILL 片段 [P1]

**文件**: `src/gns3_copilot/prompts/native_topology_prompt.py`

**函数**: `build_topology_skill_phase_prompt()`

**逻辑**: 不再完整传入两份 SKILL.md，而是按当前 Phase 裁剪：
- Phase 1: 传入完整 SKILL.md（首次生成需要全貌）
- Phase 2: 仅传入 Phase 2 相关片段
- Phase 3: 仅传入 Phase 3 相关片段
- Phase 4: 仅传入 Phase 4 相关片段 + 输出规范

实现方式：在 SKILL.md 中按 `## Phase X` 标题切分，每次只传相关段落。

### 改动 4: 扩展 topology_spec_model schema 支持多 FortiGate [P3]

**文件**: `src/gns3_copilot/agent/gns3_copilot.py`

**函数**: `_build_topology_spec_extraction_prompt()`

**内容**: 将 `fortigate_name` / `fortigate_template` 替换为 `fortigate_count: int` 和 `fortigates: [{name, role, template}]` 列表。

### 改动 5: FortiGate VPN Skill 补充 IKE 版本约束 [P4]

**文件**: `src/gns3_copilot/prompts/skills/fortigate-topology/SKILL.md`

**内容**: 在 Phase 3 的站点互联部分增加：
- `set ike-version 2`（当概要指定 IKEv2 时必须显式设置）

---

## 不做的事

- **base_model Round 2 重复生成**: trace 中看到的 Round 2 `base_model` 实际上是 `_log_llm_interaction(tag="base_model")` 的日志记录，并非真正再次调用 LLM。代码中 `phase_completed` 分支直接构造 `AIMessage` 返回，没有二次 LLM 调用。这是 trace 格式的误导，不是代码问题。
- **对话历史裁剪**: `recent_messages[-10:]` 已做了截断。进一步裁剪需要更复杂的消息摘要机制，当前改动范围外。
