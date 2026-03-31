# 📊 Prometheus 监控数据查询与配置管理技能

通用 Prometheus 监控技能，支持监控数据的**查询获取**、PromQL 编写、HTTP API 调用、HTML 交互式图表生成、**告警规则创建/配置**、**Prometheus 抓取规则配置**和 **Alertmanager 静默管理**。支持三种使用方式，核心设计思想是标准输入协议——Skill 本身不关心参数从哪来，只要调用方按协议提供 url + promql 等参数即可。不内嵌任何业务指标定义或集群地址，适用于任何使用 Prometheus 的监控场景。

## 系统要求

| 项目 | 要求 |
|------|------|
| **Python** | 3.6+（脚本仅使用标准库，零额外依赖） |
| **Prometheus** | 2.0+（支持 HTTP API v1） |
| **Alertmanager** | 0.15+（静默管理功能需要，可选） |
| **浏览器** | 现代浏览器（图表功能基于 ECharts CDN） |
| **网络** | 能访问目标 Prometheus 实例的 HTTP API |
| **操作系统** | Linux / macOS / Windows（支持 Python 3 的任何系统） |

## 核心能力

### 🔍 监控数据查询
- **即时查询**：通过 Prometheus HTTP API 获取当前时刻的指标值
- **范围查询**：获取时间段内的指标变化趋势
- **PromQL 指南**：常用查询模式速查表（CPU/内存/磁盘/QPS/错误率/延迟等）
- **查询脚本**：Python 脚本工具，支持多种查询模式和输出格式
- **目标状态**：查看抓取目标健康状态
- **告警查看**：查看当前活跃告警和规则状态

### 🔔 告警规则创建与管理
- **规则文件生成**：通过命令行参数创建告警规则 YAML 文件
- **预设模板**：内置 standard/kubernetes/infrastructure 三套告警规则模板
- **规则验证**：检查规则文件语法、必要字段、Counter 类型使用
- **规则追加**：向已有规则文件追加新规则
- **配置热加载**：通过 HTTP API 重载 Prometheus 配置

### 📡 抓取规则配置
- **静态目标配置**：生成 scrape_config YAML 配置
- **文件服务发现**：生成 JSON/YAML 格式的目标文件
- **预设模板**：内置 infrastructure/middleware/blackbox 三套抓取配置模板
- **配置验证**：检查配置文件语法、job_name 唯一性
- **配置追加**：向已有配置文件追加新的抓取任务

### 🔇 Alertmanager 静默管理
- **创建静默**：按告警名称、实例、自定义标签创建静默规则
- **查看静默**：列出所有活跃和过期的静默
- **删除静默**：通过 ID 删除指定静默

### 📊 HTML 交互式图表输出
- **自包含 HTML**：基于 ECharts CDN，零额外依赖，浏览器直接打开
- **深色主题**：类 Grafana 风格，视觉效果专业
- **交互式**：鼠标悬停显示数值、支持缩放和拖拽
- **统计卡片**：自动计算 min/max/avg/latest
- **多序列支持**：自动分配颜色，图例可点击切换

### 🔐 认证支持
- **Basic Auth**：支持 `--username`/`--password` 参数进行 HTTP Basic Auth 认证
- **交互式提示**：未提供密码时交互式输入（密码不回显），服务端返回 401/403 时自动提示输入账号密码
- **安全优先**：推荐仅指定 `--username`，密码交互式输入，避免泄露到 shell 历史

## 文件结构

```
prometheus/
├── SKILL.md                              # 主入口（概述 + 文档分工 + 使用方式 + 规则）
├── README.md                             # 本文件（使用说明）
├── references/
│   ├── http-api-查询.md                  # HTTP API 查询文档
│   ├── promql-指南.md                    # PromQL 查询语言指南
│   ├── 查询脚本工具.md                    # Shell/Python 脚本工具
│   ├── alerting-rules-配置.md             # 告警规则配置文档
│   └── scrape-config-配置.md              # 抓取规则配置文档
├── scripts/
│   ├── prometheus_query.py               # Python 查询脚本工具
│   └── prometheus_config.py              # Python 配置管理脚本工具
└── templates/
    ├── instant-query.md                  # 即时查询模板
    ├── range-query-chart.md              # 范围查询 + 图表生成模板
    ├── time-range-query.md               # 指定时间范围查询模板
    ├── alerts-and-targets.md             # 告警与目标状态模板
    ├── troubleshooting.md                # 故障排查模板
    ├── alerting-rules.md                 # 告警规则配置模板
    └── scrape-config.md                  # 抓取规则配置模板
```

## 使用步骤

### 1. 安装 Skill
将 skill 目录复制到项目的 `.xx/skills/` 下

### 2. 三种使用方式

#### 2.1 URL直接指定
通过 url 参数指定 Prometheus 地址。参考 `templates/` 目录中的 7 套命令模板快速上手

#### 2.2 AI自主协调
在多 skills 之间协作使用

#### 2.3 Workflow编排
利用工作流编排的方式，在具体服务的监控文档中声明监控定义，如"提供 Prometheus skill 标准输入协议中的 promql 参数，实现指标与查询引擎解耦"

## 快速使用

### 查询监控数据

```bash
# 查看所有抓取目标状态
python3 scripts/prometheus_query.py --url http://localhost:9090 --mode targets

# 即时查询 CPU 使用率
python3 scripts/prometheus_query.py --url http://localhost:9090 \
  --query '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'

# 范围查询过去 6 小时的 QPS 趋势
python3 scripts/prometheus_query.py --url http://localhost:9090 \
  --mode range --range 6h \
  --query 'sum(rate(http_requests_total[5m]))'

# 查看当前活跃告警
python3 scripts/prometheus_query.py --url http://localhost:9090 --mode alerts
```

### 🔔 告警规则管理

```bash
# 创建单条告警规则
python3 scripts/prometheus_config.py --action create-alert-rule \
  --output /tmp/rules.yml --group-name "resource_alerts" \
  --alert-name "HighCPU" --expr 'cpu > 80' --for 5m --severity warning \
  --summary '{{ $labels.instance }} CPU 过高'

# 使用预设模板生成一套标准告警规则
python3 scripts/prometheus_config.py --action generate-alert-rules \
  --template standard --output /tmp/standard_alerts.yml

# 验证规则文件
python3 scripts/prometheus_config.py --action validate-rules \
  --rules-file /tmp/rules.yml

# 查看 Prometheus 上的所有规则
python3 scripts/prometheus_config.py --url http://localhost:9090 --action list-rules

# 热加载配置
python3 scripts/prometheus_config.py --url http://localhost:9090 --action reload
```

### 📡 抓取规则配置

```bash
# 创建抓取配置
python3 scripts/prometheus_config.py --action create-scrape-config \
  --output /tmp/scrape.yml --job-name "my-app" \
  --targets "app1:8080,app2:8080" --scrape-interval 15s \
  --labels "env=production,service=user-service"

# 创建文件服务发现目标文件
python3 scripts/prometheus_config.py --action create-file-sd-targets \
  --output /tmp/targets.json --targets "app1:8080,app2:8080" \
  --labels "job=my-app,env=production"

# 使用预设模板生成基础设施监控配置
python3 scripts/prometheus_config.py --action generate-scrape-config \
  --template infrastructure --output /tmp/prometheus.yml

# 查看当前抓取目标状态
python3 scripts/prometheus_config.py --url http://localhost:9090 --action list-targets
```

### 🔇 Alertmanager 静默管理

```bash
# 创建静默（抑制特定告警通知）
python3 scripts/prometheus_config.py --url http://localhost:9093 \
  --action create-silence --alertname "HighCPU" \
  --duration 6h --comment "计划维护窗口"

# 查看所有静默
python3 scripts/prometheus_config.py --url http://localhost:9093 --action list-silences

# 删除静默
python3 scripts/prometheus_config.py --url http://localhost:9093 \
  --action delete-silence --silence-id "<silence_id>"
```

### 🔐 带认证的查询

```bash
# 直接指定账号密码
python3 scripts/prometheus_query.py --url http://prom:9090 \
  --username admin --password my_secret --query 'up'

# 仅指定账号，交互式输入密码（推荐）
python3 scripts/prometheus_query.py --url http://prom:9090 \
  --username admin --query 'up'

# 未指定认证，服务端返回 401 时自动提示输入
python3 scripts/prometheus_query.py --url http://prom:9090 --query 'up'
```

### 📊 生成 HTML 监控图表

```bash
# 生成 QPS 趋势图表（过去 6 小时）
python3 scripts/prometheus_query.py --url http://localhost:9090 \
  --mode range --range 6h \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart

# 指定输出路径，按 job 分组
python3 scripts/prometheus_query.py --url http://localhost:9090 \
  --mode range --range 1h \
  --query 'sum by (job) (rate(http_requests_total[5m]))' \
  --format chart --output /tmp/qps-by-job.html
```

## 📝 查询与配置模板

`templates/` 目录提供了 7 套可直接复制使用的命令模板：

| 模板 | 用途 |
|------|------|
| `instant-query.md` | 即时查询：健康检查、CPU/内存/QPS/错误率当前值 |
| `range-query-chart.md` | 范围查询 + 图表：QPS/CPU/延迟等趋势图 |
| `time-range-query.md` | 指定时间查询：某天全天、指定时段、跨天时段 |
| `alerts-and-targets.md` | 告警与目标：活跃告警、抓取目标、规则查看 |
| `troubleshooting.md` | 故障排查：TOP N、突增突降、内存泄漏、磁盘预测 |
| `alerting-rules.md` | 告警规则配置：规则生成、预设模板、验证、热加载、静默管理 |
| `scrape-config.md` | 抓取规则配置：静态目标、文件服务发现、配置验证、热加载 |

使用方式：修改模板中的 `PROM_URL` 和 PromQL 后直接执行。

### 直接使用 curl

```bash
# 即时查询
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq

# 范围查询
curl -s 'http://localhost:9090/api/v1/query_range' \
  --data-urlencode 'query=rate(http_requests_total[5m])' \
  --data-urlencode "start=$(date -d '1 hour ago' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode 'step=60s' | jq
```

## Installation

```bash
npx add https://github.com/wpank/ai/tree/main/skills/devops/prometheus
```

### OpenClaw / Moltbot / Clawbot

```bash
npx clawhub@latest install prometheus
```

### Manual Installation

#### Cursor (per-project)

From your project root:

```bash
mkdir -p .cursor/skills
cp -r ~/.ai-skills/skills/devops/prometheus .cursor/skills/prometheus
```

#### Cursor (global)

```bash
mkdir -p ~/.cursor/skills
cp -r ~/.ai-skills/skills/devops/prometheus ~/.cursor/skills/prometheus
```

#### Claude Code (per-project)

From your project root:

```bash
mkdir -p .claude/skills
cp -r ~/.ai-skills/skills/devops/prometheus .claude/skills/prometheus
```

#### Claude Code (global)

```bash
mkdir -p ~/.claude/skills
cp -r ~/.ai-skills/skills/devops/prometheus ~/.claude/skills/prometheus
```

## ⚠️ 注意事项

### 安全建议
- **密码安全**：推荐使用交互式密码输入（仅指定 `--username`），避免密码出现在 shell 命令历史中
- **网络访问**：确保你的环境能访问目标 Prometheus 实例的 HTTP API 端口
- **图表 CDN**：HTML 图表依赖 `cdn.jsdelivr.net` 加载 ECharts，离线环境需自行替换 CDN 地址

### 查询限制
- **范围查询**：避免无标签过滤的全量查询，可能导致 Prometheus OOM
- **高基数指标**：先用 `count()` 确认序列数量，再执行查询
- **Counter 类型**：必须使用 `rate()` 或 `increase()` 包裹，直接查询原始值无意义
- **step 步长**：脚本默认自动计算，也可通过 `--step` 手动指定

### 兼容性
- 本技能是通用 Prometheus 引擎，不内嵌任何业务指标定义或集群地址
- 支持直连 Prometheus 实例和通过 Grafana 数据源代理访问
- 可与其他 Skill 或 Workflow 配合使用，通过标准输入协议接收参数

## License

MIT License
