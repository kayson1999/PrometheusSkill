# Prometheus 范围查询 + 图表生成模板（Range Query + Chart）

> **用途**：查询时间段内的指标趋势并生成 HTML 交互式图表
> **使用**：修改 `PROM_URL`、PromQL、时间范围后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
SCRIPT="scripts/prometheus_query.py"
OUTPUT_DIR="/tmp"
```

## 场景 1：最近 N 小时的 QPS 趋势图

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 6h \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-trend-6h.html"
```

## 场景 2：按 job 分组的 QPS 趋势（多序列对比）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 1h \
  --query 'sum by (job) (rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-by-job.html"
```

## 场景 3：CPU 使用率趋势图

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 24h \
  --query '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)' \
  --format chart --output "${OUTPUT_DIR}/cpu-usage-24h.html"
```

## 场景 4：内存使用率趋势图

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 24h \
  --query '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100' \
  --format chart --output "${OUTPUT_DIR}/memory-usage-24h.html"
```

## 场景 5：错误率趋势图

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 6h \
  --query 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/error-rate-6h.html"
```

## 场景 6：P95 延迟趋势图

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 6h \
  --query 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))' \
  --format chart --output "${OUTPUT_DIR}/latency-p95-6h.html"
```

## 场景 7：多分位延迟对比图（P50/P90/P99 叠加）

> 注意：需要分别查询后手动对比，或使用 Grafana。这里演示 P99 单独查询。

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 6h \
  --query 'histogram_quantile(0.99, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m])))' \
  --format chart --output "${OUTPUT_DIR}/latency-p99-by-job.html"
```

## 场景 8：容器 CPU 使用率趋势（K8s 环境）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 6h \
  --query 'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{namespace="default"}[5m]))' \
  --format chart --output "${OUTPUT_DIR}/container-cpu-6h.html"
```
