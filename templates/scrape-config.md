# Prometheus 抓取规则配置模板

> **用途**：创建和管理 Prometheus 抓取配置，包括静态目标、文件服务发现、配置验证和热加载
> **使用**：修改 `PROM_URL` 和配置参数后复制命令执行

## 配置区

```bash
PROM_URL="http://localhost:9090"
SCRIPT="scripts/prometheus_config.py"
CONFIG_FILE="/etc/prometheus/prometheus.yml"
TARGETS_DIR="/etc/prometheus/targets"
```

## 1. 生成抓取配置

### 静态目标配置

```bash
# 生成 Node Exporter 抓取配置
python3 $SCRIPT --action create-scrape-config \
  --output "$CONFIG_FILE" \
  --job-name "node-exporter" \
  --targets "node1:9100,node2:9100,node3:9100" \
  --scrape-interval "30s" \
  --labels "env=production,dc=guangzhou"

# 生成应用服务抓取配置
python3 $SCRIPT --action create-scrape-config \
  --output "$CONFIG_FILE" \
  --job-name "my-app" \
  --targets "app1:8080,app2:8080" \
  --metrics-path "/actuator/prometheus" \
  --scrape-interval "15s" \
  --labels "service=user-service,env=production"
```

### 带认证的抓取配置

```bash
# 生成带 Basic Auth 的抓取配置
python3 $SCRIPT --action create-scrape-config \
  --output "$CONFIG_FILE" \
  --job-name "secured-app" \
  --targets "secure-app:8443" \
  --scheme "https" \
  --basic-auth-user "prometheus" \
  --basic-auth-pass "secret" \
  --tls-skip-verify
```

## 2. 生成文件服务发现目标

```bash
# 生成 JSON 格式的目标文件
python3 $SCRIPT --action create-file-sd-targets \
  --output "$TARGETS_DIR/my-app.json" \
  --targets "app1:8080,app2:8080,app3:8080" \
  --labels "job=my-app,env=production,service=user-service"

# 生成 YAML 格式的目标文件
python3 $SCRIPT --action create-file-sd-targets \
  --output "$TARGETS_DIR/my-app.yml" \
  --targets "app1:8080,app2:8080" \
  --labels "job=my-app,env=production"
```

## 3. 使用预设模板生成配置

```bash
# 生成基础设施监控配置（Prometheus + Node + cAdvisor）
python3 $SCRIPT --action generate-scrape-config \
  --template "infrastructure" \
  --output "$CONFIG_FILE"

# 生成中间件监控配置（Redis + MySQL + Kafka + Nginx）
python3 $SCRIPT --action generate-scrape-config \
  --template "middleware" \
  --output "$CONFIG_FILE"

# 生成 Blackbox 探针监控配置
python3 $SCRIPT --action generate-scrape-config \
  --template "blackbox" \
  --output "$CONFIG_FILE" \
  --probe-targets "https://example.com,https://api.example.com/health"
```

## 4. 查看当前抓取目标

```bash
# 查看所有抓取目标状态
python3 $SCRIPT --url "$PROM_URL" --action list-targets

# 仅查看活跃目标
python3 $SCRIPT --url "$PROM_URL" --action list-targets --state active

# 仅查看已丢弃的目标
python3 $SCRIPT --url "$PROM_URL" --action list-targets --state dropped

# 按 job 过滤
python3 $SCRIPT --url "$PROM_URL" --action list-targets --job "my-app"
```

## 5. 查看当前配置

```bash
# 查看 Prometheus 当前加载的完整配置
python3 $SCRIPT --url "$PROM_URL" --action show-config

# 仅查看 scrape_configs 部分
python3 $SCRIPT --url "$PROM_URL" --action show-config --section scrape_configs
```

## 6. 验证配置

```bash
# 验证 Prometheus 主配置文件
python3 $SCRIPT --action validate-config \
  --config-file "$CONFIG_FILE"
```

## 7. 重载配置

```bash
# 热加载 Prometheus 配置
python3 $SCRIPT --url "$PROM_URL" --action reload
```

## 8. 向已有配置追加抓取任务

```bash
# 向已有 prometheus.yml 追加新的 scrape_config
python3 $SCRIPT --action append-scrape-config \
  --config-file "$CONFIG_FILE" \
  --job-name "new-service" \
  --targets "new-svc1:8080,new-svc2:8080" \
  --scrape-interval "15s" \
  --labels "env=production"
```
