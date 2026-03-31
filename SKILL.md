---
name: prometheus
display_name: 📊 Prometheus 监控数据查询与配置管理
description: >
  通用 Prometheus 监控技能。支持通过 PromQL 查询监控数据、调用 Prometheus HTTP API 获取实时/历史指标、
  生成 HTML 交互式监控图表、查看当前活跃告警状态、创建和管理告警规则、配置 Prometheus 抓取规则、
  管理 Alertmanager 静默。当用户需要查询监控数据、生成监控曲线图、分析指标趋势、排查性能问题、
  获取 CPU/内存/磁盘/网络/请求量/错误率/延迟等监控指标、查看告警状态、创建告警规则、
  配置抓取目标、管理服务发现时使用此技能。
  本技能是通用引擎，不内嵌任何业务指标定义。通过标准输入协议接收参数，
  调用方（其他 Skill、Workflow、用户）只需按协议提供参数即可。
version: 3.0.0
tags: [prometheus, monitoring, metrics, alerting, observability, promql, query, grafana, scrape, rules, alertmanager]
keywords: [Prometheus, PromQL, 监控, 指标, 查询, HTTP API, 告警, 告警规则, 抓取配置, 服务发现, Alertmanager, 静默, CPU, 内存, QPS, 错误率, 延迟, Grafana, 时间序列]
examples:
  - 查询某服务的 CPU 使用率
  - 过去 1 小时的 QPS 趋势
  - 帮我写一个查错误率的 PromQL
  - 怎么通过 Prometheus API 获取监控数据
  - 查看当前活跃告警
  - 找出延迟最高的 5 个服务
  - 帮我输出过去 6 小时的 QPS 监控图表
  - 帮我创建一个 CPU 使用率过高的告警规则
  - 生成一套标准告警规则
  - 配置 Prometheus 抓取我的应用服务
  - 创建文件服务发现的目标配置
  - 帮我创建一个 Alertmanager 静默
---

# Prometheus 监控数据查询与配置管理技能

## 概述

本技能是 **通用 Prometheus 查询与配置管理引擎**，重点覆盖：
- 通过 HTTP API 查询实时/历史监控数据（即时查询、范围查询）
- **查看当前活跃告警和规则状态**（`/api/v1/alerts`、`/api/v1/rules`）
- **生成 HTML 交互式监控图表**（`--format chart`，类 Grafana 风格）
- PromQL 查询表达式编写（资源、流量、延迟、容器等场景）
- **告警规则创建与管理**（规则文件生成、预设模板、验证、热加载）
- **Prometheus 抓取规则配置**（静态目标、文件服务发现、Kubernetes/Consul SD、标签重写）
- **Alertmanager 静默管理**（创建/查看/删除静默）
- 查询与配置脚本工具（Python / Shell）

## 边界说明

- 本技能提供 **知识查询、PromQL 编写指导、API 调用示例**
- 可通过 `scripts/prometheus_query.py` 脚本实际执行 Prometheus 查询
- 支持 `--format chart` 将范围查询结果生成自包含 HTML 交互式图表（ECharts CDN，零额外依赖）
- 支持 Basic Auth 认证（`--username`/`--password`），连接返回 401/403 时自动交互式提示用户输入账号密码
- **不内嵌任何业务指标定义**：业务指标（指标名、PromQL 模板、Job 命名规则等）由调用方按标准输入协议提供
- **不内嵌任何业务集群地址**：Prometheus 查询地址由调用方按标准输入协议提供
- **不知道有哪些业务/服务/集群存在**：本技能是纯通用引擎，完全不感知调用方的业务上下文
- 可通过 `scripts/prometheus_config.py` 脚本创建告警规则文件、抓取配置文件、文件服务发现目标
- 支持预设告警规则模板（standard/kubernetes/infrastructure）和抓取配置模板（infrastructure/middleware/blackbox）
- 支持告警规则文件验证、Prometheus 配置文件验证
- 支持 Prometheus 配置热加载（`/-/reload`）
- 支持 Alertmanager 静默管理（创建/查看/删除）
- 不负责 Prometheus 集群的部署、扩缩容或底层存储管理
- 不提供 Grafana Dashboard 的创建/编辑（但可通过 chart 模式生成类似效果的独立图表）

## 标准输入协议

> 本技能通过「标准输入协议」接收查询参数。调用方（其他 Skill、Workflow 上游 Step、用户直接提供）只需按协议提供参数，本技能不关心参数从哪来。

### 协议参数

| 参数 | 必选 | 类型 | 说明 | 示例 |
|------|------|------|------|------|
| `url` | ✅ | string | Prometheus 查询地址（HTTP API 端点） | `http://prometheus:9090` |
| `promql` | ✅ | string | PromQL 查询表达式 | `sum(rate(http_requests_total[5m]))` |
| `mode` | ❌ | string | 查询模式：`instant` / `range`（默认 `range`） | `range` |
| `range` | ❌ | string | 时间范围（默认 `1h`） | `6h`、`1d`、`7d` |
| `start` | ❌ | string | 起始时间（ISO 8601 或相对时间） | `2024-03-26`、`now-2h` |
| `end` | ❌ | string | 结束时间（ISO 8601 或相对时间） | `2024-03-27`、`now` |
| `step` | ❌ | string | 查询步长（默认自动计算） | `60s`、`5m` |
| `format` | ❌ | string | 输出格式：`text` / `chart`（默认 `text`） | `chart` |
| `output` | ❌ | string | 图表输出文件路径 | `/tmp/qps.html` |
| `auth.username` | ❌ | string | Basic Auth 用户名 | `admin` |
| `auth.password` | ❌ | string | Basic Auth 密码 | `secret` |

### 协议使用示例

#### 示例 1：其他 Skill 提供参数（AI 自主协调）

```
调用方（如集群信息 Skill）提供：
  url: http://grafana.example.com/api/datasources/proxy/uid/xxx
  
调用方（如服务监控 Skill）提供：
  promql: sum(rate(http_requests_total{job=~"my-service.*"}[5m]))

→ Prometheus Skill 接收 url + promql，执行查询
```

#### 示例 2：Workflow 编排传入

```yaml
# Workflow 上游 Step 输出：
#   url: ${{ steps.get_cluster.outputs.prometheus_url }}
#   promql: ${{ steps.get_metrics.outputs.promql }}
```

#### 示例 3：用户直接提供

```
用户："帮我查 http://prometheus:9090 上的 up 指标"
→ url = http://prometheus:9090
→ promql = up
```

### 协议验证规则

在执行查询前，**必须验证**以下条件：

1. **`url` 不能为空**：如果调用方未提供 url，向用户询问
2. **`promql` 不能为空**：如果调用方未提供 promql，根据用户意图构建 PromQL
3. **Counter 类型指标必须包裹 `rate()` 或 `increase()`**
4. **`range` 模式下 step 必须合理**：避免返回过多数据点

## 文档分工

### `references/http-api-查询.md`
**HTTP API 查询文档**
- API 端点概览、即时查询、范围查询、时间参数说明、查找时间序列和标签、查看目标和告警状态

### `references/promql-指南.md`
**PromQL 查询语言指南**
- 常用查询模式速查表（资源/流量/延迟/容器）、核心函数、操作符、常见排查场景的 PromQL

### `references/查询脚本工具.md`
**查询脚本工具**
- Shell 脚本快速查询、Python 脚本功能说明、使用示例
- **HTML 图表输出模式**：`--format chart` 参数说明、图表特性、使用示例

### `references/alerting-rules-配置.md`
**告警规则配置文档**
- 告警规则文件语法、关键字段说明、模板变量、告警状态流转
- Prometheus 规则管理 API（查看/重载）
- Alertmanager HTTP API（查看告警/创建静默/管理静默）
- 规则验证工具（promtool）
- 常用告警规则模板（服务可用性/资源使用率/请求与延迟/容器与 Kubernetes）
- 最佳实践（告警分级、for 时间建议、命名规范）

### `references/scrape-config-配置.md`
**抓取规则配置文档**
- 抓取配置文件语法、关键字段说明
- 静态目标配置、多环境配置
- 服务发现机制（文件 SD、Kubernetes SD、Consul SD）
- 标签重写（relabel_configs / metric_relabel_configs）
- 通过 HTTP API 查看抓取状态
- 配置验证工具（promtool）
- 常用抓取配置模板（基础设施/中间件/探针监控）
- 最佳实践（抓取间隔建议、标签规范、安全建议）

## 模板（templates）

`templates/` 目录提供了可直接复制使用的命令模板，覆盖查询和配置场景：

| 模板文件 | 用途 | 典型场景 |
|---------|------|----------|
| `instant-query.md` | 即时查询 | 健康检查、CPU/内存/QPS/错误率的当前值 |
| `range-query-chart.md` | 范围查询 + 图表 | QPS/CPU/内存/错误率/延迟趋势图 |
| `time-range-query.md` | 指定时间范围查询 | 查询某天全天、指定时间段、跨天时段 |
| `alerts-and-targets.md` | 告警与目标状态 | 活跃告警、抓取目标、规则、标签探索 |
| `troubleshooting.md` | 故障排查 | TOP N 排序、突增突降、内存泄漏、磁盘预测 |
| `alerting-rules.md` | 告警规则配置 | 规则文件生成、预设模板、验证、热加载、静默管理 |
| `scrape-config.md` | 抓取规则配置 | 静态目标、文件服务发现、配置验证、热加载 |

> 使用方式：修改模板中的 `PROM_URL` 和参数后直接执行，或参考模板中的命令片段组合使用。

## 使用方式

### Step 1：识别问题类型

优先判断用户问题属于以下哪一类：
- **查询监控数据**：需要获取实时/历史指标值
- **查看告警状态**：需要查看当前活跃告警或规则状态
- **生成监控图表**：需要输出可视化的监控曲线图
- **编写 PromQL**：需要构建查询表达式
- **创建/管理告警规则**：需要生成告警规则文件、使用预设模板、验证规则
- **配置抓取规则**：需要创建抓取配置、文件服务发现目标、管理抓取任务
- **管理 Alertmanager 静默**：需要创建/查看/删除告警静默
- **使用脚本工具**：需要通过脚本批量查询或自动化

### Step 2：验证输入协议（查询/图表类必须执行）

> ⚠️ **关键步骤**：在执行任何监控数据查询或图表生成之前，**必须验证标准输入协议的必选参数已就绪**。不得跳过此步骤直接执行查询。

#### 验证流程

```
检查 url 是否已提供
  ├── ✅ 已提供 → 继续
  └── ❌ 未提供 → 向用户询问 Prometheus 查询地址

检查 promql 是否已提供
  ├── ✅ 已提供 → 继续
  └── ❌ 未提供 → 根据用户意图 + 读取 PromQL 指南构建表达式

验证 promql 语法合理性
  ├── Counter 类型是否包裹 rate()/increase()
  ├── histogram_quantile() 是否保留 le 标签
  └── 是否存在无标签过滤的全量查询
```

#### 向用户确认查询信息

在执行查询前，向用户展示并确认以下信息：

> 📋 **查询信息确认**：
> - **Prometheus 查询 URL**：`{url}`
> - **查询指标/PromQL**：`{promql}`
> - **查询模式**：{mode}（{range}）
> - **输出格式**：{format}
> - **认证**：如需认证，脚本会自动提示输入账号密码
>
> 以上信息是否正确？如需调整请告知。

### Step 3：读取最小必要文档

| 问题类型 | 优先读取文档 |
|---------|--------------|
| 查询监控数据（API 调用） | `references/http-api-查询.md` |
| 查看告警状态 | `references/http-api-查询.md`（查看目标和告警状态章节） |
| 生成监控图表 | `references/查询脚本工具.md`（图表输出模式章节） |
| 编写 PromQL 表达式 | `references/promql-指南.md` |
| 创建/管理告警规则 | `references/alerting-rules-配置.md` |
| 配置抓取规则 | `references/scrape-config-配置.md` |
| 管理 Alertmanager 静默 | `references/alerting-rules-配置.md`（Alertmanager HTTP API 章节） |
| 使用查询脚本 | `references/查询脚本工具.md` |
| 使用配置管理脚本 | `templates/alerting-rules.md` 或 `templates/scrape-config.md` |
| 需要快速命令模板 | `templates/` 目录下对应场景的模板文件 |

> 如果问题跨多个主题，应同时读取多个 reference 文件，但避免一次性读取全部文档。

### Step 4：组织回答

回答时遵循以下原则：
- **先给结论/示例，再给解释**
- 查询类问题优先给出可直接执行的 curl 命令或 PromQL 表达式
- **如果用户需要可视化图表**，优先使用 `--format chart` 生成 HTML 图表
- 标明信息来自哪个文档
- 区分"即时查询"和"范围查询"的适用场景
- 涉及脚本时，说明脚本路径和参数

## ⛔ 严格规则

### PromQL 编写规则

1. **Counter 类型必须用 `rate()` 或 `increase()`**：直接查询 Counter 原始值无意义
2. **`rate()` 的时间窗口不能小于 scrape_interval 的 4 倍**：推荐至少 `[5m]`
3. **`histogram_quantile()` 必须保留 `le` 标签**：聚合时用 `sum by (le)` 而非 `sum`

### 查询安全规则

1. **范围查询必须设置合理的 step**：避免返回过多数据点导致 OOM
2. **避免无标签过滤的全量查询**：如 `http_requests_total` 不加任何 label selector
3. **高基数指标谨慎查询**：先用 `count()` 确认序列数量

### 回答规范

1. **给出的 PromQL 必须语法正确**：不确定时先在 `promtool` 中验证
2. **curl 示例必须包含完整参数**：包括 `--data-urlencode` 处理特殊字符
3. **时间范围建议必须匹配 step**：参考时间参数说明表

## 输出规范

### 查询类问题

建议输出：
- 可直接执行的 curl 命令或 PromQL 表达式
- 预期返回格式说明
- 如需范围查询，给出推荐的 time range 和 step

### 图表输出问题

建议输出：
- 完整的 `python3 scripts/prometheus_query.py --format chart` 命令
- 说明图表文件路径和打开方式

### PromQL 编写问题

建议输出：
- 完整的 PromQL 表达式
- 表达式各部分的含义解释
- 适用的查询模式（即时/范围）
- 可能的变体（如按不同维度聚合）

### 告警规则配置问题

建议输出：
- 完整的 `python3 scripts/prometheus_config.py --action create-alert-rule` 命令
- 或直接给出告警规则 YAML 内容
- 说明 severity 分级、for 时间建议
- 如使用预设模板，说明模板包含的规则列表

### 抓取配置问题

建议输出：
- 完整的 `python3 scripts/prometheus_config.py --action create-scrape-config` 命令
- 或直接给出 scrape_config YAML 内容
- 说明抓取间隔建议、标签规范
- 如涉及服务发现，说明 SD 机制和 relabel 规则

### Alertmanager 静默管理问题

建议输出：
- 完整的 `python3 scripts/prometheus_config.py --action create-silence` 命令
- 或直接给出 curl 命令
- 说明静默的匹配条件和持续时间

## 异常处理

- **Prometheus 需要认证**：脚本支持 `--username`/`--password` 参数进行 Basic Auth 认证；若未提供认证信息且服务端返回 401/403，脚本会自动交互式提示用户输入账号和密码
- **`url` 未提供**：向用户询问 Prometheus 查询地址；提示用户可从集群信息类 Skill 或运维文档中获取
- **`promql` 未提供**：根据用户描述的查询意图，结合 `references/promql-指南.md` 构建 PromQL 表达式
- **指标名不确定**：建议先用 `/api/v1/label/__name__/values` 或 `/api/v1/metadata` 查找
- **查询超时或 OOM**：建议缩小时间范围、增大 step、添加标签过滤
- **reference 未覆盖**：明确说明超出本技能范围，建议查看 Prometheus 官方文档
