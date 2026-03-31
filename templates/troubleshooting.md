# Prometheus 故障排查 PromQL 模板

> **用途**：常见故障排查场景的 PromQL 查询命令
> **使用**：修改 `PROM_URL` 和相关标签后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
SCRIPT="scripts/prometheus_query.py"
OUTPUT_DIR="/tmp"
```

## 场景 1：找出 CPU 使用率最高的 5 台机器

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'topk(5, 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))'
```

## 场景 2：找出错误率最高的 5 个服务

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'topk(5, sum by (job) (rate(http_requests_total{status=~"5.."}[5m])) / sum by (job) (rate(http_requests_total[5m])))'
```

## 场景 3：找出延迟最高的 5 个服务（P95）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'topk(5, histogram_quantile(0.95, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m]))))'
```

## 场景 4：找出内存增长最快的实例（可能内存泄漏）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'topk(5, deriv(process_resident_memory_bytes[1h]))'
```

## 场景 5：找出磁盘即将满的实例（预测 4 小时内耗尽）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'predict_linear(node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}[6h], 4*3600) < 0'
```

## 场景 6：找出最近 1 小时重启过的服务

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'changes(process_start_time_seconds[1h]) > 0'
```

## 场景 7：请求量突增的服务（当前 vs 1 小时前 > 2 倍）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query '(sum by (job) (rate(http_requests_total[5m])) / sum by (job) (rate(http_requests_total[5m] offset 1h))) > 2'
```

## 场景 8：请求量突降的服务（当前 < 1 小时前的 50%）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query '(sum by (job) (rate(http_requests_total[5m])) / sum by (job) (rate(http_requests_total[5m] offset 1h))) < 0.5'
```

## 场景 9：Pod 重启次数（K8s 环境，过去 1 小时）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'increase(kube_pod_container_status_restarts_total[1h]) > 0'
```

## 场景 10：CPU 限流比例（K8s 容器被 throttle）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'sum by (namespace, pod) (rate(container_cpu_cfs_throttled_periods_total[5m])) / sum by (namespace, pod) (rate(container_cpu_cfs_periods_total[5m])) > 0.1'
```

## 场景 11：故障时段的错误率趋势图（指定时间范围）

> 修改 `--start` 和 `--end` 为故障发生的时间段。

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range \
  --start '2024-03-26 14:00:00' \
  --end '2024-03-26 16:00:00' \
  --query 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/incident-error-rate.html"
```
