# Fortinet AIOps 测试数据生成平台 - 项目计划

## 概述

本项目旨在构建一个通用的 AIOps 测试数据生成平台，专注于 Fortinet 网络拓扑的各种测试场景。FortiGate 配置生成只是其中一个应用场景，平台可扩展支持多种测试数据类型。

---

## 项目架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fortinet AIOps 测试数据生成平台                │
├─────────────────────────────────────────────────────────────────┤
│                         用户交互层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  自然语言    │  │  模板选择   │  │  参数配置   │              │
│  │  描述需求    │  │  快速生成   │  │  精细调整   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                      LangGraph Agent 层                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  状态管理 → LLM决策 → 工具调用 → 结果验证 → 用户确认        ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│                        工具层 (Tools)                            │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ 拓扑生成  │ │ 配置生成  │ │ 流量生成  │ │ 日志生成  │       │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │ 策略生成  │ │ 威胁模拟  │ │ 性能数据  │ │ 合规检查  │       │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │
├─────────────────────────────────────────────────────────────────┤
│                        目标系统层                                │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │
│  │   GNS3    │ │ FortiGate │ │ FortiMgr  │ │ FortiAna  │       │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 测试数据类型分类

### 1. 网络拓扑数据

| 数据类型 | 描述 | 应用场景 |
|---------|------|---------|
| 基础拓扑 | PC、路由器、交换机组合 | 功能测试 |
| 安全拓扑 | FortiGate + 内网/外网分区 | 安全策略测试 |
| 高可用拓扑 | HA 集群、VRRP 配置 | 故障切换测试 |
| SD-WAN 拓扑 | 多链路、策略路由 | SD-WAN 功能测试 |
| 分支机构拓扑 | Hub-Spoke、Full-Mesh | 企业网络测试 |

### 2. 设备配置数据

| 数据类型 | 描述 | 应用场景 |
|---------|------|---------|
| 防火墙策略 | 访问控制规则 | 策略审计测试 |
| VPN 配置 | IPSec、SSL VPN | VPN 功能测试 |
| 路由配置 | 静态路由、OSPF、BGP | 路由协议测试 |
| NAT 配置 | SNAT、DNAT、VIP | NAT 功能测试 |
| 用户认证 | LDAP、RADIUS、本地用户 | 认证测试 |

### 3. 流量与日志数据

| 数据类型 | 描述 | 应用场景 |
|---------|------|---------|
| 正常流量日志 | HTTP、HTTPS、DNS 等 | 基线建立 |
| 攻击流量日志 | DDoS、扫描、入侵 | 威胁检测测试 |
| 应用识别日志 | 应用分类、带宽统计 | 应用控制测试 |
| VPN 日志 | 隧道建立、断开事件 | VPN 监控测试 |
| 系统事件日志 | 配置变更、登录事件 | 审计测试 |

### 4. 性能与监控数据

| 数据类型 | 描述 | 应用场景 |
|---------|------|---------|
| CPU/内存指标 | 资源使用率时序数据 | 容量规划测试 |
| 会话统计 | 并发会话、新建会话 | 性能压测 |
| 接口流量 | 带宽利用率、丢包率 | 网络监控测试 |
| 延迟抖动 | 链路质量指标 | SD-WAN 测试 |

---

## 详细开发计划

### 阶段一：核心框架搭建（2周）

#### 1.1 基础工具类设计

```python
from abc import ABC, abstractmethod
from langchain.tools import BaseTool
from typing import Any

class FortinetTestDataTool(BaseTool, ABC):
    """Fortinet 测试数据生成工具基类"""
    
    # 工具分类
    category: str = "general"
    
    # 支持的输出格式
    output_formats: list[str] = ["json", "cli", "api"]
    
    @abstractmethod
    def generate(self, params: dict) -> dict:
        """生成测试数据"""
        pass
    
    @abstractmethod
    def validate(self, data: dict) -> bool:
        """验证生成的数据"""
        pass
    
    @abstractmethod
    def export(self, data: dict, format: str) -> str:
        """导出指定格式"""
        pass
```

#### 1.2 状态管理扩展

```python
from typing import TypedDict, Annotated
import operator

class AIOpsTestDataState(TypedDict):
    """AIOps 测试数据生成状态"""
    
    messages: Annotated[list, operator.add]
    
    # 当前任务类型
    task_type: str  # topology, config, traffic, log, performance
    
    # 目标设备/系统
    target_system: str  # gns3, fortigate, fortimanager, fortianalyzer
    
    # 生成参数
    generation_params: dict
    
    # 生成的数据
    generated_data: list[dict]
    
    # 验证结果
    validation_results: list[dict]
    
    # 用户确认状态
    user_confirmed: bool
    
    # 导出格式
    export_format: str
```

#### 1.3 任务路由器

```python
def route_task(state: AIOpsTestDataState) -> str:
    """根据任务类型路由到对应处理节点"""
    
    task_type = state.get("task_type")
    
    routing_map = {
        "topology": "topology_generator",
        "config": "config_generator", 
        "traffic": "traffic_generator",
        "log": "log_generator",
        "performance": "performance_generator",
    }
    
    return routing_map.get(task_type, "general_generator")
```

---

### 阶段二：拓扑生成工具（2周）

#### 2.1 拓扑模板库

```python
TOPOLOGY_TEMPLATES = {
    "basic_security": {
        "description": "基础安全拓扑：FortiGate + 内网PC + 外网服务器",
        "nodes": [
            {"type": "fortigate", "count": 1, "role": "firewall"},
            {"type": "pc", "count": 2, "role": "internal"},
            {"type": "server", "count": 1, "role": "external"},
        ],
        "zones": ["trust", "untrust", "dmz"],
    },
    
    "ha_cluster": {
        "description": "高可用集群：FortiGate HA + 核心交换机",
        "nodes": [
            {"type": "fortigate", "count": 2, "role": "ha_pair"},
            {"type": "switch", "count": 2, "role": "core"},
            {"type": "pc", "count": 4, "role": "client"},
        ],
        "ha_mode": "active-passive",
    },
    
    "sdwan_branch": {
        "description": "SD-WAN 分支：双链路 + 策略路由",
        "nodes": [
            {"type": "fortigate", "count": 1, "role": "sdwan_edge"},
            {"type": "router", "count": 2, "role": "wan_link"},
            {"type": "pc", "count": 3, "role": "branch_user"},
        ],
        "wan_links": ["mpls", "internet"],
    },
}
```

#### 2.2 拓扑生成工具

```python
class TopologyGeneratorTool(FortinetTestDataTool):
    """网络拓扑生成工具"""
    
    name: str = "generate_topology"
    description: str = """
    生成 Fortinet 网络拓扑测试数据。
    
    支持的拓扑类型：
    - basic_security: 基础安全拓扑
    - ha_cluster: 高可用集群
    - sdwan_branch: SD-WAN 分支
    - custom: 自定义拓扑
    
    输入参数：
    - template: 模板名称或 "custom"
    - scale: 规模参数（节点数量倍数）
    - customization: 自定义参数
    """
    
    category: str = "topology"
    
    def generate(self, params: dict) -> dict:
        template = params.get("template", "basic_security")
        scale = params.get("scale", 1)
        
        if template in TOPOLOGY_TEMPLATES:
            base = TOPOLOGY_TEMPLATES[template]
            return self._scale_topology(base, scale)
        else:
            return self._generate_custom(params)
```

---

### 阶段三：配置生成工具（3周）

#### 3.1 FortiGate 配置生成器

```python
class FortiGateConfigGeneratorTool(FortinetTestDataTool):
    """FortiGate 配置生成工具"""
    
    name: str = "generate_fortigate_config"
    description: str = """
    生成 FortiGate 设备配置。
    
    支持的配置类型：
    - firewall_policy: 防火墙策略
    - vpn_ipsec: IPSec VPN
    - vpn_ssl: SSL VPN
    - routing: 路由配置
    - nat: NAT 配置
    - user_auth: 用户认证
    - sdwan: SD-WAN 配置
    """
    
    category: str = "config"
    
    CONFIG_GENERATORS = {
        "firewall_policy": "_generate_firewall_policy",
        "vpn_ipsec": "_generate_ipsec_vpn",
        "vpn_ssl": "_generate_ssl_vpn",
        "routing": "_generate_routing",
        "nat": "_generate_nat",
        "user_auth": "_generate_user_auth",
        "sdwan": "_generate_sdwan",
    }
    
    def _generate_firewall_policy(self, params: dict) -> dict:
        """生成防火墙策略配置"""
        policy_count = params.get("count", 10)
        
        policies = []
        for i in range(policy_count):
            policy = {
                "policyid": i + 1,
                "name": f"policy_{i+1}",
                "srcintf": params.get("srcintf", "port1"),
                "dstintf": params.get("dstintf", "port2"),
                "srcaddr": f"subnet_{i+1}",
                "dstaddr": "all",
                "action": "accept",
                "schedule": "always",
                "service": self._random_service(),
                "logtraffic": "all",
            }
            policies.append(policy)
        
        return {"firewall_policy": policies}
```

#### 3.2 配置模板引擎

```python
from jinja2 import Template

class ConfigTemplateEngine:
    """配置模板引擎"""
    
    TEMPLATES = {
        "firewall_policy_cli": """
config firewall policy
{% for policy in policies %}
    edit {{ policy.policyid }}
        set name "{{ policy.name }}"
        set srcintf "{{ policy.srcintf }}"
        set dstintf "{{ policy.dstintf }}"
        set srcaddr "{{ policy.srcaddr }}"
        set dstaddr "{{ policy.dstaddr }}"
        set action {{ policy.action }}
        set schedule "{{ policy.schedule }}"
        set service "{{ policy.service }}"
        set logtraffic {{ policy.logtraffic }}
    next
{% endfor %}
end
""",
        
        "ipsec_vpn_cli": """
config vpn ipsec phase1-interface
    edit "{{ vpn.name }}"
        set interface "{{ vpn.interface }}"
        set peertype any
        set proposal aes256-sha256
        set remote-gw {{ vpn.remote_gw }}
        set psksecret {{ vpn.psk }}
    next
end
""",
    }
    
    def render(self, template_name: str, data: dict) -> str:
        template = Template(self.TEMPLATES[template_name])
        return template.render(**data)
```

---

### 阶段四：流量与日志生成工具（2周）

#### 4.1 流量日志生成器

```python
class TrafficLogGeneratorTool(FortinetTestDataTool):
    """流量日志生成工具"""
    
    name: str = "generate_traffic_logs"
    description: str = """
    生成 FortiGate 流量日志数据。
    
    支持的日志类型：
    - traffic: 流量日志
    - utm: UTM 安全日志
    - event: 系统事件日志
    - attack: 攻击日志
    
    参数：
    - log_type: 日志类型
    - count: 日志条数
    - time_range: 时间范围
    - traffic_profile: 流量特征配置
    """
    
    category: str = "log"
    
    def _generate_traffic_log(self, params: dict) -> list[dict]:
        """生成流量日志"""
        count = params.get("count", 1000)
        
        logs = []
        for i in range(count):
            log = {
                "date": self._random_date(params.get("time_range")),
                "time": self._random_time(),
                "logid": f"0000000{i:06d}",
                "type": "traffic",
                "subtype": "forward",
                "srcip": self._random_ip("internal"),
                "dstip": self._random_ip("external"),
                "srcport": self._random_port(),
                "dstport": self._random_port("service"),
                "proto": self._random_protocol(),
                "action": "accept",
                "policyid": random.randint(1, 100),
                "sentbyte": random.randint(100, 1000000),
                "rcvdbyte": random.randint(100, 1000000),
                "duration": random.randint(1, 3600),
            }
            logs.append(log)
        
        return logs
```

#### 4.2 攻击流量模拟器

```python
class AttackSimulatorTool(FortinetTestDataTool):
    """攻击流量模拟工具"""
    
    name: str = "simulate_attack_traffic"
    description: str = """
    模拟各类网络攻击流量日志。
    
    支持的攻击类型：
    - ddos: DDoS 攻击
    - port_scan: 端口扫描
    - brute_force: 暴力破解
    - sql_injection: SQL 注入
    - xss: 跨站脚本
    - malware: 恶意软件
    """
    
    category: str = "security"
    
    ATTACK_PATTERNS = {
        "ddos": {
            "signature": "DDoS.Attack",
            "severity": "critical",
            "action": "dropped",
        },
        "port_scan": {
            "signature": "Port.Scan",
            "severity": "high",
            "action": "detected",
        },
        "brute_force": {
            "signature": "Brute.Force.Login",
            "severity": "high",
            "action": "blocked",
        },
    }
```

---

### 阶段五：性能数据生成工具（1周）

#### 5.1 性能指标生成器

```python
class PerformanceDataGeneratorTool(FortinetTestDataTool):
    """性能数据生成工具"""
    
    name: str = "generate_performance_data"
    description: str = """
    生成设备性能监控数据。
    
    支持的指标类型：
    - cpu: CPU 使用率
    - memory: 内存使用率
    - session: 会话统计
    - throughput: 吞吐量
    - latency: 延迟数据
    """
    
    category: str = "performance"
    
    def _generate_time_series(self, params: dict) -> list[dict]:
        """生成时序数据"""
        duration_hours = params.get("duration_hours", 24)
        interval_minutes = params.get("interval_minutes", 5)
        
        data_points = []
        current_time = datetime.now() - timedelta(hours=duration_hours)
        
        while current_time < datetime.now():
            point = {
                "timestamp": current_time.isoformat(),
                "cpu_usage": self._generate_cpu_pattern(current_time),
                "memory_usage": self._generate_memory_pattern(current_time),
                "active_sessions": self._generate_session_pattern(current_time),
                "throughput_mbps": self._generate_throughput_pattern(current_time),
            }
            data_points.append(point)
            current_time += timedelta(minutes=interval_minutes)
        
        return data_points
```

---

### 阶段六：集成与验证（2周）

#### 6.1 完整 Agent 图构建

```python
from langgraph.graph import StateGraph, START, END

def build_aiops_testdata_agent():
    """构建 AIOps 测试数据生成 Agent"""
    
    # 定义所有工具
    tools = [
        TopologyGeneratorTool(),
        FortiGateConfigGeneratorTool(),
        TrafficLogGeneratorTool(),
        AttackSimulatorTool(),
        PerformanceDataGeneratorTool(),
    ]
    
    # 构建图
    builder = StateGraph(AIOpsTestDataState)
    
    # 添加节点
    builder.add_node("task_analyzer", analyze_task)
    builder.add_node("topology_generator", generate_topology)
    builder.add_node("config_generator", generate_config)
    builder.add_node("traffic_generator", generate_traffic)
    builder.add_node("log_generator", generate_logs)
    builder.add_node("performance_generator", generate_performance)
    builder.add_node("validator", validate_data)
    builder.add_node("user_confirmation", get_user_confirmation)
    builder.add_node("exporter", export_data)
    
    # 添加边
    builder.add_edge(START, "task_analyzer")
    builder.add_conditional_edges(
        "task_analyzer",
        route_task,
        {
            "topology": "topology_generator",
            "config": "config_generator",
            "traffic": "traffic_generator",
            "log": "log_generator",
            "performance": "performance_generator",
        }
    )
    
    # 所有生成器都连接到验证器
    for generator in ["topology_generator", "config_generator", 
                      "traffic_generator", "log_generator", 
                      "performance_generator"]:
        builder.add_edge(generator, "validator")
    
    builder.add_edge("validator", "user_confirmation")
    builder.add_conditional_edges(
        "user_confirmation",
        lambda s: "exporter" if s["user_confirmed"] else END,
    )
    builder.add_edge("exporter", END)
    
    return builder.compile()
```

#### 6.2 使用示例

```python
# 示例 1：生成安全测试拓扑
result = agent.invoke({
    "messages": [HumanMessage(content="生成一个包含2个FortiGate HA集群和10个客户端的测试拓扑")],
    "task_type": "topology",
    "target_system": "gns3",
})

# 示例 2：生成防火墙策略配置
result = agent.invoke({
    "messages": [HumanMessage(content="为DMZ区域生成50条防火墙策略，包含Web服务和数据库访问规则")],
    "task_type": "config",
    "target_system": "fortigate",
})

# 示例 3：生成攻击流量日志
result = agent.invoke({
    "messages": [HumanMessage(content="模拟一次DDoS攻击，生成10000条攻击日志")],
    "task_type": "log",
    "target_system": "fortianalyzer",
})

# 示例 4：生成性能基线数据
result = agent.invoke({
    "messages": [HumanMessage(content="生成过去7天的设备性能数据，模拟正常业务负载")],
    "task_type": "performance",
    "target_system": "fortimanager",
})
```

---

## 项目时间线

| 阶段 | 内容 | 时间 | 交付物 |
|-----|------|-----|--------|
| 阶段一 | 核心框架搭建 | 第1-2周 | 基础工具类、状态管理、路由器 |
| 阶段二 | 拓扑生成工具 | 第3-4周 | 拓扑模板库、生成器 |
| 阶段三 | 配置生成工具 | 第5-7周 | 配置生成器、模板引擎 |
| 阶段四 | 流量日志工具 | 第8-9周 | 日志生成器、攻击模拟器 |
| 阶段五 | 性能数据工具 | 第10周 | 性能数据生成器 |
| 阶段六 | 集成与验证 | 第11-12周 | 完整 Agent、测试用例 |

---

## 扩展方向

### 1. 更多 Fortinet 产品支持

- **FortiManager**: 集中管理配置模板
- **FortiAnalyzer**: 日志分析场景数据
- **FortiSwitch**: 交换机配置数据
- **FortiAP**: 无线配置数据

### 2. 高级功能

- **数据关联**: 拓扑、配置、日志数据自动关联
- **场景编排**: 多步骤测试场景自动生成
- **数据变异**: 基于基线数据生成异常数据
- **合规检查**: 生成合规审计测试数据

### 3. 集成能力

- **CI/CD 集成**: 自动化测试数据生成
- **API 接口**: RESTful API 供外部系统调用
- **数据导出**: 支持多种格式（JSON、CSV、Syslog）

---

## 总结

本项目计划将 FortiGate 配置生成扩展为一个完整的 Fortinet AIOps 测试数据生成平台，涵盖：

1. **拓扑数据** - 各种网络架构的测试拓扑
2. **配置数据** - 防火墙、VPN、路由等配置
3. **流量日志** - 正常流量和攻击流量日志
4. **性能数据** - 设备监控指标时序数据

通过 LangGraph Agent 架构，用户可以用自然语言描述需求，系统自动选择合适的工具生成测试数据，并支持用户确认和多种格式导出。
