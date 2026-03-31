# Prometheus 即时查询模板（Instant Query）

> **用途**：获取当前时刻的指标值
> **使用**：修改 `PROM_URL` 和 PromQL 后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
SCRIPT="scripts/prometheus_query.py"
```

## 1. 基础健康检查

查看所有目标的 up 状态：

```bash
python3 $SCRIPT --url "$PROM_URL" --query 'up'
```

查看 down 的目标：

```bash
python3 $SCRIPT --url "$PROM_URL" --query 'up == 0'
```

## 2. CPU 使用率

所有实例的 CPU 使用率：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
```

CPU 使用率 TOP 5：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'topk(5, 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))'
```

## 3. 内存使用率

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'
```

## 4. QPS 查询

总 QPS：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'sum(rate(http_requests_total[5m]))'
```

按 job 分组的 QPS：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'sum by (job) (rate(http_requests_total[5m]))'
```

## 5. 错误率

5xx 错误率：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))'
```

## 6. 延迟 P99

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --query 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))'
```

## 7. JSON 格式输出

```bash
python3 $SCRIPT --url "$PROM_URL" --query 'up' --format json
```
