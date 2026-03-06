---
name: fortigate-topology
description: FortiGate 拓扑与配置子技能。用于 FortiGate 相关场景下的节点、接口、路由、策略、VPN 与本地上网分流逻辑生成。
---

# FortiGate Topology Skill

当请求包含 FortiGate / FGT / 防火墙语义时启用本技能。

## 各阶段补充约束

### Phase 1 补充（拓扑概要）

- 识别 FortiGate 数量（例如总部 + 分支 = 2 台）
- 为每台 FortiGate 绑定站点角色与对应内网/WAN
- 当用户未指定 IP 时，自动分配合理默认值：
  - WAN 口：192.168.122.x/24（模拟公网）
  - 内网：10.1.x.0/24、10.2.x.0/24 等
  - VPN 预共享密钥：默认使用 `Fortinet123#`
- 仅当真正高影响歧义（如设备数量不确定）时才澄清

### Phase 2 补充（节点与链路）

- `port1` 仅保留管理用途，不作为业务网关口
- 业务网段从 `port2` 及以上接口承载
- 站点互联场景节点骨架参考：
  - HQ-FGT（总部 FortiGate）、BR-FGT（分支 FortiGate）
  - HQ-SW-Office / HQ-SW-Server / BR-SW-Office（内网交换机）
  - WAN-SW（模拟 WAN 互联的交换机或 Cloud）
  - NAT（提供上网出口）

### Phase 3 补充（执行步骤）

配置完整性要求：
- 必须包含 `config system interface`、`config router static`、`config firewall policy`
- 静态路由需明确远端业务网段走 VPN，默认路由走本地 WAN
  - 路由须包含 `set dst` 和 `set device`

站点互联（当请求提到 IPsec/VPN）：
- 两端均要有完整 Phase1/Phase2 配置：
  - `config vpn ipsec phase1-interface`
  - `config vpn ipsec phase2-interface`
  - `set psksecret`
  - 当拓扑概要指定 IKEv2 时，必须显式设置 `set ike-version 2`（FortiGate 默认可能为 IKEv1）
- 双边内网需可互访的防火墙策略
- "本地上网仍走本地 WAN"必须被保留，不可被全局 VPN 路由覆盖

步骤顺序要求：
- 创建节点 → 创建链路 → 启动 → wait_for_nodes_ready → configure_node → 验证
- 建议先配置接口和路由，再配置 VPN，最后配置策略

### Phase 4 补充（合并输出）

- FortiGate 完整 CLI 配置块必须内联在执行步骤中
- 不输出和执行无关的解释性段落

## 信息不足时的澄清规则

- 优先询问高影响缺失项（对端公网地址、内网网段、IKE 提案等）
- 问题必须使用 `clarify_options`
- 一次只问一个问题
