# Prometheus 指定时间范围查询模板（--start / --end）

> **用途**：查询过去某天或指定时间段的监控数据
> **使用**：修改 `PROM_URL`、日期、PromQL 后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
SCRIPT="scripts/prometheus_query.py"
OUTPUT_DIR="/tmp"
```

## 场景 1：查询某天全天数据

仅指定 `--start` 为纯日期，自动查询 00:00:00 ~ 23:59:59：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --start '2024-03-26' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-20240326-fullday.html"
```

## 场景 2：查询指定时间段（精确到小时）

同时指定 `--start` 和 `--end`：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range \
  --start '2024-03-26 10:00:00' \
  --end '2024-03-26 18:00:00' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-20240326-10to18.html"
```

## 场景 3：查询某个时间点之前 N 小时

仅指定 `--end` + `--range`：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 2h \
  --end '2024-03-26 18:00:00' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-before-18.html"
```

## 场景 4：查询某个时间点之后 N 小时

仅指定 `--start`（含时分秒）+ `--range`：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --range 6h \
  --start '2024-03-26 08:00:00' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-after-08.html"
```

## 场景 5：对比两天的数据（分别查询后对比）

第一天：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --start '2024-03-25' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-day1-0325.html"
```

第二天：

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range --start '2024-03-26' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format chart --output "${OUTPUT_DIR}/qps-day2-0326.html"
```

## 场景 6：查询跨天的时间段（如凌晨故障时段）

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range \
  --start '2024-03-25 22:00:00' \
  --end '2024-03-26 06:00:00' \
  --query 'sum(rate(http_requests_total{status=~"5.."}[5m]))' \
  --format chart --output "${OUTPUT_DIR}/error-overnight.html"
```

## 场景 7：使用 Unix 时间戳指定范围

```bash
python3 $SCRIPT --url "$PROM_URL" \
  --mode range \
  --start '1711400000' \
  --end '1711500000' \
  --query 'sum(rate(http_requests_total[5m]))' \
  --format json
```
