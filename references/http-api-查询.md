# Prometheus HTTP API 查询

## API 端点概览

Prometheus 提供 RESTful HTTP API 用于查询监控数据。所有查询 API 的基础路径为 `/api/v1/`。

| API 端点 | 方法 | 用途 |
|----------|------|------|
| `/api/v1/query` | GET/POST | 即时查询（当前时刻的指标值） |
| `/api/v1/query_range` | GET/POST | 范围查询（时间段内的指标变化） |
| `/api/v1/series` | GET/POST | 查找匹配的时间序列 |
| `/api/v1/labels` | GET/POST | 获取所有标签名 |
| `/api/v1/label/<label_name>/values` | GET | 获取某标签的所有值 |
| `/api/v1/targets` | GET | 查看抓取目标状态 |
| `/api/v1/alerts` | GET | 查看当前活跃告警 |
| `/api/v1/rules` | GET | 查看告警和 Recording Rules |
| `/api/v1/metadata` | GET | 查看指标元数据 |
| `/api/v1/status/config` | GET | 查看当前配置 |

## 即时查询（Instant Query）

获取某个时间点的指标值：

```bash
# 基本格式
curl -s 'http://<prometheus_host>:9090/api/v1/query' \
  --data-urlencode 'query=<PromQL表达式>' \
  --data-urlencode 'time=<时间戳>'

# 示例：查询所有目标的 up 状态
curl -s 'http://localhost:9090/api/v1/query?query=up'

# 示例：查询某 job 的 CPU 使用率
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'

# 示例：查询某 job 的请求 QPS
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{job="my-app"}[5m]))'

# 示例：查询某 job 的错误率
curl -s 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=sum(rate(http_requests_total{job="my-app",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="my-app"}[5m]))'
```

**响应格式：**

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": { "instance": "app1:9090", "job": "my-app" },
        "value": [1711500000, "0.85"]
      }
    ]
  }
}
```

## 范围查询（Range Query）

获取时间段内的指标变化趋势：

```bash
# 基本格式
curl -s 'http://<prometheus_host>:9090/api/v1/query_range' \
  --data-urlencode 'query=<PromQL表达式>' \
  --data-urlencode 'start=<开始时间>' \
  --data-urlencode 'end=<结束时间>' \
  --data-urlencode 'step=<步长>'

# 示例：查询过去 1 小时的 CPU 使用率趋势（每分钟一个点）
curl -s 'http://localhost:9090/api/v1/query_range' \
  --data-urlencode 'query=100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)' \
  --data-urlencode "start=$(date -d '1 hour ago' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode 'step=60s'

# 示例：查询过去 24 小时的请求量趋势（每 5 分钟一个点）
curl -s 'http://localhost:9090/api/v1/query_range' \
  --data-urlencode 'query=sum(rate(http_requests_total{job="my-app"}[5m]))' \
  --data-urlencode "start=$(date -d '24 hours ago' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode 'step=300s'
```

**响应格式：**

```json
{
  "status": "success",
  "data": {
    "resultType": "matrix",
    "result": [
      {
        "metric": { "instance": "app1:9090" },
        "values": [
          [1711496400, "45.2"],
          [1711496460, "47.8"],
          [1711496520, "43.1"]
        ]
      }
    ]
  }
}
```

## 时间参数说明

| 格式 | 示例 | 说明 |
|------|------|------|
| Unix 时间戳 | `1711500000` | 精确到秒 |
| RFC3339 | `2024-03-27T10:00:00Z` | ISO 格式 |
| 相对时间（shell） | `$(date -d '1 hour ago' +%s)` | 通过 shell 计算 |

**step 步长建议：**

| 查询时间范围 | 推荐 step |
|-------------|-----------|
| 最近 5 分钟 | 15s |
| 最近 1 小时 | 60s |
| 最近 6 小时 | 120s |
| 最近 24 小时 | 300s |
| 最近 7 天 | 1800s |
| 最近 30 天 | 3600s |

## 查找时间序列和标签

```bash
# 查找匹配的时间序列
curl -s 'http://localhost:9090/api/v1/series' \
  --data-urlencode 'match[]=http_requests_total{job="my-app"}' \
  --data-urlencode "start=$(date -d '1 hour ago' +%s)" \
  --data-urlencode "end=$(date +%s)"

# 获取所有标签名
curl -s 'http://localhost:9090/api/v1/labels'

# 获取某标签的所有值（如获取所有 job 名称）
curl -s 'http://localhost:9090/api/v1/label/job/values'

# 获取某标签的所有值（如获取所有 instance）
curl -s 'http://localhost:9090/api/v1/label/instance/values'

# 查看指标元数据
curl -s 'http://localhost:9090/api/v1/metadata?metric=http_requests_total'
```

## 查看目标和告警状态

```bash
# 查看所有抓取目标状态
curl -s 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[] | {job: .labels.job, instance: .labels.instance, health: .health}'

# 查看当前活跃告警
curl -s 'http://localhost:9090/api/v1/alerts' | jq '.data.alerts[] | {alertname: .labels.alertname, state: .state, severity: .labels.severity}'

# 查看所有规则（告警 + Recording）
curl -s 'http://localhost:9090/api/v1/rules' | jq '.data.groups[].rules[] | {name: .name, type: .type, health: .health}'
```
