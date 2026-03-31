# PromQL 查询语言指南

## 常用查询模式速查表

### 资源监控

```promql
# CPU 使用率（百分比）
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 内存使用率（百分比）
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# 磁盘使用率（百分比）
(1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})) * 100

# 磁盘 I/O 利用率
rate(node_disk_io_time_seconds_total[5m]) * 100

# 网络接收速率（bytes/s）
sum by (instance) (rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[5m]))

# 网络发送速率（bytes/s）
sum by (instance) (rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[5m]))
```

### 请求/流量监控

```promql
# 总 QPS
sum(rate(http_requests_total[5m]))

# 按 job 分组的 QPS
sum by (job) (rate(http_requests_total[5m]))

# 按状态码分组的 QPS
sum by (status) (rate(http_requests_total[5m]))

# 5xx 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# 4xx 错误率
sum(rate(http_requests_total{status=~"4.."}[5m])) / sum(rate(http_requests_total[5m]))

# 成功率（可用性）
1 - (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))
```

### 延迟监控

```promql
# P50 延迟
histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# P90 延迟
histogram_quantile(0.90, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# P95 延迟
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# P99 延迟
histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# 平均延迟
sum(rate(http_request_duration_seconds_sum[5m])) / sum(rate(http_request_duration_seconds_count[5m]))
```

### 容器/K8s 监控

```promql
# 容器 CPU 使用率（相对 limit）
(sum by (namespace, pod, container) (rate(container_cpu_usage_seconds_total[5m])) / sum by (namespace, pod, container) (container_spec_cpu_quota / container_spec_cpu_period)) * 100

# 容器内存使用率（相对 limit）
(container_memory_working_set_bytes / container_spec_memory_limit_bytes) * 100

# Pod 重启次数（过去 1 小时）
increase(kube_pod_container_status_restarts_total[1h])

# Pending Pod 数量
count(kube_pod_status_phase{phase="Pending"})

# CPU 限流比例
sum by (namespace, pod, container) (rate(container_cpu_cfs_throttled_periods_total[5m])) / sum by (namespace, pod, container) (rate(container_cpu_cfs_periods_total[5m]))
```

## 核心函数

| 函数 | 用途 | 示例 |
|------|------|------|
| `rate()` | 计算 Counter 的每秒增长率 | `rate(http_requests_total[5m])` |
| `irate()` | 基于最后两个数据点的瞬时增长率 | `irate(http_requests_total[5m])` |
| `increase()` | 时间范围内的总增量 | `increase(http_requests_total[1h])` |
| `sum()` | 求和聚合 | `sum by (job) (rate(...))` |
| `avg()` | 平均值聚合 | `avg by (instance) (...)` |
| `max()` / `min()` | 最大/最小值 | `max by (job) (...)` |
| `count()` | 计数 | `count by (job) (up == 1)` |
| `topk()` | 取前 N 个最大值 | `topk(5, rate(http_requests_total[5m]))` |
| `bottomk()` | 取前 N 个最小值 | `bottomk(5, ...)` |
| `histogram_quantile()` | 从 Histogram 计算分位数 | `histogram_quantile(0.95, ...)` |
| `predict_linear()` | 线性预测 | `predict_linear(node_filesystem_avail_bytes[6h], 4*3600)` |
| `delta()` | Gauge 在时间范围内的变化量 | `delta(process_resident_memory_bytes[1h])` |
| `deriv()` | Gauge 的每秒变化率 | `deriv(process_resident_memory_bytes[1h])` |
| `absent()` | 检测指标是否存在 | `absent(up{job="my-app"})` |
| `changes()` | 时间范围内值变化的次数 | `changes(process_start_time_seconds[1h])` |
| `resets()` | Counter 重置次数 | `resets(http_requests_total[1h])` |
| `label_replace()` | 标签替换 | `label_replace(up, "host", "$1", "instance", "(.*):.*")` |

## 操作符

```promql
# 算术操作符: + - * / % ^
http_requests_total / 1000

# 比较操作符: == != > < >= <=
up == 0                          # 返回 down 的目标
rate(http_requests_total[5m]) > 100  # QPS 超过 100 的

# 逻辑操作符: and or unless
up == 0 and on(job) (count by (job) (up) > 1)  # 有多实例的 job 中 down 的

# 聚合操作符: by / without
sum by (job) (rate(http_requests_total[5m]))     # 按 job 聚合
sum without (instance) (rate(http_requests_total[5m]))  # 排除 instance 聚合
```

## 常见排查场景的 PromQL

```promql
# 场景1：找出 CPU 使用率最高的 5 台机器
topk(5, 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))

# 场景2：找出错误率最高的 5 个服务
topk(5, sum by (job) (rate(http_requests_total{status=~"5.."}[5m])) / sum by (job) (rate(http_requests_total[5m])))

# 场景3：找出延迟最高的 5 个服务
topk(5, histogram_quantile(0.95, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m]))))

# 场景4：找出内存增长最快的实例（可能内存泄漏）
topk(5, deriv(process_resident_memory_bytes[1h]))

# 场景5：找出磁盘即将满的实例（4 小时内）
predict_linear(node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}[6h], 4*3600) < 0

# 场景6：找出最近 1 小时重启过的服务
changes(process_start_time_seconds[1h]) > 0

# 场景7：找出请求量突增的服务（当前 vs 1 小时前）
(sum by (job) (rate(http_requests_total[5m])) / sum by (job) (rate(http_requests_total[5m] offset 1h))) > 2

# 场景8：找出请求量突降的服务
(sum by (job) (rate(http_requests_total[5m])) / sum by (job) (rate(http_requests_total[5m] offset 1h))) < 0.5
```
