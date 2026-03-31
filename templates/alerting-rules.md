# Prometheus 告警规则配置模板

> **用途**：创建和管理告警规则，包括规则文件生成、验证、热加载和 Alertmanager 静默管理
> **使用**：修改 `PROM_URL`、`ALERTMANAGER_URL` 和规则参数后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
ALERTMANAGER_URL="http://localhost:9093"
SCRIPT="scripts/prometheus_config.py"
RULES_DIR="/etc/prometheus/rules"
```

## 1. 生成告警规则文件

### 服务可用性告警

```bash
# 生成实例宕机告警规则
python3 $SCRIPT --action create-alert-rule \
  --output "$RULES_DIR/service_availability.yml" \
  --group-name "service_availability" \
  --alert-name "InstanceDown" \
  --expr 'up == 0' \
  --for "3m" \
  --severity "critical" \
  --summary '{{ $labels.instance }} 的 {{ $labels.job }} 服务已宕机' \
  --description '{{ $labels.instance }} 已超过 3 分钟无法访问'
```

### 资源使用率告警

```bash
# 生成 CPU 使用率过高告警
python3 $SCRIPT --action create-alert-rule \
  --output "$RULES_DIR/resource_alerts.yml" \
  --group-name "resource_alerts" \
  --alert-name "HighCPUUsage" \
  --expr '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80' \
  --for "10m" \
  --severity "warning" \
  --summary '{{ $labels.instance }} CPU 使用率过高' \
  --description 'CPU 使用率已达 {{ $value | printf "%.1f" }}%，持续超过 10 分钟'
```

### 请求错误率告警

```bash
# 生成错误率过高告警
python3 $SCRIPT --action create-alert-rule \
  --output "$RULES_DIR/request_alerts.yml" \
  --group-name "request_alerts" \
  --alert-name "HighErrorRate" \
  --expr 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (job) / sum(rate(http_requests_total[5m])) by (job) > 0.05' \
  --for "5m" \
  --severity "critical" \
  --summary '{{ $labels.job }} 错误率过高' \
  --description '{{ $labels.job }} 的 5xx 错误率已达 {{ $value | printf "%.2f" }}（阈值 5%）'
```

## 2. 使用预设模板生成规则

```bash
# 使用内置模板生成一组常用告警规则
python3 $SCRIPT --action generate-alert-rules \
  --template "standard" \
  --output "$RULES_DIR/standard_alerts.yml"

# 使用 Kubernetes 模板
python3 $SCRIPT --action generate-alert-rules \
  --template "kubernetes" \
  --output "$RULES_DIR/k8s_alerts.yml"

# 使用基础设施模板
python3 $SCRIPT --action generate-alert-rules \
  --template "infrastructure" \
  --output "$RULES_DIR/infra_alerts.yml"
```

## 3. 验证规则文件

```bash
# 验证单个规则文件
python3 $SCRIPT --action validate-rules \
  --rules-file "$RULES_DIR/service_availability.yml"

# 验证目录下所有规则文件
python3 $SCRIPT --action validate-rules \
  --rules-dir "$RULES_DIR"
```

## 4. 查看当前规则

```bash
# 查看 Prometheus 上所有规则
python3 $SCRIPT --url "$PROM_URL" --action list-rules

# 仅查看告警规则
python3 $SCRIPT --url "$PROM_URL" --action list-rules --rule-type alert

# 仅查看 Recording Rules
python3 $SCRIPT --url "$PROM_URL" --action list-rules --rule-type record
```

## 5. 查看活跃告警

```bash
# 查看所有活跃告警
python3 $SCRIPT --url "$PROM_URL" --action list-alerts

# 通过 Alertmanager 查看告警
python3 $SCRIPT --url "$ALERTMANAGER_URL" --action list-am-alerts
```

## 6. 重载配置

```bash
# 热加载 Prometheus 配置（需启动时添加 --web.enable-lifecycle）
python3 $SCRIPT --url "$PROM_URL" --action reload
```

## 7. 管理 Alertmanager 静默

```bash
# 创建静默（抑制特定告警通知）
python3 $SCRIPT --url "$ALERTMANAGER_URL" --action create-silence \
  --alertname "HighCPU" \
  --instance "app1:9090" \
  --duration "6h" \
  --comment "计划维护窗口"

# 查看所有静默
python3 $SCRIPT --url "$ALERTMANAGER_URL" --action list-silences

# 删除静默
python3 $SCRIPT --url "$ALERTMANAGER_URL" --action delete-silence \
  --silence-id "<silence_id>"
```

## 8. 向规则文件追加规则

```bash
# 向已有规则文件追加新规则
python3 $SCRIPT --action append-alert-rule \
  --rules-file "$RULES_DIR/resource_alerts.yml" \
  --group-name "resource_alerts" \
  --alert-name "HighMemoryUsage" \
  --expr '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85' \
  --for "10m" \
  --severity "warning" \
  --summary '{{ $labels.instance }} 内存使用率过高' \
  --description '内存使用率已达 {{ $value | printf "%.1f" }}%'
```
