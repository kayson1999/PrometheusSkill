#!/usr/bin/env python3
"""prometheus_query.py - Prometheus 监控数据查询工具

支持即时查询、范围查询、目标状态查看、告警查看、标签查询等功能。
无需额外依赖，仅使用 Python 标准库。

用法:
    python3 prometheus_query.py --url http://localhost:9090 --query 'up'
    python3 prometheus_query.py --url http://localhost:9090 --query 'rate(http_requests_total[5m])' --mode range --range 1h
    python3 prometheus_query.py --url http://localhost:9090 --mode targets
    python3 prometheus_query.py --url http://localhost:9090 --mode alerts
    python3 prometheus_query.py --url http://localhost:9090 --mode labels --label job

    # 带认证的查询
    python3 prometheus_query.py --url http://prom:9090 --username admin --password secret --query 'up'
    # 交互式输入密码（不在命令行暴露密码）
    python3 prometheus_query.py --url http://prom:9090 --username admin --query 'up'
"""

import argparse
import base64
import getpass
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime


# ============================================================
# 全局认证状态
# ============================================================

_auth_header = None  # 缓存的 Authorization 请求头


def build_auth_header(username: str, password: str) -> str:
    """构建 HTTP Basic Auth 请求头值"""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return f"Basic {encoded}"


def prompt_for_credentials() -> tuple:
    """交互式提示用户输入 Prometheus 登录账号和密码
    
    Returns:
        (username, password) 元组
    """
    print("\n🔐 Prometheus 需要认证，请输入登录凭据：", file=sys.stderr)
    username = input("   账号: ").strip()
    if not username:
        print("错误: 账号不能为空", file=sys.stderr)
        sys.exit(1)
    password = getpass.getpass("   密码: ").strip()
    if not password:
        print("错误: 密码不能为空", file=sys.stderr)
        sys.exit(1)
    return username, password


def init_auth(username: str = None, password: str = None):
    """初始化认证信息
    
    - 如果提供了 username 但没有 password，交互式提示输入密码
    - 如果都提供了，直接构建认证头
    - 如果都没提供，不设置认证
    """
    global _auth_header
    if username:
        if not password:
            print(f"\n🔐 已指定账号 '{username}'，请输入密码：", file=sys.stderr)
            password = getpass.getpass("   密码: ").strip()
            if not password:
                print("错误: 密码不能为空", file=sys.stderr)
                sys.exit(1)
        _auth_header = build_auth_header(username, password)


def handle_auth_error(http_code: int, url: str) -> bool:
    """处理认证错误（401/403），提示用户输入凭据并重试
    
    Args:
        http_code: HTTP 状态码
        url: 请求的 URL
    
    Returns:
        True 表示已获取新凭据可以重试，False 表示放弃
    """
    global _auth_header
    if http_code == 401:
        print(f"\n⚠️  Prometheus 返回 401 Unauthorized，需要登录认证。", file=sys.stderr)
    elif http_code == 403:
        print(f"\n⚠️  Prometheus 返回 403 Forbidden，当前凭据无权限或未提供认证。", file=sys.stderr)
    else:
        return False
    
    try:
        username, password = prompt_for_credentials()
        _auth_header = build_auth_header(username, password)
        return True
    except (KeyboardInterrupt, EOFError):
        print("\n已取消认证。", file=sys.stderr)
        return False


def parse_duration(duration_str: str) -> int:
    """解析时间范围字符串为秒数
    
    支持格式: 30s, 5m, 1h, 24h, 7d
    """
    if not duration_str:
        return 3600  # 默认 1 小时
    unit = duration_str[-1].lower()
    try:
        value = int(duration_str[:-1])
    except ValueError:
        return 3600
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return value * multipliers.get(unit, 3600)


def parse_time_string(time_str: str) -> float:
    """解析时间字符串为 Unix 时间戳
    
    支持格式:
    - Unix 时间戳: 1711500000
    - 日期: 2024-03-27
    - 日期时间: 2024-03-27 10:00:00 或 2024-03-27T10:00:00
    - 日期时间带时区: 2024-03-27T10:00:00Z
    
    Returns:
        Unix 时间戳（float）
    """
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # 尝试解析为纯数字（Unix 时间戳）
    try:
        ts = float(time_str)
        return ts
    except ValueError:
        pass
    
    # 去掉末尾的 Z（UTC 标记），统一按本地时间处理
    time_str = time_str.rstrip('Z').rstrip('z')
    # 将 T 分隔符替换为空格
    time_str = time_str.replace('T', ' ')
    
    # 尝试多种日期时间格式
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.timestamp()
        except ValueError:
            continue
    
    print(f"错误: 无法解析时间字符串 '{time_str}'", file=sys.stderr)
    print("支持的格式: Unix时间戳, YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, YYYY-MM-DDTHH:MM:SSZ", file=sys.stderr)
    sys.exit(1)


def resolve_time_range(args) -> tuple:
    """根据 --start、--end、--range 参数解析出查询的起止时间
    
    优先级规则:
    1. 同时指定 --start 和 --end：使用指定的绝对时间范围
    2. 仅指定 --start（无 --end）：
       - 如果 --start 是纯日期（无时分秒），则查询该天全天（00:00:00 ~ 23:59:59）
       - 否则 end = start + range
    3. 仅指定 --end（无 --start）：start = end - range
    4. 都不指定：end = now, start = now - range
    
    Returns:
        (start_ts, end_ts, duration_sec, time_desc) 元组
        time_desc 是人类可读的时间范围描述
    """
    now = time.time()
    duration_sec = parse_duration(args.range)
    
    has_start = hasattr(args, 'start') and args.start
    has_end = hasattr(args, 'end') and args.end
    
    if has_start and has_end:
        # 情况 1：同时指定了 start 和 end
        start_ts = parse_time_string(args.start)
        end_ts = parse_time_string(args.end)
        if start_ts >= end_ts:
            print("错误: --start 必须早于 --end", file=sys.stderr)
            sys.exit(1)
        duration_sec = end_ts - start_ts
        start_dt = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d %H:%M:%S')
        end_dt = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d %H:%M:%S')
        time_desc = f"{start_dt} ~ {end_dt}"
    elif has_start and not has_end:
        # 情况 2：仅指定 start
        start_ts = parse_time_string(args.start)
        start_str = args.start.strip().rstrip('Z').rstrip('z').replace('T', ' ')
        # 判断是否为纯日期格式（无时分秒）
        is_date_only = False
        for fmt in ['%Y-%m-%d', '%Y/%m/%d']:
            try:
                datetime.strptime(start_str, fmt)
                is_date_only = True
                break
            except ValueError:
                continue
        if is_date_only:
            # 纯日期：查询该天全天 00:00:00 ~ 23:59:59
            end_ts = start_ts + 86400 - 1  # 23:59:59
            duration_sec = 86400
            date_str = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
            time_desc = f"{date_str} 全天"
        else:
            # 有时分秒：end = start + range
            end_ts = start_ts + duration_sec
            start_dt = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d %H:%M:%S')
            end_dt = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d %H:%M:%S')
            time_desc = f"{start_dt} ~ {end_dt}（start + {args.range}）"
    elif has_end and not has_start:
        # 情况 3：仅指定 end
        end_ts = parse_time_string(args.end)
        start_ts = end_ts - duration_sec
        end_dt = datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d %H:%M:%S')
        time_desc = f"{args.range} before {end_dt}"
    else:
        # 情况 4：都不指定，使用 now - range ~ now
        end_ts = now
        start_ts = end_ts - duration_sec
        time_desc = f"最近 {args.range}"
    
    return start_ts, end_ts, duration_sec, time_desc


def auto_step(duration_seconds: int) -> str:
    """根据查询时间范围自动计算合适的 step"""
    if duration_seconds <= 300:       # <= 5 分钟
        return '15s'
    elif duration_seconds <= 3600:    # <= 1 小时
        return '60s'
    elif duration_seconds <= 21600:   # <= 6 小时
        return '120s'
    elif duration_seconds <= 86400:   # <= 24 小时
        return '300s'
    elif duration_seconds <= 604800:  # <= 7 天
        return '1800s'
    else:                             # > 7 天
        return '3600s'


def http_get(url: str, timeout: int = 30, _retry_auth: bool = True) -> dict:
    """发送 HTTP GET 请求并返回 JSON 响应
    
    支持 Basic Auth 认证。当收到 401/403 时，交互式提示用户输入凭据并自动重试。
    """
    try:
        headers = {'Accept': 'application/json'}
        if _auth_header:
            headers['Authorization'] = _auth_header
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        # 认证失败时提示用户输入凭据并重试
        if e.code in (401, 403) and _retry_auth:
            if handle_auth_error(e.code, url):
                return http_get(url, timeout=timeout, _retry_auth=False)
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP 错误 {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"连接错误: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("响应解析错误: 非 JSON 格式", file=sys.stderr)
        sys.exit(1)


def http_post(url: str, data: dict, timeout: int = 30, _retry_auth: bool = True) -> dict:
    """发送 HTTP POST 请求并返回 JSON 响应
    
    支持 Basic Auth 认证。当收到 401/403 时，交互式提示用户输入凭据并自动重试。
    """
    try:
        encoded = urllib.parse.urlencode(data).encode('utf-8')
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        if _auth_header:
            headers['Authorization'] = _auth_header
        req = urllib.request.Request(url, data=encoded, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        # 认证失败时提示用户输入凭据并重试
        if e.code in (401, 403) and _retry_auth:
            if handle_auth_error(e.code, url):
                return http_post(url, data, timeout=timeout, _retry_auth=False)
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP 错误 {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"连接错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def query_instant(base_url: str, query: str, time_val: float = None) -> dict:
    """即时查询 - 获取某个时间点的指标值"""
    params = {'query': query}
    if time_val:
        params['time'] = str(time_val)
    return http_post(f"{base_url}/api/v1/query", params)


def query_range(base_url: str, query: str, start: float, end: float, step: str) -> dict:
    """范围查询 - 获取时间段内的指标变化趋势"""
    params = {
        'query': query,
        'start': str(start),
        'end': str(end),
        'step': step,
    }
    return http_post(f"{base_url}/api/v1/query_range", params)


def query_series(base_url: str, match: str, start: float = None, end: float = None) -> dict:
    """查找匹配的时间序列"""
    params = {'match[]': match}
    if start:
        params['start'] = str(start)
    if end:
        params['end'] = str(end)
    url = f"{base_url}/api/v1/series?{urllib.parse.urlencode(params)}"
    return http_get(url)


def query_targets(base_url: str) -> dict:
    """查询抓取目标状态"""
    return http_get(f"{base_url}/api/v1/targets")


def query_alerts(base_url: str) -> dict:
    """查询活跃告警"""
    return http_get(f"{base_url}/api/v1/alerts")


def query_rules(base_url: str) -> dict:
    """查询告警和 Recording Rules"""
    return http_get(f"{base_url}/api/v1/rules")


def query_labels(base_url: str) -> dict:
    """获取所有标签名"""
    return http_get(f"{base_url}/api/v1/labels")


def query_label_values(base_url: str, label: str) -> dict:
    """获取某标签的所有值"""
    return http_get(f"{base_url}/api/v1/label/{label}/values")


def query_metadata(base_url: str, metric: str = None) -> dict:
    """查看指标元数据"""
    url = f"{base_url}/api/v1/metadata"
    if metric:
        url += f"?metric={urllib.parse.quote(metric)}"
    return http_get(url)


# ============================================================
# 图表生成（自包含 HTML + ECharts CDN，零额外依赖）
# ============================================================

CHART_HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #1a1a2e; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont,
    'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    padding: 20px;
  }}
  .header {{
    text-align: center; padding: 20px 0 10px;
  }}
  .header h1 {{
    font-size: 22px; color: #00d4ff; margin-bottom: 6px;
  }}
  .header .meta {{
    font-size: 13px; color: #888;
  }}
  #chart-container {{
    width: 100%; height: 500px; margin: 20px auto;
    background: #16213e; border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    padding: 10px;
  }}
  .stats-grid {{
    display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;
    margin: 20px auto; max-width: 1200px;
  }}
  .stat-card {{
    background: #16213e; border-radius: 8px; padding: 16px 24px;
    min-width: 180px; text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
  }}
  .stat-card .label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
  .stat-card .value {{ font-size: 20px; font-weight: bold; color: #00d4ff; }}
  .footer {{
    text-align: center; padding: 20px 0; font-size: 12px; color: #555;
  }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 {title}</h1>
  <div class="meta">{query_info}</div>
</div>
<div id="chart-container"></div>
<div class="stats-grid" id="stats-grid"></div>
<div class="footer">
  Prometheus 监控数据查询工具 | 生成时间: {gen_time}
</div>
<script>
var chartData = {chart_data_json};

// 渲染图表
var chart = echarts.init(document.getElementById('chart-container'), 'dark');
var series = [];
var legendData = [];

chartData.series.forEach(function(s) {{
  legendData.push(s.name);
  series.push({{
    name: s.name,
    type: 'line',
    smooth: true,
    symbol: 'none',
    lineStyle: {{ width: 2 }},
    areaStyle: {{ opacity: chartData.series.length === 1 ? 0.15 : 0.05 }},
    data: s.data
  }});
}});

var option = {{
  backgroundColor: 'transparent',
  tooltip: {{
    trigger: 'axis',
    backgroundColor: 'rgba(22,33,62,0.95)',
    borderColor: '#00d4ff',
    textStyle: {{ color: '#e0e0e0', fontSize: 12 }},
    formatter: function(params) {{
      var time = params[0].axisValueLabel;
      var lines = '<div style="font-weight:bold;margin-bottom:4px">' + time + '</div>';
      params.forEach(function(p) {{
        var val = typeof p.value === 'number' ? p.value.toFixed(4) : p.value;
        lines += '<div>' + p.marker + ' ' + p.seriesName + ': <b>' + val + '</b></div>';
      }});
      return lines;
    }}
  }},
  legend: {{
    data: legendData,
    textStyle: {{ color: '#aaa', fontSize: 11 }},
    top: 10,
    type: legendData.length > 8 ? 'scroll' : 'plain'
  }},
  grid: {{ left: 60, right: 30, top: 50, bottom: 40 }},
  xAxis: {{
    type: 'category',
    data: chartData.timestamps,
    axisLabel: {{ color: '#888', fontSize: 11 }},
    axisLine: {{ lineStyle: {{ color: '#333' }} }},
    splitLine: {{ show: false }}
  }},
  yAxis: {{
    type: 'value',
    axisLabel: {{
      color: '#888', fontSize: 11,
      formatter: function(v) {{
        if (Math.abs(v) >= 1e9) return (v/1e9).toFixed(1) + 'G';
        if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(1) + 'M';
        if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(1) + 'K';
        return v.toFixed(2);
      }}
    }},
    axisLine: {{ lineStyle: {{ color: '#333' }} }},
    splitLine: {{ lineStyle: {{ color: '#222' }} }}
  }},
  dataZoom: [
    {{ type: 'inside', start: 0, end: 100 }},
    {{ type: 'slider', start: 0, end: 100, height: 20, bottom: 5,
      borderColor: '#333', fillerColor: 'rgba(0,212,255,0.15)',
      handleStyle: {{ color: '#00d4ff' }},
      textStyle: {{ color: '#888' }} }}
  ],
  series: series
}};
chart.setOption(option);
window.addEventListener('resize', function() {{ chart.resize(); }});

// 渲染统计卡片
var statsGrid = document.getElementById('stats-grid');
chartData.series.forEach(function(s) {{
  var vals = s.data.filter(function(v) {{ return v !== null && !isNaN(v); }});
  if (vals.length === 0) return;
  var min = Math.min.apply(null, vals);
  var max = Math.max.apply(null, vals);
  var avg = vals.reduce(function(a,b){{ return a+b; }}, 0) / vals.length;
  var latest = vals[vals.length - 1];
  var name = s.name.length > 30 ? s.name.substring(0, 30) + '...' : s.name;
  var html = '<div class="stat-card">' +
    '<div class="label">' + name + '</div>' +
    '<div class="value">' + latest.toFixed(4) + '</div>' +
    '<div class="label" style="margin-top:8px">最小: ' + min.toFixed(4) +
    ' | 最大: ' + max.toFixed(4) + ' | 平均: ' + avg.toFixed(4) + '</div></div>';
  statsGrid.innerHTML += html;
}});
</script>
</body>
</html>
"""


def generate_chart_html(query: str, time_desc: str, step: str, result: list, output_path: str = None, duration_sec: int = None) -> str:
    """将范围查询结果生成自包含的 HTML 图表文件
    
    Args:
        query: PromQL 查询表达式
        time_desc: 查询时间范围描述（如 "最近 1h", "2024-03-26 全天"）
        step: 查询步长
        result: Prometheus 范围查询返回的 result 数组
        output_path: 输出文件路径，为 None 时自动生成
        duration_sec: 查询时间跨度（秒），用于决定时间戳格式
    
    Returns:
        生成的 HTML 文件路径
    """
    if not result:
        print("错误: 查询无数据，无法生成图表", file=sys.stderr)
        sys.exit(1)
    
    # 如果未提供 duration_sec，从数据中推算
    if duration_sec is None:
        values = result[0].get('values', [])
        if len(values) >= 2:
            duration_sec = values[-1][0] - values[0][0]
        else:
            duration_sec = 3600
    
    # 提取时间戳（使用第一条序列的时间戳作为 X 轴）
    timestamps = []
    for ts, _ in result[0].get('values', []):
        dt = datetime.fromtimestamp(ts)
        timestamps.append(dt.strftime('%H:%M:%S') if duration_sec <= 86400 else dt.strftime('%m-%d %H:%M'))
    
    # 构建每条序列的数据
    series_data = []
    for item in result:
        metric = item.get('metric', {})
        # 生成简洁的序列名称
        label_parts = []
        for k, v in sorted(metric.items()):
            if k == '__name__':
                continue
            label_parts.append(f'{k}={v}')
        name = ', '.join(label_parts) if label_parts else metric.get('__name__', 'value')
        
        values = []
        for _, v in item.get('values', []):
            try:
                values.append(round(float(v), 6))
            except (ValueError, TypeError):
                values.append(None)
        
        series_data.append({
            'name': name,
            'data': values,
        })
    
    chart_data = {
        'timestamps': timestamps,
        'series': series_data,
    }
    
    # 生成标题
    title = f'Prometheus 监控 - {query[:80]}' if len(query) > 80 else f'Prometheus 监控 - {query}'
    query_info = f'PromQL: {query} | 范围: {time_desc} | 步长: {step} | 序列数: {len(result)}'
    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    html_content = CHART_HTML_TEMPLATE.format(
        title=title,
        query_info=query_info,
        gen_time=gen_time,
        chart_data_json=json.dumps(chart_data, ensure_ascii=False),
    )
    
    # 确定输出路径
    if not output_path:
        output_path = os.path.join('/tmp', f'prom_chart_{int(time.time())}.html')
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path


def format_instant_table(result: list) -> str:
    """将即时查询结果格式化为表格"""
    if not result:
        return "  (无数据)"
    lines = []
    for item in result:
        metric = item.get('metric', {})
        labels = ', '.join(f'{k}={v}' for k, v in sorted(metric.items()))
        ts, val = item['value']
        dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"  {labels:60s} | {dt} | {val}")
    return '\n'.join(lines)


def format_range_table(result: list) -> str:
    """将范围查询结果格式化为表格"""
    if not result:
        return "  (无数据)"
    lines = []
    for item in result:
        metric = item.get('metric', {})
        labels = ', '.join(f'{k}={v}' for k, v in sorted(metric.items()))
        values = item.get('values', [])
        if not values:
            lines.append(f"  {labels:60s} | 无数据点")
            continue
        first_ts = datetime.fromtimestamp(values[0][0]).strftime('%H:%M:%S')
        last_ts = datetime.fromtimestamp(values[-1][0]).strftime('%H:%M:%S')
        first_val = values[0][1]
        last_val = values[-1][1]
        # 计算最大值和最小值
        float_vals = []
        for _, v in values:
            try:
                float_vals.append(float(v))
            except (ValueError, TypeError):
                pass
        if float_vals:
            min_val = f"{min(float_vals):.4g}"
            max_val = f"{max(float_vals):.4g}"
            avg_val = f"{sum(float_vals)/len(float_vals):.4g}"
            lines.append(
                f"  {labels}\n"
                f"    数据点: {len(values)} | 时间: {first_ts} ~ {last_ts}\n"
                f"    最小: {min_val} | 最大: {max_val} | 平均: {avg_val} | 最新: {last_val}"
            )
        else:
            lines.append(
                f"  {labels}\n"
                f"    数据点: {len(values)} | 时间: {first_ts} ~ {last_ts} | 最新: {last_val}"
            )
    return '\n'.join(lines)


def cmd_instant(args):
    """执行即时查询"""
    if not args.query:
        print("错误: instant 模式需要 --query 参数", file=sys.stderr)
        sys.exit(1)
    data = query_instant(args.url, args.query)
    if data.get('status') != 'success':
        print(f"查询失败: {data.get('error', '未知错误')}", file=sys.stderr)
        sys.exit(1)
    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        result = data.get('data', {}).get('result', [])
        print(f"查询: {args.query}")
        print(f"类型: {data.get('data', {}).get('resultType', '?')}")
        print(f"结果数: {len(result)}")
        print(format_instant_table(result))


def cmd_range(args):
    """执行范围查询"""
    if not args.query:
        print("错误: range 模式需要 --query 参数", file=sys.stderr)
        sys.exit(1)
    start, end, duration_sec, time_desc = resolve_time_range(args)
    step = args.step if args.step != 'auto' else auto_step(duration_sec)
    data = query_range(args.url, args.query, start, end, step)
    if data.get('status') != 'success':
        print(f"查询失败: {data.get('error', '未知错误')}", file=sys.stderr)
        sys.exit(1)
    result = data.get('data', {}).get('result', [])
    if args.format == 'chart':
        # 图表模式：生成自包含 HTML 文件
        output_path = getattr(args, 'output', None)
        chart_path = generate_chart_html(args.query, time_desc, step, result, output_path, duration_sec)
        print(f"📊 图表已生成: {chart_path}")
        print(f"   查询: {args.query}")
        print(f"   范围: {time_desc}，步长 {step}，序列数: {len(result)}")
        print(f"   请在浏览器中打开查看交互式图表")
    elif args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"查询: {args.query}")
        print(f"范围: {time_desc}，步长 {step}")
        print(f"结果数: {len(result)}")
        print(format_range_table(result))


def cmd_targets(args):
    """查看抓取目标状态"""
    data = query_targets(args.url)
    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        active = data.get('data', {}).get('activeTargets', [])
        dropped = data.get('data', {}).get('droppedTargets', [])
        print(f"活跃目标: {len(active)} | 已丢弃: {len(dropped)}")
        print()
        # 按 health 分组统计
        health_count = {}
        for t in active:
            h = t.get('health', 'unknown')
            health_count[h] = health_count.get(h, 0) + 1
        print("健康状态统计:")
        for h, c in sorted(health_count.items()):
            print(f"  {h}: {c}")
        print()
        # 详细列表
        for t in sorted(active, key=lambda x: (x.get('health', ''), x.get('labels', {}).get('job', ''))):
            health = t.get('health', 'unknown')
            job = t.get('labels', {}).get('job', '?')
            instance = t.get('labels', {}).get('instance', '?')
            last_scrape = t.get('lastScrape', '?')
            error = t.get('lastError', '')
            status_icon = '✅' if health == 'up' else '❌'
            line = f"  {status_icon} [{health:6s}] {job:30s} {instance}"
            if error:
                line += f"  ⚠️ {error}"
            print(line)


def cmd_alerts(args):
    """查看活跃告警"""
    data = query_alerts(args.url)
    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        alerts = data.get('data', {}).get('alerts', [])
        print(f"活跃告警数: {len(alerts)}")
        if not alerts:
            print("  (无活跃告警)")
            return
        print()
        # 按 severity 分组
        by_severity = {}
        for a in alerts:
            sev = a.get('labels', {}).get('severity', 'unknown')
            by_severity.setdefault(sev, []).append(a)
        severity_order = ['critical', 'warning', 'info', 'unknown']
        for sev in severity_order:
            if sev not in by_severity:
                continue
            sev_alerts = by_severity[sev]
            icon = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(sev, '⚪')
            print(f"{icon} {sev.upper()} ({len(sev_alerts)}):")
            for a in sev_alerts:
                name = a.get('labels', {}).get('alertname', '?')
                state = a.get('state', '?')
                summary = a.get('annotations', {}).get('summary', '')
                print(f"    [{state:8s}] {name}")
                if summary:
                    print(f"              {summary}")
            print()


def cmd_labels(args):
    """查看标签信息"""
    if args.label:
        data = query_label_values(args.url, args.label)
        if args.format == 'json':
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            values = data.get('data', [])
            print(f"标签 '{args.label}' 的值 ({len(values)} 个):")
            for v in sorted(values):
                print(f"  - {v}")
    else:
        data = query_labels(args.url)
        if args.format == 'json':
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            labels = data.get('data', [])
            print(f"所有标签名 ({len(labels)} 个):")
            for l in sorted(labels):
                print(f"  - {l}")


def cmd_rules(args):
    """查看规则"""
    data = query_rules(args.url)
    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        groups = data.get('data', {}).get('groups', [])
        total_rules = sum(len(g.get('rules', [])) for g in groups)
        print(f"规则组: {len(groups)} | 总规则数: {total_rules}")
        print()
        for g in groups:
            name = g.get('name', '?')
            rules = g.get('rules', [])
            print(f"  📋 {name} ({len(rules)} 条规则):")
            for r in rules:
                rtype = r.get('type', '?')
                rname = r.get('name', '?')
                health = r.get('health', '?')
                icon = '📊' if rtype == 'recording' else '🔔'
                health_icon = '✅' if health == 'ok' else '❌'
                print(f"    {icon} {health_icon} [{rtype:9s}] {rname}")
            print()


def cmd_metadata(args):
    """查看指标元数据"""
    data = query_metadata(args.url, args.metric)
    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        metadata = data.get('data', {})
        if args.metric:
            entries = metadata.get(args.metric, [])
            print(f"指标: {args.metric}")
            for entry in entries:
                print(f"  类型: {entry.get('type', '?')}")
                print(f"  帮助: {entry.get('help', '?')}")
                print(f"  单位: {entry.get('unit', '(无)')}")
        else:
            print(f"指标总数: {len(metadata)}")
            for name in sorted(metadata.keys())[:50]:
                entries = metadata[name]
                mtype = entries[0].get('type', '?') if entries else '?'
                print(f"  [{mtype:9s}] {name}")
            if len(metadata) > 50:
                print(f"  ... 还有 {len(metadata) - 50} 个指标")


def cmd_series(args):
    """查找时间序列"""
    if not args.query:
        print("错误: series 模式需要 --query 参数（作为 match 表达式）", file=sys.stderr)
        sys.exit(1)
    start, end, duration_sec, time_desc = resolve_time_range(args)
    data = query_series(args.url, args.query, start, end)
    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        series = data.get('data', [])
        print(f"匹配 '{args.query}' 的时间序列: {len(series)}")
        for s in series[:50]:
            labels = ', '.join(f'{k}={v}' for k, v in sorted(s.items()))
            print(f"  {labels}")
        if len(series) > 50:
            print(f"  ... 还有 {len(series) - 50} 条")


def main():
    parser = argparse.ArgumentParser(
        description='Prometheus 监控数据查询工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看所有抓取目标状态
  %(prog)s --url http://localhost:9090 --mode targets

  # 查看当前活跃告警
  %(prog)s --url http://localhost:9090 --mode alerts

  # 即时查询 CPU 使用率
  %(prog)s --url http://localhost:9090 --query 'up'

  # 范围查询过去 6 小时的 QPS 趋势
  %(prog)s --url http://localhost:9090 --mode range --range 6h \\
    --query 'sum(rate(http_requests_total[5m]))'

  # 查看所有 job 名称
  %(prog)s --url http://localhost:9090 --mode labels --label job

  # 查看指标元数据
  %(prog)s --url http://localhost:9090 --mode metadata --metric http_requests_total

  # 生成 HTML 交互式图表（范围查询）
  %(prog)s --url http://localhost:9090 --mode range --range 6h \\
    --query 'sum(rate(http_requests_total[5m]))' --format chart

  # 指定图表输出路径
  %(prog)s --url http://localhost:9090 --mode range --range 1h \\
    --query 'sum by (job) (rate(http_requests_total[5m]))' \\
    --format chart --output /tmp/qps-chart.html

  # 查询指定日期的全天数据（自动设为 00:00:00 ~ 23:59:59）
  %(prog)s --url http://localhost:9090 --mode range \\
    --start '2024-03-26' \\
    --query 'sum(rate(http_requests_total[5m]))' --format chart

  # 查询指定时间范围的数据
  %(prog)s --url http://localhost:9090 --mode range \\
    --start '2024-03-26 10:00:00' --end '2024-03-26 18:00:00' \\
    --query 'sum(rate(http_requests_total[5m]))' --format chart

  # 查询某个时间点之前 2 小时的数据
  %(prog)s --url http://localhost:9090 --mode range --range 2h \\
    --end '2024-03-26 18:00:00' \\
    --query 'sum(rate(http_requests_total[5m]))'

  # 带认证的查询（直接指定密码）
  %(prog)s --url http://prom:9090 --username admin --password secret --query 'up'

  # 带认证的查询（交互式输入密码，更安全）
  %(prog)s --url http://prom:9090 --username admin --query 'up'

  # 未指定认证时，若服务端返回 401/403 会自动提示输入账号密码
        """
    )
    parser.add_argument('--url', '-u', required=True,
                        help='Prometheus 地址，如 http://localhost:9090')
    parser.add_argument('--query', '-q',
                        help='PromQL 查询表达式')
    parser.add_argument('--range', '-r', default='1h',
                        help='查询时间范围，如 5m/1h/24h/7d（默认 1h）。与 --start/--end 配合使用时作为补充')
    parser.add_argument('--start', default=None,
                        help='查询起始时间。支持格式: Unix时间戳(1711500000)、日期(2024-03-27)、日期时间(2024-03-27 10:00:00 或 2024-03-27T10:00:00Z)。'
                             '仅指定 --start 为纯日期时，自动查询该天全天数据')
    parser.add_argument('--end', default=None,
                        help='查询结束时间。格式同 --start。未指定时默认为当前时间')
    parser.add_argument('--step', '-s', default='auto',
                        help='查询步长，如 15s/60s/300s（默认 auto 自动计算）')
    parser.add_argument('--format', '-f', choices=['json', 'table', 'chart'], default='table',
                        help='输出格式: table(文本表格) / json(JSON) / chart(HTML图表)（默认 table）')
    parser.add_argument('--output', '-o',
                        help='图表输出文件路径（仅 chart 格式有效，默认 /tmp/prom_chart_<timestamp>.html）')
    parser.add_argument('--mode', '-m',
                        choices=['instant', 'range', 'targets', 'alerts', 'labels',
                                 'rules', 'metadata', 'series'],
                        default='instant',
                        help='查询模式（默认 instant）')
    parser.add_argument('--label', '-l',
                        help='标签名（用于 labels 模式查询特定标签的值）')
    parser.add_argument('--metric',
                        help='指标名（用于 metadata 模式查询特定指标的元数据）')
    parser.add_argument('--username', '-U',
                        help='Prometheus 登录账号（Basic Auth 用户名）')
    parser.add_argument('--password', '-P',
                        help='Prometheus 登录密码（Basic Auth 密码，未指定时交互式输入）')
    parser.add_argument('--timeout', '-t', type=int, default=30,
                        help='请求超时时间（秒，默认 30）')

    args = parser.parse_args()
    args.url = args.url.rstrip('/')

    # 初始化认证信息
    init_auth(args.username, args.password)

    mode_handlers = {
        'instant': cmd_instant,
        'range': cmd_range,
        'targets': cmd_targets,
        'alerts': cmd_alerts,
        'labels': cmd_labels,
        'rules': cmd_rules,
        'metadata': cmd_metadata,
        'series': cmd_series,
    }

    handler = mode_handlers.get(args.mode)
    if handler:
        handler(args)
    else:
        print(f"未知模式: {args.mode}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
