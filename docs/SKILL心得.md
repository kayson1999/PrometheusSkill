> 在 AIBox 这套 Agent Skill 管理与工作流编排框架下，可以将各类能力拆分为独立的 Skill，通过 Workflow 串联完成运维排障、监控查询等任务编排。本文总结 Skill 的写法原则与优化方式，并以 Prometheus 监控查询 Skill 为例，展示工具能力类 Skill 的设计思路和三种使用方式的实践样例。

**这篇文章聊什么？**

🔗 **执行链路**——Skill 在 Agent 摘要→路由→加载→执行四阶段中分别扮演什么角色

📐 **优化原则**——agentskills.io 提出的 Description 召回、渐进式披露、结构化 SOP 等核心建议

📝 **写法原则**——结合项目实践归纳的 8 条 Skill 编写原则

🔀 **两种类型**——服务运维类与工具能力类 Skill 各自的写法侧重和共同框架

📋 **Skill 模板**——一份可直接复用的 Skill 结构模板

🛠️ **项目实践**——以 `prometheus`（工具能力类）为例，展示原则的落地写法和三种使用方式的实践样例。

🔗 **跨 Skill 协作**——展示工具类 Skill 如何通过标准输入协议与业务 Skill 解耦，实现指标定义下沉和关注点分离。

---

## 一、Skill 在 Agent 执行链路中的角色

Agent 在接收用户问题后，并不会一次性读取所有 Skill 全文。实际流程是：

1. **摘要阶段**：提取每个 Skill 的 `name` 和 `description`，组装成 `<skills>` 摘要注入 system prompt
2. **路由阶段**：Agent 根据摘要中的 description 判断应该激活哪个 Skill
3. **加载阶段**：读取被选中 Skill 的完整 `SKILL.md` 内容
4. **执行阶段**：Agent 按 Skill 中定义的流程、规则、约束组织回答

这意味着：

- **description 是路由入口**，决定 Agent 是否能选对 Skill
- **Skill 正文是执行规范**，决定 Agent 回答的质量和稳定性
- 两者写得好不好，直接影响首跳命中率、上下文效率和工作流收敛性

---

## 二、agentskills.io 的优化原则

[agentskills.io/skill-creation/optimizing-descriptions](https://agentskills.io/skill-creation/optimizing-descriptions) 提出了几条核心建议：

### 2.1 Description 是召回入口，不是产品简介

Description 的目标不是"让人看懂这个 Skill 是什么"，而是"让 Agent 在面对用户问题时能准确命中"。因此需要：

- 包含**用户会使用的关键词和短语**
- 覆盖**典型问题场景**，而不只是功能描述
- 明确**边界**——什么问题不该由这个 Skill 处理

### 2.2 渐进式披露（Progressive Disclosure）

不要在一个 Skill 里堆砌所有信息。正确做法是分层：

- **第一层**：description 负责路由命中
- **第二层**：Skill 正文给出结构化的使用流程
- **第三层**：reference 文档提供细节知识

Agent 按需逐层深入，而不是一次性消化全量内容。

### 2.3 结构化优于自然语言叙述

Skill 正文应该像一份可执行的 SOP，而不是一篇说明文。包含：

- 明确的激活条件
- 分类路由表
- 步骤化的使用流程
- 严格规则和负约束
- 异常处理策略

---

## 三、Skill 写法原则

结合 agentskills.io 的建议和本项目实践，归纳为以下原则：

### 原则 1：Description 写召回，不写百科

```
❌ "Prometheus 是一个开源的监控和告警工具包..."
✅ "支持通过 PromQL 查询监控数据、生成 HTML 交互式监控图表、查看当前活跃告警状态"
```

Description 中应包含：模块名/工具名、别名、典型操作或故障现象、关键技术术语、用户常用问法。

### 原则 2：总入口负责路由，服务 Skill 负责执行

总入口 Skill 提供架构图和路由表，不承担具体排障。服务 Skill 提供精确的链路分析、错误码查找和排障步骤。

### 原则 3：文档分层，按需读取

将 reference 文档按职责拆分（总览 / 协议 / 流程 / 排障），在 Skill 中用路由表指导 Agent 只读取最小必要文档。

### 原则 4：写清边界

明确声明"不处理什么"，防止 Agent 在多 Skill 环境中串台。工具类 Skill 还应声明与业务 Skill 的协作关系。

### 原则 5：负约束比正向知识更重要

"禁止跨链路猜测""链路内未找到要明确说明""不进入伪精确诊断""Counter 必须用 rate()"——这类规则对稳定性的提升往往大于增加更多背景知识。

### 原则 6：把操作顺序固化为规则

"先确认链路 → 再分组件 → 再查错误码"或"先确认地址 → 再构造查询 → 再执行"，这种顺序不应该依赖 Agent 自己推理，而应该写进 Skill 作为强制执行的步骤。

### 原则 7：定义缺信息时的行为

明确列出前置信息清单，规定信息不足时只做分类、不做诊断，并告诉用户最需要补充哪一项。

### 原则 8：为 Workflow 设计，不只为聊天设计

每个 Skill 的输入判断、读取策略、输出结构、异常处理都应该足够明确，使其可以被 workflow 的步骤直接消费。

---

## 四、两种类型 Skill 的写法要点

Skill 按定位可以分为两种类型：**服务运维类**和**工具能力类**。前者围绕"一个服务的知识体系"组织，后者围绕"一种操作能力的使用流程"组织。两者遵循相同的结构框架，但填充内容的侧重点不同。

### 4.1 服务运维类

- **description 以领域术语和故障现象为主**：模块名、子系统名、错误码、典型故障表现
- **文档按知识域拆分**：协议 / 流程 / 排障各一份 reference，Agent 按问题类型路由
- **严格规则侧重防止知识幻觉**：禁止跨链路猜测、链路内未找到要明确说明
- **前置确认围绕业务信息**：业务名、应用 ID、环境、错误码等
- **跨 Skill 协作沿请求链路展开**：引用上下游模块的 Skill

### 4.2 工具能力类

- **description 以操作动词和指标类型为主**：查询、生成、分析 + CPU/QPS/错误率
- **文档按操作类型拆分**：API 调用 / PromQL 编写 / 脚本工具各一份 reference
- **引入预置模板**：Agent 从模板出发做参数替换，降低生成错误命令的概率
- **严格规则侧重防止操作风险**：Counter 必须用 rate()、禁止无过滤全量查询
- **前置确认围绕执行环境**：查询地址、数据源、认证方式
- **跨 Skill 协作通过能力互补**：引用业务 Skill 获取地址和集群信息

### 4.3 共同的结构框架

```
description → 边界 → 文档分工 → 使用步骤 → 严格规则 → 异常处理
```

框架是通用的，但填充内容必须贴合 Skill 的类型特征。服务运维类围绕"知识体系"组织，重点是让 Agent 找到正确的知识、给出准确的判断；工具能力类围绕"操作流程"组织，重点是让 Agent 执行正确的操作、避免危险的命令。

---

## 五、推荐的 Skill 模板

```markdown
---
name: xxx
display_name: 📦 模块显示名
description: >
  模块名 + 别名 + 子系统 + 典型故障现象 + 关键术语 + 触发条件描述
version: 1.x.x
tags: [ops, module-name, monitoring, troubleshooting]
keywords: [模块别名, 子系统名, 错误码, 常见现象, 技术术语]
examples:
  - 用户会怎么问 1
  - 用户会怎么问 2
  - 用户会怎么问 3
---

# 模块运维技能

## 激活
说明什么时候应该用这个 Skill，重点覆盖哪些问题域。

## 边界
说明不处理什么，避免与其他 Skill 串台。

## 文档分工
列出 references 的用途分工，每份文档负责什么。

## 使用方式
### Step 1：识别问题类型
### Step 2：读取最小必要文档（问题类型 → reference 路由表）
### Step 3：组织回答（先结论后依据，标明来源，区分事实与建议）

## ⛔ 严格规则
## 缺信息时如何处理
## 回答规范
## 异常处理
```

---

## 六、工具能力类示例：`prometheus`

`prometheus` 是一个**跨模块的通用查询引擎**，属于典型的工具能力类 Skill。与服务运维类 Skill 围绕"一个服务的知识体系"组织不同，工具能力类 Skill 围绕"一种操作能力的使用流程"组织。

prometheus 的设计理念是：**纯通用查询引擎 + 标准输入协议**。业务指标定义和集群地址由调用方维护，prometheus 只负责"接收参数 → 执行查询 → 输出结果"。

### 6.1 Description 设计

```yaml
name: prometheus
display_name: 📊 Prometheus 监控数据查询
description: >
  通用 Prometheus 监控数据查询技能。支持通过 PromQL 查询监控数据、调用 Prometheus HTTP API
  获取实时/历史指标、生成 HTML 交互式监控图表、查看当前活跃告警状态。当用户需要查询监控数据、
  生成监控曲线图、分析指标趋势、排查性能问题、获取 CPU/内存/磁盘/网络/请求量/错误率/延迟
  等监控指标、查看告警状态时使用此技能。
  本技能是通用查询引擎，不内嵌任何业务指标定义。通过标准输入协议接收查询参数（url + promql），
  调用方（其他 Skill、Workflow、用户）只需按协议提供参数即可。
version: 1.0.0
keywords: [Prometheus, PromQL, 监控, 指标, 查询, HTTP API, 告警, CPU, 内存, QPS,
           错误率, 延迟, Grafana, 时间序列]
examples:
  - 查询某服务的 CPU 使用率
  - 过去 1 小时的 QPS 趋势
  - 帮我写一个查错误率的 PromQL
  - 查看当前活跃告警
  - 帮我输出过去 6 小时的 QPS 监控图表
```

**分析**：description 明确了"通用查询引擎"和"标准输入协议"的定位，关键词来源于用户操作意图而非业务名词，不包含任何业务耦合的 example。这让 Agent 在面对任何监控查询需求时都能命中 prometheus Skill，而不会因为缺少特定业务关键词而漏选。

### 6.2 边界声明与解耦设计

```markdown
## 边界说明
- 可通过 scripts/prometheus_query.py 脚本实际执行 Prometheus 查询
- 支持 --format chart 将范围查询结果生成自包含 HTML 交互式图表
- **不内嵌任何业务指标定义**：业务指标（指标名、PromQL 模板、Job 命名规则等）由调用方按标准输入协议提供
- **不内嵌任何业务集群地址**：Prometheus 查询地址由调用方按标准输入协议提供
- **不知道有哪些业务/服务/集群存在**：本技能是纯通用引擎，完全不感知调用方的业务上下文
- 不负责 Prometheus 集群的部署、扩缩容或底层存储管理
- 不负责 Prometheus 配置管理（Scrape、服务发现、Recording Rules、Alert Rules）
- 不提供 Grafana Dashboard 的创建/编辑
```

边界声明的核心是**三个"不"**——不内嵌指标、不内嵌地址、不感知业务。这种设计让 prometheus skill 成为一个真正的通用引擎，新服务接入时完全不需要修改 prometheus skill。

### 6.3 标准输入协议

prometheus skill 的核心设计是**标准输入协议**——通过一组标准化参数接收查询请求，不关心参数从哪来：

```markdown
| 参数 | 必选 | 说明 | 示例 |
|------|------|------|------|
| url | ✅ | Prometheus 查询地址 | http://prometheus:9090 |
| promql | ✅ | PromQL 查询表达式 | sum(rate(http_requests_total[5m])) |
| mode | ❌ | 查询模式（默认 range） | instant / range |
| range | ❌ | 时间范围（默认 1h） | 6h、1d、7d |
| format | ❌ | 输出格式（默认 text） | text / chart |
| auth.username | ❌ | Basic Auth 用户名 | admin |
| auth.password | ❌ | Basic Auth 密码 | secret |
```

### 6.4 查询模板（templates）

prometheus Skill 提供了**通用查询模板**，Agent 不需要从零构造 PromQL 和 curl 命令，而是从模板出发做参数替换，大幅降低生成错误查询的概率。模板只覆盖通用场景，不包含任何业务特定的查询模板：

```markdown
| 模板文件                      | 用途           | 典型场景                              |
|-----------------------------|---------------|--------------------------------------|
| instant-query.md            | 即时查询        | 健康检查、CPU/内存/QPS/错误率的当前值     |
| range-query-chart.md        | 范围查询 + 图表  | QPS/CPU/内存/错误率/延迟趋势图           |
| time-range-query.md         | 指定时间范围查询  | 查询某天全天、指定时间段、跨天时段         |
| alerts-and-targets.md       | 告警与目标状态   | 活跃告警、抓取目标、规则、标签探索         |
| troubleshooting.md          | 故障排查        | TOP N 排序、突增突降、内存泄漏、磁盘预测   |
```

业务特定的查询模板（如某个服务的 PromQL、集群地址等）不放在 prometheus skill 中，而是由各业务 Skill 自行维护，实现引擎与业务的彻底解耦。

### 6.5 强制验证流程

prometheus Skill 在使用流程中设计了一个**强制验证环节**——在执行查询前，必须验证标准输入协议的必选参数已就绪：

```markdown
### Step 2：验证输入协议（查询/图表类必须执行）

> ⚠️ 关键步骤：在执行任何监控数据查询或图表生成之前，
> 必须验证标准输入协议的必选参数已就绪。不得跳过此步骤直接执行查询。

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

验证流程不绑定任何特定业务的地址拼接逻辑，而是纯粹验证协议参数的完整性和合理性。监控查询的"地址错误"是最常见的失败原因，把验证流程写成强制步骤而不是依赖 Agent 自己判断，能显著降低查错集群的概率。

### 6.6 严格规则

```markdown
## ⛔ 严格规则

### PromQL 编写规则
1. Counter 类型必须用 rate() 或 increase()：直接查询 Counter 原始值无意义
2. rate() 的时间窗口不能小于 scrape_interval 的 4 倍：推荐至少 [5m]
3. histogram_quantile() 必须保留 le 标签：聚合时用 sum by (le) 而非 sum

### 查询安全规则
1. 范围查询必须设置合理的 step：避免返回过多数据点导致 OOM
2. 避免无标签过滤的全量查询
3. 高基数指标谨慎查询：先用 count() 确认序列数量
```

工具能力类 Skill 的严格规则更偏向**技术正确性约束**。风险不在于"答错知识"，而在于"生成错误的查询导致系统问题"（如无过滤全量查询导致 OOM）。

---

## 七、三种使用方式实践样例

Prometheus Skill 支持三种使用方式，覆盖从简单到复杂的不同场景。三种方式的共同点是：**Prometheus Skill 始终是纯通用引擎**，不内嵌任何业务指标定义和集群地址，只负责“接收参数 → 执行查询 → 输出结果”。

### 7.1 方式一：URL 直接指定

**适用场景**：快速查询、临时排障、个人开发调试

用户直接在对话中提供 Prometheus 地址和查询意图，Agent 根据标准输入协议执行查询。这是最简单的使用方式，无需任何额外配置。

**用户对话示例**：

```
用户：帮我查一下 http://prometheus.example.com:9090 上过去 6 小时的 QPS 趋势，并生成图表
```

Agent 解析出协议参数后执行：

```bash
python3 scripts/prometheus_query.py \
  --url http://prometheus.example.com:9090 \
  --mode range --range 6h \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output /tmp/qps-trend.html
```

**特点**：上手难度最低，直接提供地址即可；无需配置多个 Skill；指标变更时用户自行修改查询。

### 7.2 方式二：AI 自主协调

**适用场景**：多服务监控、跨模块协作、服务故障排查

在多 Skill 环境中，Agent 自主协调多个 Skill 完成任务。业务 Skill 提供指标定义和集群地址，Prometheus Skill 提供查询能力，Agent 自动将两者串联。

**协作流程示例**：

```
用户：帮我查一下 user-service 的 CPU 使用率

→ Agent 激活业务 Skill（如 user-service-ops）
  → 业务 Skill 提供：
     url: http://prometheus.internal:9090
     promql: 100 - avg(rate(process_cpu_seconds_total{job="user-service"}[5m])) * 100

→ Agent 激活 Prometheus Skill
  → 接收协议参数，执行查询，输出结果
```

**关键设计**：业务 Skill 在其 reference 文档中声明监控定义（指标名、PromQL 模板、Prometheus 地址），并按 Prometheus Skill 的标准输入协议格式提供参数。新服务接入时只需在业务 Skill 中创建指标文档，完全不需要修改 Prometheus Skill。

### 7.3 方式三：Workflow 编排

**适用场景**：自动化巡检、批量报告、定时监控流水线

通过 Workflow 定义多步骤流水线，将参数获取、查询执行、结果处理编排为自动化流程。

**Workflow 定义示例**：

```yaml
name: daily-service-health-check
steps:
  - name: get_cluster_info
    skill: cluster-info
    output: prometheus_url

  - name: get_metrics_definition
    skill: user-service-ops
    output: promql_list

  - name: query_metrics
    skill: prometheus
    input:
      url: ${{ steps.get_cluster_info.outputs.prometheus_url }}
      promql: ${{ steps.get_metrics_definition.outputs.promql_list }}
      mode: range
      range: 24h
      format: chart

  - name: generate_report
    skill: report-generator
    input:
      charts: ${{ steps.query_metrics.outputs.chart_files }}
```

**特点**：全自动执行，无需人工干预；新服务接入只需在工作流中添加 Step；指标变更只需修改上游 Step 输出。

### 7.4 三种方式对比

| 维度 | URL 直接指定 | AI 自主协调 | Workflow 编排 |
|------|-------------|------------|---------------|
| 上手难度 | ⭐ 最低 | ⭐⭐ 中等 | ⭐⭐⭐ 较高 |
| 适用场景 | 快速查询、临时排障 | 多服务监控、跨模块协作 | 自动化巡检、批量报告 |
| 自动化程度 | 手动 | 半自动（Agent 协调） | 全自动（工作流驱动） |
| 新服务接入 | 无需配置 | 只需创建指标文档 | 只需添加 Step |
| Prometheus Skill 改动 | 无 | 无 | 无 |

---

## 八、结论

Skill 不只是给 Agent 追加的一段文档，而是 Agent 执行性能的组成部分。Skill 的 description 决定路由命中率，正文结构决定上下文效率，规则和约束决定回答稳定性。

从 `prometheus`（工具能力类）的三种使用方式可以看到，好的 Skill 都在做同一件事：**用结构化的规则替代 Agent 的自由推理，用最小必要信息替代全量上下文，用明确的边界替代模糊的能力范围**。

prometheus 的设计验证了一个原则：**工具类 Skill 应该是纯通用引擎，通过标准输入协议与业务 Skill 解耦**。无论是用户直接指定 URL、Agent 自主协调多个 Skill、还是 Workflow 编排自动化流水线，prometheus skill 始终只负责"接收参数 → 执行查询 → 输出结果"，完全不需要触碰查询引擎——这就是"开闭原则"在 Skill 体系中的落地。

这些实践做好之后，Agent 在真实工作流中的表现会明显更稳、更准、更可预期。