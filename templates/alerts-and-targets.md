# Prometheus 告警与目标状态查询模板

> **用途**：查看告警状态、抓取目标、规则、指标元数据
> **使用**：修改 `PROM_URL` 后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
SCRIPT="scripts/prometheus_query.py"
```

## 1. 查看当前活跃告警

```bash
python3 $SCRIPT --url "$PROM_URL" --mode alerts
```

## 2. 查看所有抓取目标状态

```bash
python3 $SCRIPT --url "$PROM_URL" --mode targets
```

## 3. 查看告警和 Recording Rules

```bash
python3 $SCRIPT --url "$PROM_URL" --mode rules
```

## 4. 查看所有 job 名称

```bash
python3 $SCRIPT --url "$PROM_URL" --mode labels --label job
```

## 5. 查看所有标签名

```bash
python3 $SCRIPT --url "$PROM_URL" --mode labels
```

## 6. 查看指标元数据

```bash
python3 $SCRIPT --url "$PROM_URL" --mode metadata --query 'http_requests_total'
```

## 7. 查找匹配的时间序列

```bash
python3 $SCRIPT --url "$PROM_URL" --mode series --query 'http_requests_total' --range 1h
```

## 8. 使用 PromQL 检查 down 的目标

```bash
python3 $SCRIPT --url "$PROM_URL" --query 'up == 0'
```

## 9. 查看最近 1 小时重启过的服务

```bash
python3 $SCRIPT --url "$PROM_URL" --query 'changes(process_start_time_seconds[1h]) > 0'
```
