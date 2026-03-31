# Prometheus 告警规则配置

## 概述

Prometheus 告警规则（Alerting Rules）定义在 YAML 配置文件中，由 Prometheus 定期评估。
当规则条件满足时，Prometheus 会生成告警并发送到 Alertmanager 进行路由、分组和通知。

本文档覆盖：
- 告警规则文件语法
- 通过 Prometheus HTTP API 管理规则（查看/重载）
- 通过 Alertmanager HTTP API 管理告警（查看/静默/抑制）
- 常用告警规则模板（资源/服务/容器等场景）
- 规则验证工具（promtool）

## 告警规则文件语法

### 基本结构

```yaml
# 告警规则文件（如 /etc/prometheus/rules/alert_rules.yml）
groups:
  - name: <group_name>          # 规则组名称（同组规则按相同间隔评估）
    interval: <duration>         # 评估间隔（可选，默认使用全局 evaluation_interval）
    rules:
      - alert: <alert_name>     # 告警名称
        expr: <PromQL>          # 告警条件（PromQL 表达式）
        for: <duration>         # 持续时间（条件持续满足多久才触发，可选）
        keep_firing_for: <duration>  # 告警触发后至少保持多久（Prometheus 2.42+，可选）
        labels:                 # 附加标签（会合并到告警标签中）
          severity: critical    # 严重级别：critical / warning / info
          team: backend
        annotations:            # 注解信息（用于通知模板）
          summary: "{{ $labels.instance }} 的 {{ $labels.job }} 服务异常"
          description: "{{ $labels.instance }} 的 CPU 使用率已达 {{ $value | printf \"%.1f\" }}%"
          runbook_url: "https://wiki.example.com/runbook/high-cpu"
```

### 关键字段说明

| 字段 | 必选 | 说明 |
|------|------|------|
| `alert` | ✅ | 告警名称，同一组内唯一 |
| `expr` | ✅ | PromQL 表达式，返回非空结果时触发 |
| `for` | ❌ | 持续时间阈值，避免瞬时抖动误报（如 `5m`） |
| `keep_firing_for` | ❌ | 告警触发后最少保持时间，避免频繁恢复/触发（Prometheus 2.42+） |
| `labels` | ❌ | 附加标签，常用于 severity 分级和路由 |
| `annotations` | ❌ | 注解，支持 Go 模板语法，用于通知内容 |

### 模板变量

在 `labels` 和 `annotations` 中可使用 Go 模板语法：

| 变量 | 说明 | 示例 |
|------|------|------|
| `{{ $labels }}` | 告警的所有标签 | `{{ $labels.instance }}` |
| `{{ $labels.<name> }}` | 指定标签的值 | `{{ $labels.job }}` |
| `{{ $value }}` | 表达式的当前值 | `{{ $value \| printf "%.2f" }}` |
| `{{ $externalLabels }}` | Prometheus 外部标签 | `{{ $externalLabels.cluster }}` |

### 告警状态流转

```
inactive → pending → firing → resolved
    ↑         │         │
    └─────────┘         │  （条件不再满足）
    （for 未满足）       └──→ resolved
```

- **inactive**：条件不满足
- **pending**：条件满足但 `for` 时间未到
- **firing**：条件持续满足超过 `for` 时间，告警已触发
- **resolved**：条件不再满足，告警已恢复

## Prometheus 规则管理 API

### 查看所有规则

```bash
# 查看所有告警和 Recording Rules
curl -s 'http://<prometheus_host>:9090/api/v1/rules' | jq

# 仅查看告警规则
curl -s 'http://<prometheus_host>:9090/api/v1/rules?type=alert' | jq

# 仅查看 Recording Rules
curl -s 'http://<prometheus_host>:9090/api/v1/rules?type=record' | jq
```

### 查看活跃告警

```bash
# 查看当前所有活跃告警
curl -s 'http://<prometheus_host>:9090/api/v1/alerts' | jq

# 过滤特定告警
curl -s 'http://<prometheus_host>:9090/api/v1/alerts' | \
  jq '.data.alerts[] | select(.labels.alertname == "HighCPU")'
```

### 重载配置（热加载规则）

Prometheus 支持通过 HTTP API 热加载配置（需启动时添加 `--web.enable-lifecycle` 参数）：

```bash
# 方式 1：HTTP POST 重载
curl -X POST 'http://<prometheus_host>:9090/-/reload'

# 方式 2：发送 SIGHUP 信号
kill -HUP $(pidof prometheus)
```

### 查看当前配置

```bash
# 查看 Prometheus 当前加载的完整配置
curl -s 'http://<prometheus_host>:9090/api/v1/status/config' | jq '.data.yaml'

# 查看规则文件列表
curl -s 'http://<prometheus_host>:9090/api/v1/status/runtimeinfo' | jq
```

## Alertmanager HTTP API

Alertmanager 提供独立的 HTTP API 用于管理告警通知。

### 查看告警

```bash
# 查看所有告警
curl -s 'http://<alertmanager_host>:9093/api/v2/alerts' | jq

# 按标签过滤
curl -s 'http://<alertmanager_host>:9093/api/v2/alerts?filter=severity="critical"' | jq
```

### 创建静默（Silence）

```bash
# 创建静默规则（抑制特定告警的通知）
curl -X POST 'http://<alertmanager_host>:9093/api/v2/silences' \
  -H 'Content-Type: application/json' \
  -d '{
    "matchers": [
      {
        "name": "alertname",
        "value": "HighCPU",
        "isRegex": false,
        "isEqual": true
      },
      {
        "name": "instance",
        "value": "app1:9090",
        "isRegex": false,
        "isEqual": true
      }
    ],
    "startsAt": "2024-03-27T00:00:00Z",
    "endsAt": "2024-03-27T06:00:00Z",
    "createdBy": "admin",
    "comment": "计划维护窗口，临时静默 HighCPU 告警"
  }'
```

### 查看/删除静默

```bash
# 查看所有静默
curl -s 'http://<alertmanager_host>:9093/api/v2/silences' | jq

# 删除静默（通过 silenceID）
curl -X DELETE 'http://<alertmanager_host>:9093/api/v2/silence/<silenceID>'
```

### 查看告警分组

```bash
# 查看告警分组状态
curl -s 'http://<alertmanager_host>:9093/api/v2/alerts/groups' | jq
```

## 规则验证工具

### promtool 验证规则文件

```bash
# 检查规则文件语法
promtool check rules /etc/prometheus/rules/alert_rules.yml

# 检查所有规则文件
promtool check rules /etc/prometheus/rules/*.yml

# 测试规则（单元测试）
promtool test rules /etc/prometheus/rules/test_rules.yml
```

### 规则单元测试文件格式

```yaml
# test_rules.yml - 告警规则单元测试
rule_files:
  - alert_rules.yml

evaluation_interval: 1m

tests:
  - interval: 1m
    input_series:
      - series: 'up{job="my-app", instance="app1:9090"}'
        values: '1 1 1 0 0 0 0 0 0 0'  # 第 4 分钟开始 down
    alert_rule_test:
      - eval_time: 5m
        alertname: InstanceDown
        exp_alerts:
          - exp_labels:
              job: my-app
              instance: app1:9090
              severity: critical
            exp_annotations:
              summary: "app1:9090 的 my-app 服务已宕机"
```

## 常用告警规则模板

### 服务可用性

```yaml
groups:
  - name: service_availability
    rules:
      # 实例宕机
      - alert: InstanceDown
        expr: up == 0
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.instance }} 的 {{ $labels.job }} 服务已宕机"
          description: "{{ $labels.instance }} 已超过 3 分钟无法访问"

      # 抓取目标过多失败
      - alert: TooManyTargetsDown
        expr: (count by (job) (up == 0) / count by (job) (up)) > 0.5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} 超过 50% 的实例宕机"
```

### 资源使用率

```yaml
groups:
  - name: resource_alerts
    rules:
      # CPU 使用率过高
      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.instance }} CPU 使用率过高"
          description: "CPU 使用率已达 {{ $value | printf \"%.1f\" }}%，持续超过 10 分钟"

      # 内存使用率过高
      - alert: HighMemoryUsage
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.instance }} 内存使用率过高"
          description: "内存使用率已达 {{ $value | printf \"%.1f\" }}%"

      # 磁盘空间不足
      - alert: DiskSpaceLow
        expr: (1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes) * 100 > 85
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.instance }} 磁盘空间不足"
          description: "{{ $labels.mountpoint }} 磁盘使用率已达 {{ $value | printf \"%.1f\" }}%"

      # 磁盘将在 24 小时内写满（预测性告警）
      - alert: DiskWillFillIn24Hours
        expr: predict_linear(node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}[6h], 24*3600) < 0
        for: 30m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.instance }} 磁盘预计 24 小时内写满"
          description: "{{ $labels.mountpoint }} 按当前趋势预计 24 小时内磁盘空间耗尽"
```

### 请求与延迟

```yaml
groups:
  - name: request_alerts
    rules:
      # 错误率过高
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) by (job) / sum(rate(http_requests_total[5m])) by (job) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} 错误率过高"
          description: "{{ $labels.job }} 的 5xx 错误率已达 {{ $value | printf \"%.2f\" }}（阈值 5%）"

      # P99 延迟过高
      - alert: HighP99Latency
        expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job)) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.job }} P99 延迟过高"
          description: "{{ $labels.job }} 的 P99 延迟已达 {{ $value | printf \"%.2f\" }}s（阈值 1s）"

      # QPS 突降（相比 1 小时前下降 50%）
      - alert: QPSSuddenDrop
        expr: |
          (sum(rate(http_requests_total[5m])) by (job)
           / sum(rate(http_requests_total[5m] offset 1h)) by (job)) < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.job }} QPS 突降"
          description: "{{ $labels.job }} 的 QPS 相比 1 小时前下降超过 50%"
```

### 容器与 Kubernetes

```yaml
groups:
  - name: container_alerts
    rules:
      # 容器 OOM Kill
      - alert: ContainerOOMKilled
        expr: increase(kube_pod_container_status_restarts_total[1h]) > 3 and kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} == 1
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.namespace }}/{{ $labels.pod }} 容器频繁 OOM"
          description: "容器 {{ $labels.container }} 在过去 1 小时内 OOM 重启 {{ $value }} 次"

      # Pod 未就绪
      - alert: PodNotReady
        expr: kube_pod_status_ready{condition="true"} == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.namespace }}/{{ $labels.pod }} 未就绪"
          description: "Pod 已超过 10 分钟未进入 Ready 状态"

      # 容器 CPU 限流
      - alert: ContainerCPUThrottling
        expr: rate(container_cpu_cfs_throttled_seconds_total[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.namespace }}/{{ $labels.pod }} CPU 限流严重"
          description: "容器 {{ $labels.container }} CPU 限流率 {{ $value | printf \"%.2f\" }}s/s"
```

## 最佳实践

### 告警分级

| 级别 | 含义 | 响应时间 | 示例 |
|------|------|---------|------|
| `critical` | 严重影响，需立即处理 | < 5 分钟 | 服务宕机、数据丢失 |
| `warning` | 需要关注，可能恶化 | < 30 分钟 | CPU 高、磁盘快满 |
| `info` | 信息性通知 | 工作时间内 | 配置变更、版本更新 |

### for 时间建议

| 场景 | 建议 for 值 | 原因 |
|------|------------|------|
| 服务宕机 | 2m ~ 5m | 避免瞬时网络抖动误报 |
| 资源使用率 | 10m ~ 15m | 资源使用有波动，需持续观察 |
| 错误率 | 5m ~ 10m | 短暂错误峰值可能是正常的 |
| 预测性告警 | 30m ~ 1h | 预测需要更长时间确认趋势 |
| 容器 OOM | 0m | OOM 是确定性事件，无需等待 |

### 命名规范

- 告警名使用 **PascalCase**：`HighCPUUsage`、`InstanceDown`
- 规则组名使用 **snake_case**：`service_availability`、`resource_alerts`
- 标签值使用 **小写**：`severity: critical`
