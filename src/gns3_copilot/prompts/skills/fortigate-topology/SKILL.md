---
name: fortigate-topology
description: FortiGate 拓扑与配置子技能。用于 FortiGate 相关场景下的节点、接口、路由、策略、VPN 与本地上网分流逻辑生成。
---

# FortiGate Topology Skill

当请求包含 FortiGate / FGT / 防火墙语义时启用本技能。

必须遵循以下规则：

1. 设备与角色识别：
   - 识别 FortiGate 数量（例如总部 + 分支 = 2 台）。
   - 为每台 FortiGate 绑定站点角色与对应内网/WAN。
2. 接口与安全约束：
   - `port1` 仅保留管理用途，不作为业务网关口。
   - 业务网段从 `port2` 及以上接口承载。
3. 路由与策略完整性：
   - 必须包含 `config system interface`、`config router static`、`config firewall policy`。
   - 静态路由需明确远端业务网段走 VPN，默认路由走本地 WAN。
4. 站点互联（当请求提到 IPsec/VPN）：
   - 两端均要有 Phase1/Phase2（或等价完整配置）与双向策略。
   - 双边内网需可互访。
   - “本地上网仍走本地WAN”必须被保留，不可被全局 VPN 路由覆盖。
5. 信息不足时只问一个问题：
   - 优先询问高影响缺失项（对端公网地址、内网网段、IKE 提案等）。
   - 问题必须使用 `clarify_options`。

输出约束：

- 若信息已足够，直接输出完整可执行拓扑 prompt（由主技能框架组织章节）。
- 不输出和执行无关的解释性段落。
