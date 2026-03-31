# Prometheus 抓取规则配置

## 概述

Prometheus 通过 `scrape_configs` 配置抓取目标（targets），定期从目标的 `/metrics` 端点拉取监控数据。
抓取配置定义在 `prometheus.yml` 主配置文件中，支持静态配置和多种服务发现机制。

本文档覆盖：
- 抓取配置文件语法
- 静态目标配置
- 服务发现机制（Kubernetes、Consul、文件等）
- 标签重写（relabeling）
- 通过 HTTP API 查看抓取状态
- 常用抓取配置模板

## 抓取配置语法

### 基本结构

```yaml
# prometheus.yml 中的 scrape_configs 部分
global:
  scrape_interval: 15s          # 全局抓取间隔（默认 1m）
  scrape_timeout: 10s           # 全局抓取超时（默认 10s）
  evaluation_interval: 15s      # 规则评估间隔（默认 1m）
  external_labels:              # 外部标签（联邦/远程写入时附加）
    cluster: production
    region: ap-guangzhou

# 规则文件路径（支持通配符）
rule_files:
  - /etc/prometheus/rules/*.yml
  - /etc/prometheus/rules/*.yaml

# 抓取配置
scrape_configs:
  - job_name: <job_name>                # 任务名称（唯一标识）
    scrape_interval: <duration>          # 抓取间隔（可选，覆盖全局）
    scrape_timeout: <duration>           # 抓取超时（可选，覆盖全局）
    metrics_path: <path>                 # 指标路径（默认 /metrics）
    scheme: <scheme>                     # 协议：http / https（默认 http）
    honor_labels: <bool>                 # 是否保留目标自带标签（默认 false）
    honor_timestamps: <bool>             # 是否使用目标提供的时间戳（默认 true）
    params:                              # URL 查询参数
      module: [http_2xx]
    basic_auth:                          # Basic Auth 认证
      username: <string>
      password: <string>
    bearer_token: <string>               # Bearer Token 认证
    tls_config:                          # TLS 配置
      ca_file: <path>
      cert_file: <path>
      key_file: <path>
      insecure_skip_verify: <bool>
    static_configs:                      # 静态目标列表
      - targets: [...]
        labels: {...}
    relabel_configs:                     # 抓取前标签重写
      - ...
    metric_relabel_configs:              # 抓取后指标标签重写
      - ...
```

### 关键字段说明

| 字段 | 必选 | 说明 |
|------|------|------|
| `job_name` | ✅ | 任务名称，全局唯一，自动添加为 `job` 标签 |
| `scrape_interval` | ❌ | 抓取间隔，覆盖全局设置 |
| `scrape_timeout` | ❌ | 抓取超时，不能大于 scrape_interval |
| `metrics_path` | ❌ | 指标端点路径，默认 `/metrics` |
| `scheme` | ❌ | 协议，默认 `http` |
| `static_configs` | ❌ | 静态目标列表（与服务发现二选一） |
| `relabel_configs` | ❌ | 抓取前标签重写规则 |
| `metric_relabel_configs` | ❌ | 抓取后指标标签重写规则 |

## 静态目标配置

### 基本示例

```yaml
scrape_configs:
  # 监控 Prometheus 自身
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  # 监控 Node Exporter
  - job_name: node-exporter
    scrape_interval: 30s
    static_configs:
      - targets:
          - 'node1:9100'
          - 'node2:9100'
          - 'node3:9100'
        labels:
          env: production
          dc: guangzhou

  # 监控应用服务
  - job_name: my-app
    metrics_path: /actuator/prometheus    # Spring Boot Actuator
    scrape_interval: 15s
    static_configs:
      - targets: ['app1:8080', 'app2:8080']
        labels:
          service: user-service
          version: v2.1.0
```

### 多环境配置

```yaml
scrape_configs:
  - job_name: my-app-prod
    static_configs:
      - targets: ['prod-app1:8080', 'prod-app2:8080']
        labels:
          env: production

  - job_name: my-app-staging
    scrape_interval: 30s    # 非生产环境可降低频率
    static_configs:
      - targets: ['staging-app1:8080']
        labels:
          env: staging
```

## 服务发现

### 基于文件的服务发现（file_sd_configs）

最灵活的服务发现方式，Prometheus 自动监听文件变化并热加载。

```yaml
# prometheus.yml
scrape_configs:
  - job_name: file-sd-targets
    file_sd_configs:
      - files:
          - /etc/prometheus/targets/*.json
          - /etc/prometheus/targets/*.yml
        refresh_interval: 30s    # 文件检查间隔（默认 5m）
```

**JSON 格式的目标文件：**

```json
[
  {
    "targets": ["app1:8080", "app2:8080"],
    "labels": {
      "job": "my-app",
      "env": "production",
      "service": "user-service"
    }
  },
  {
    "targets": ["app3:8080"],
    "labels": {
      "job": "my-app",
      "env": "staging",
      "service": "user-service"
    }
  }
]
```

**YAML 格式的目标文件：**

```yaml
- targets:
    - app1:8080
    - app2:8080
  labels:
    job: my-app
    env: production
    service: user-service
```

### Kubernetes 服务发现

```yaml
scrape_configs:
  # 发现 Kubernetes Pod
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: ['default', 'production']
    relabel_configs:
      # 仅抓取带有 prometheus.io/scrape: "true" 注解的 Pod
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      # 使用注解中的端口
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: ${1}
      # 使用注解中的路径
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      # 添加 namespace 标签
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      # 添加 pod 名称标签
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod

  # 发现 Kubernetes Service
  - job_name: kubernetes-services
    kubernetes_sd_configs:
      - role: endpoints
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_service_name]
        target_label: service
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
```

### Consul 服务发现

```yaml
scrape_configs:
  - job_name: consul-services
    consul_sd_configs:
      - server: 'consul.example.com:8500'
        services: []    # 空列表表示发现所有服务
        tags:
          - prometheus   # 仅发现带有 prometheus 标签的服务
    relabel_configs:
      - source_labels: [__meta_consul_service]
        target_label: service
      - source_labels: [__meta_consul_dc]
        target_label: datacenter
      - source_labels: [__meta_consul_tags]
        regex: .*,env=([^,]+),.*
        target_label: env
```

## 标签重写（Relabeling）

### relabel_configs（抓取前）

在抓取目标之前对标签进行重写，常用于：
- 过滤目标（keep/drop）
- 修改目标地址
- 添加/修改标签

```yaml
relabel_configs:
  # 保留特定标签值的目标
  - source_labels: [__meta_kubernetes_namespace]
    action: keep
    regex: (production|staging)

  # 丢弃特定目标
  - source_labels: [__meta_kubernetes_pod_label_app]
    action: drop
    regex: test-.*

  # 替换标签值
  - source_labels: [__meta_kubernetes_pod_label_app]
    target_label: app
    action: replace

  # 使用多个源标签拼接
  - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_pod_name]
    separator: /
    target_label: instance

  # 使用 hashmod 进行分片（多 Prometheus 实例分担抓取）
  - source_labels: [__address__]
    modulus: 3
    target_label: __tmp_hash
    action: hashmod
  - source_labels: [__tmp_hash]
    regex: 0
    action: keep
```

### metric_relabel_configs（抓取后）

在抓取数据之后对指标标签进行重写，常用于：
- 丢弃不需要的指标
- 修改指标标签
- 降低高基数

```yaml
metric_relabel_configs:
  # 丢弃不需要的指标（减少存储）
  - source_labels: [__name__]
    regex: go_.*
    action: drop

  # 丢弃高基数标签
  - regex: (request_id|trace_id)
    action: labeldrop

  # 重命名指标
  - source_labels: [__name__]
    regex: old_metric_name
    target_label: __name__
    replacement: new_metric_name
```

### Relabel 动作说明

| 动作 | 说明 |
|------|------|
| `replace` | 用 `replacement` 替换 `target_label`（默认动作） |
| `keep` | 仅保留 `source_labels` 匹配 `regex` 的目标 |
| `drop` | 丢弃 `source_labels` 匹配 `regex` 的目标 |
| `hashmod` | 对 `source_labels` 取哈希模，用于分片 |
| `labelmap` | 将匹配 `regex` 的标签名映射为新标签名 |
| `labeldrop` | 丢弃匹配 `regex` 的标签 |
| `labelkeep` | 仅保留匹配 `regex` 的标签 |

## 通过 HTTP API 查看抓取状态

### 查看所有抓取目标

```bash
# 查看所有活跃和已丢弃的目标
curl -s 'http://<prometheus_host>:9090/api/v1/targets' | jq

# 仅查看活跃目标
curl -s 'http://<prometheus_host>:9090/api/v1/targets?state=active' | jq

# 仅查看已丢弃的目标
curl -s 'http://<prometheus_host>:9090/api/v1/targets?state=dropped' | jq

# 按 job 过滤
curl -s 'http://<prometheus_host>:9090/api/v1/targets' | \
  jq '.data.activeTargets[] | select(.labels.job == "my-app")'
```

### 查看抓取目标元数据

```bash
# 查看目标的指标元数据
curl -s 'http://<prometheus_host>:9090/api/v1/targets/metadata' | jq

# 按 job 过滤
curl -s 'http://<prometheus_host>:9090/api/v1/targets/metadata?match_target={job="my-app"}' | jq
```

### 查看当前配置

```bash
# 查看完整配置（包含所有 scrape_configs）
curl -s 'http://<prometheus_host>:9090/api/v1/status/config' | jq -r '.data.yaml'

# 查看运行时信息
curl -s 'http://<prometheus_host>:9090/api/v1/status/runtimeinfo' | jq
```

### 重载配置

```bash
# 热加载配置（需启动时添加 --web.enable-lifecycle）
curl -X POST 'http://<prometheus_host>:9090/-/reload'

# 验证配置文件语法
promtool check config /etc/prometheus/prometheus.yml
```

## 配置验证工具

### promtool 验证配置

```bash
# 检查主配置文件
promtool check config /etc/prometheus/prometheus.yml

# 检查规则文件
promtool check rules /etc/prometheus/rules/*.yml

# 检查 Web 配置（认证相关）
promtool check web-config /etc/prometheus/web.yml
```

### 常见验证错误

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `unknown fields in scrape_config` | 配置字段拼写错误 | 检查字段名是否正确 |
| `scrape timeout greater than interval` | 超时大于抓取间隔 | 调整 scrape_timeout < scrape_interval |
| `duplicate job name` | job_name 重复 | 确保每个 job_name 唯一 |
| `invalid regex` | relabel 中正则表达式语法错误 | 检查 regex 语法 |

## 常用抓取配置模板

### 监控基础设施

```yaml
scrape_configs:
  # Prometheus 自身
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  # Node Exporter（主机监控）
  - job_name: node-exporter
    scrape_interval: 30s
    static_configs:
      - targets: ['node1:9100', 'node2:9100']

  # cAdvisor（容器监控）
  - job_name: cadvisor
    scrape_interval: 15s
    static_configs:
      - targets: ['cadvisor:8080']

  # Blackbox Exporter（探针监控）
  - job_name: blackbox-http
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://example.com
          - https://api.example.com/health
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

### 监控中间件

```yaml
scrape_configs:
  # Redis Exporter
  - job_name: redis
    static_configs:
      - targets: ['redis-exporter:9121']
        labels:
          redis_instance: redis-master

  # MySQL Exporter
  - job_name: mysql
    static_configs:
      - targets: ['mysql-exporter:9104']
        labels:
          mysql_instance: mysql-master

  # Kafka Exporter
  - job_name: kafka
    static_configs:
      - targets: ['kafka-exporter:9308']

  # Nginx Exporter
  - job_name: nginx
    static_configs:
      - targets: ['nginx-exporter:9113']
```

## 最佳实践

### 抓取间隔建议

| 目标类型 | 建议间隔 | 原因 |
|---------|---------|------|
| 基础设施（Node/cAdvisor） | 15s ~ 30s | 需要较高精度 |
| 应用服务 | 15s ~ 30s | 业务指标需要及时反映 |
| 中间件（Redis/MySQL） | 30s ~ 60s | 指标变化相对平缓 |
| 探针监控（Blackbox） | 30s ~ 60s | 避免对目标造成压力 |
| 非生产环境 | 30s ~ 60s | 降低资源消耗 |

### 标签规范

- `job`：自动由 `job_name` 生成，表示服务/组件名称
- `instance`：自动由 `__address__` 生成，表示目标地址
- `env`：环境标识（production/staging/development）
- `service`：服务名称
- `team`：负责团队
- `dc` / `region`：数据中心/地域

### 安全建议

1. **使用 TLS**：生产环境建议启用 HTTPS 抓取
2. **认证保护**：对外暴露的 metrics 端点应添加认证
3. **网络隔离**：Prometheus 与目标之间使用内网通信
4. **最小权限**：Kubernetes SD 使用最小 RBAC 权限
