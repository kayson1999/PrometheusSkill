#!/usr/bin/env python3
"""prometheus_config.py - Prometheus 配置管理工具

支持告警规则创建/管理、抓取配置创建/管理、配置验证、热加载、Alertmanager 静默管理等功能。
无需额外依赖，仅使用 Python 标准库。

用法:
    # 告警规则管理
    python3 prometheus_config.py --action create-alert-rule --output /tmp/rules.yml \
      --group-name "test" --alert-name "HighCPU" --expr 'cpu > 80' --for 5m --severity warning
    python3 prometheus_config.py --action generate-alert-rules --template standard --output /tmp/rules.yml
    python3 prometheus_config.py --action validate-rules --rules-file /tmp/rules.yml
    python3 prometheus_config.py --url http://localhost:9090 --action list-rules
    python3 prometheus_config.py --url http://localhost:9090 --action list-alerts

    # 抓取配置管理
    python3 prometheus_config.py --action create-scrape-config --output /tmp/scrape.yml \
      --job-name "my-app" --targets "app1:8080,app2:8080"
    python3 prometheus_config.py --action create-file-sd-targets --output /tmp/targets.json \
      --targets "app1:8080,app2:8080" --labels "job=my-app,env=prod"
    python3 prometheus_config.py --url http://localhost:9090 --action list-targets

    # 配置热加载
    python3 prometheus_config.py --url http://localhost:9090 --action reload

    # Alertmanager 静默管理
    python3 prometheus_config.py --url http://localhost:9093 --action create-silence \
      --alertname "HighCPU" --duration 6h --comment "维护窗口"
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
from datetime import datetime, timedelta


# ============================================================
# 全局认证状态（复用 prometheus_query.py 的认证模式）
# ============================================================

_auth_header = None


def build_auth_header(username: str, password: str) -> str:
    """构建 HTTP Basic Auth 请求头值"""
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return f"Basic {encoded}"


def init_auth(username: str = None, password: str = None):
    """初始化认证信息"""
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
    """处理认证错误"""
    global _auth_header
    if http_code == 401:
        print(f"\n⚠️  服务返回 401 Unauthorized，需要登录认证。", file=sys.stderr)
    elif http_code == 403:
        print(f"\n⚠️  服务返回 403 Forbidden，当前凭据无权限或未提供认证。", file=sys.stderr)
    else:
        return False
    try:
        print("\n🔐 请输入登录凭据：", file=sys.stderr)
        username = input("   账号: ").strip()
        if not username:
            print("错误: 账号不能为空", file=sys.stderr)
            return False
        password = getpass.getpass("   密码: ").strip()
        if not password:
            print("错误: 密码不能为空", file=sys.stderr)
            return False
        _auth_header = build_auth_header(username, password)
        return True
    except (KeyboardInterrupt, EOFError):
        print("\n已取消认证。", file=sys.stderr)
        return False


# ============================================================
# HTTP 工具函数
# ============================================================

def http_get(url: str, timeout: int = 30, _retry_auth: bool = True) -> dict:
    """发送 HTTP GET 请求并返回 JSON 响应"""
    try:
        headers = {'Accept': 'application/json'}
        if _auth_header:
            headers['Authorization'] = _auth_header
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
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


def http_post(url: str, data=None, json_data=None, timeout: int = 30, _retry_auth: bool = True):
    """发送 HTTP POST 请求"""
    try:
        headers = {'Accept': 'application/json'}
        if _auth_header:
            headers['Authorization'] = _auth_header

        if json_data is not None:
            encoded = json.dumps(json_data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif data is not None:
            encoded = urllib.parse.urlencode(data).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            encoded = b''

        req = urllib.request.Request(url, data=encoded, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
            if body:
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {'status': 'success', 'message': body}
            return {'status': 'success'}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and _retry_auth:
            if handle_auth_error(e.code, url):
                return http_post(url, data=data, json_data=json_data, timeout=timeout, _retry_auth=False)
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP 错误 {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"连接错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


def http_delete(url: str, timeout: int = 30, _retry_auth: bool = True):
    """发送 HTTP DELETE 请求"""
    try:
        headers = {'Accept': 'application/json'}
        if _auth_header:
            headers['Authorization'] = _auth_header
        req = urllib.request.Request(url, headers=headers, method='DELETE')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
            if body:
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {'status': 'success', 'message': body}
            return {'status': 'success'}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and _retry_auth:
            if handle_auth_error(e.code, url):
                return http_delete(url, timeout=timeout, _retry_auth=False)
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP 错误 {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"连接错误: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ============================================================
# YAML 简易序列化（零依赖，不使用 PyYAML）
# ============================================================

def yaml_dump_value(value, indent=0):
    """将 Python 值序列化为 YAML 字符串片段"""
    prefix = '  ' * indent
    if isinstance(value, str):
        # 包含特殊字符时使用引号
        if any(c in value for c in ':{}\n[]&*!|>%@`#,') or value.startswith(('{{', "'", '"')):
            # 包含 Go 模板语法或特殊字符，使用双引号并转义
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        if value.lower() in ('true', 'false', 'null', 'yes', 'no', 'on', 'off'):
            return f'"{value}"'
        try:
            float(value)
            return f'"{value}"'
        except ValueError:
            pass
        return value
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif value is None:
        return 'null'
    else:
        return str(value)


def yaml_dump_dict(data, indent=0):
    """将字典序列化为 YAML 字符串"""
    lines = []
    prefix = '  ' * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(yaml_dump_dict(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # 列表中的字典项
                    first = True
                    for k, v in item.items():
                        if first:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}  - {k}:")
                                lines.append(yaml_dump_dict(v, indent + 3))
                            elif isinstance(v, list):
                                lines.append(f"{prefix}  - {k}:")
                                for sub_item in v:
                                    if isinstance(sub_item, dict):
                                        first_sub = True
                                        for sk, sv in sub_item.items():
                                            if first_sub:
                                                if isinstance(sv, (dict, list)):
                                                    lines.append(f"{prefix}      - {sk}:")
                                                    if isinstance(sv, dict):
                                                        lines.append(yaml_dump_dict(sv, indent + 5))
                                                    else:
                                                        for ssi in sv:
                                                            lines.append(f"{prefix}          - {yaml_dump_value(ssi)}")
                                                else:
                                                    lines.append(f"{prefix}      - {sk}: {yaml_dump_value(sv)}")
                                                first_sub = False
                                            else:
                                                if isinstance(sv, (dict, list)):
                                                    lines.append(f"{prefix}        {sk}:")
                                                    if isinstance(sv, dict):
                                                        lines.append(yaml_dump_dict(sv, indent + 5))
                                                    else:
                                                        for ssi in sv:
                                                            lines.append(f"{prefix}          - {yaml_dump_value(ssi)}")
                                                else:
                                                    lines.append(f"{prefix}        {sk}: {yaml_dump_value(sv)}")
                                    else:
                                        lines.append(f"{prefix}      - {yaml_dump_value(sub_item)}")
                            else:
                                lines.append(f"{prefix}  - {k}: {yaml_dump_value(v)}")
                            first = False
                        else:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}    {k}:")
                                lines.append(yaml_dump_dict(v, indent + 3))
                            elif isinstance(v, list):
                                lines.append(f"{prefix}    {k}:")
                                for sub_item in v:
                                    if isinstance(sub_item, dict):
                                        first_sub = True
                                        for sk, sv in sub_item.items():
                                            if first_sub:
                                                lines.append(f"{prefix}      - {sk}: {yaml_dump_value(sv)}")
                                                first_sub = False
                                            else:
                                                lines.append(f"{prefix}        {sk}: {yaml_dump_value(sv)}")
                                    else:
                                        lines.append(f"{prefix}      - {yaml_dump_value(sub_item)}")
                            else:
                                lines.append(f"{prefix}    {k}: {yaml_dump_value(v)}")
                else:
                    lines.append(f"{prefix}  - {yaml_dump_value(item)}")
        else:
            lines.append(f"{prefix}{key}: {yaml_dump_value(value)}")
    return '\n'.join(lines)


def yaml_serialize(data):
    """将数据结构序列化为完整的 YAML 文档"""
    return yaml_dump_dict(data)


# ============================================================
# 告警规则管理
# ============================================================

def build_alert_rule(alert_name, expr, for_duration=None, keep_firing_for=None,
                     severity=None, extra_labels=None, summary=None,
                     description=None, runbook_url=None):
    """构建单条告警规则的数据结构"""
    rule = {
        'alert': alert_name,
        'expr': expr,
    }
    if for_duration:
        rule['for'] = for_duration
    if keep_firing_for:
        rule['keep_firing_for'] = keep_firing_for

    labels = {}
    if severity:
        labels['severity'] = severity
    if extra_labels:
        labels.update(extra_labels)
    if labels:
        rule['labels'] = labels

    annotations = {}
    if summary:
        annotations['summary'] = summary
    if description:
        annotations['description'] = description
    if runbook_url:
        annotations['runbook_url'] = runbook_url
    if annotations:
        rule['annotations'] = annotations

    return rule


def create_alert_rule_file(output_path, group_name, rules):
    """创建告警规则 YAML 文件"""
    data = {
        'groups': [
            {
                'name': group_name,
                'rules': rules,
            }
        ]
    }
    yaml_content = yaml_serialize(data)

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content + '\n')

    return output_path


def append_alert_rule_to_file(rules_file, group_name, rule):
    """向已有规则文件追加告警规则

    简单实现：读取文件内容，在对应 group 的 rules 列表末尾追加新规则。
    如果 group 不存在，则创建新 group。
    """
    if not os.path.exists(rules_file):
        # 文件不存在，创建新文件
        return create_alert_rule_file(rules_file, group_name, [rule])

    with open(rules_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 构建新规则的 YAML 文本
    rule_yaml_lines = []
    rule_yaml_lines.append(f"      - alert: {yaml_dump_value(rule['alert'])}")
    rule_yaml_lines.append(f"        expr: {yaml_dump_value(rule['expr'])}")
    if 'for' in rule:
        rule_yaml_lines.append(f"        for: {yaml_dump_value(rule['for'])}")
    if 'keep_firing_for' in rule:
        rule_yaml_lines.append(f"        keep_firing_for: {yaml_dump_value(rule['keep_firing_for'])}")
    if 'labels' in rule:
        rule_yaml_lines.append("        labels:")
        for k, v in rule['labels'].items():
            rule_yaml_lines.append(f"          {k}: {yaml_dump_value(v)}")
    if 'annotations' in rule:
        rule_yaml_lines.append("        annotations:")
        for k, v in rule['annotations'].items():
            rule_yaml_lines.append(f"          {k}: {yaml_dump_value(v)}")

    new_rule_text = '\n'.join(rule_yaml_lines)

    # 检查是否存在对应的 group
    # 简单查找 "name: <group_name>" 行
    group_marker = f"name: {group_name}"
    if group_marker in content or f'name: "{group_name}"' in content:
        # 在文件末尾追加规则（在最后一行之前）
        content = content.rstrip('\n') + '\n' + new_rule_text + '\n'
    else:
        # 创建新 group
        new_group = f"\n  - name: {group_name}\n    rules:\n{new_rule_text}\n"
        content = content.rstrip('\n') + new_group

    with open(rules_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return rules_file


# ============================================================
# 告警规则预设模板
# ============================================================

ALERT_TEMPLATES = {
    'standard': {
        'description': '标准告警规则集（服务可用性 + 资源使用率 + 请求错误率）',
        'groups': [
            {
                'name': 'service_availability',
                'rules': [
                    build_alert_rule(
                        'InstanceDown', 'up == 0', for_duration='3m',
                        severity='critical',
                        summary='{{ $labels.instance }} 的 {{ $labels.job }} 服务已宕机',
                        description='{{ $labels.instance }} 已超过 3 分钟无法访问'
                    ),
                    build_alert_rule(
                        'TooManyTargetsDown',
                        '(count by (job) (up == 0) / count by (job) (up)) > 0.5',
                        for_duration='5m', severity='critical',
                        summary='{{ $labels.job }} 超过 50% 的实例宕机',
                        description='{{ $labels.job }} 的存活实例比例低于 50%'
                    ),
                ]
            },
            {
                'name': 'resource_alerts',
                'rules': [
                    build_alert_rule(
                        'HighCPUUsage',
                        '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.instance }} CPU 使用率过高',
                        description='CPU 使用率已达 {{ $value | printf "%.1f" }}%，持续超过 10 分钟'
                    ),
                    build_alert_rule(
                        'HighMemoryUsage',
                        '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.instance }} 内存使用率过高',
                        description='内存使用率已达 {{ $value | printf "%.1f" }}%'
                    ),
                    build_alert_rule(
                        'DiskSpaceLow',
                        '(1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes) * 100 > 85',
                        for_duration='15m', severity='warning',
                        summary='{{ $labels.instance }} 磁盘空间不足',
                        description='{{ $labels.mountpoint }} 磁盘使用率已达 {{ $value | printf "%.1f" }}%'
                    ),
                    build_alert_rule(
                        'DiskWillFillIn24Hours',
                        'predict_linear(node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"}[6h], 24*3600) < 0',
                        for_duration='30m', severity='critical',
                        summary='{{ $labels.instance }} 磁盘预计 24 小时内写满',
                        description='{{ $labels.mountpoint }} 按当前趋势预计 24 小时内磁盘空间耗尽'
                    ),
                ]
            },
            {
                'name': 'request_alerts',
                'rules': [
                    build_alert_rule(
                        'HighErrorRate',
                        'sum(rate(http_requests_total{status=~"5.."}[5m])) by (job) / sum(rate(http_requests_total[5m])) by (job) > 0.05',
                        for_duration='5m', severity='critical',
                        summary='{{ $labels.job }} 错误率过高',
                        description='{{ $labels.job }} 的 5xx 错误率已达 {{ $value | printf "%.2f" }}（阈值 5%）'
                    ),
                    build_alert_rule(
                        'HighP99Latency',
                        'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job)) > 1',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.job }} P99 延迟过高',
                        description='{{ $labels.job }} 的 P99 延迟已达 {{ $value | printf "%.2f" }}s（阈值 1s）'
                    ),
                ]
            },
        ]
    },
    'kubernetes': {
        'description': 'Kubernetes 容器告警规则集',
        'groups': [
            {
                'name': 'kubernetes_alerts',
                'rules': [
                    build_alert_rule(
                        'ContainerOOMKilled',
                        'increase(kube_pod_container_status_restarts_total[1h]) > 3 and kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} == 1',
                        for_duration='0m', severity='critical',
                        summary='{{ $labels.namespace }}/{{ $labels.pod }} 容器频繁 OOM',
                        description='容器 {{ $labels.container }} 在过去 1 小时内 OOM 重启 {{ $value }} 次'
                    ),
                    build_alert_rule(
                        'PodNotReady',
                        'kube_pod_status_ready{condition="true"} == 0',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.namespace }}/{{ $labels.pod }} 未就绪',
                        description='Pod 已超过 10 分钟未进入 Ready 状态'
                    ),
                    build_alert_rule(
                        'ContainerCPUThrottling',
                        'rate(container_cpu_cfs_throttled_seconds_total[5m]) > 0.5',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.namespace }}/{{ $labels.pod }} CPU 限流严重',
                        description='容器 {{ $labels.container }} CPU 限流率 {{ $value | printf "%.2f" }}s/s'
                    ),
                    build_alert_rule(
                        'PodCrashLooping',
                        'increase(kube_pod_container_status_restarts_total[1h]) > 5',
                        for_duration='10m', severity='critical',
                        summary='{{ $labels.namespace }}/{{ $labels.pod }} 频繁重启',
                        description='容器 {{ $labels.container }} 在过去 1 小时内重启 {{ $value }} 次'
                    ),
                ]
            }
        ]
    },
    'infrastructure': {
        'description': '基础设施告警规则集（主机 + 网络）',
        'groups': [
            {
                'name': 'infrastructure_alerts',
                'rules': [
                    build_alert_rule(
                        'InstanceDown', 'up == 0', for_duration='3m',
                        severity='critical',
                        summary='{{ $labels.instance }} 的 {{ $labels.job }} 服务已宕机',
                        description='{{ $labels.instance }} 已超过 3 分钟无法访问'
                    ),
                    build_alert_rule(
                        'HighCPUUsage',
                        '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.instance }} CPU 使用率过高',
                        description='CPU 使用率已达 {{ $value | printf "%.1f" }}%'
                    ),
                    build_alert_rule(
                        'HighMemoryUsage',
                        '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85',
                        for_duration='10m', severity='warning',
                        summary='{{ $labels.instance }} 内存使用率过高',
                        description='内存使用率已达 {{ $value | printf "%.1f" }}%'
                    ),
                    build_alert_rule(
                        'DiskSpaceLow',
                        '(1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes) * 100 > 85',
                        for_duration='15m', severity='warning',
                        summary='{{ $labels.instance }} 磁盘空间不足',
                        description='{{ $labels.mountpoint }} 磁盘使用率已达 {{ $value | printf "%.1f" }}%'
                    ),
                    build_alert_rule(
                        'HighNetworkErrors',
                        'rate(node_network_receive_errs_total[5m]) + rate(node_network_transmit_errs_total[5m]) > 10',
                        for_duration='5m', severity='warning',
                        summary='{{ $labels.instance }} 网络错误率过高',
                        description='{{ $labels.device }} 网络错误率 {{ $value | printf "%.1f" }}/s'
                    ),
                    build_alert_rule(
                        'HighLoadAverage',
                        'node_load15 / count without (cpu, mode) (node_cpu_seconds_total{mode="idle"}) > 2',
                        for_duration='15m', severity='warning',
                        summary='{{ $labels.instance }} 负载过高',
                        description='15 分钟平均负载已达 {{ $value | printf "%.2f" }}（CPU 核数的 2 倍以上）'
                    ),
                ]
            }
        ]
    },
}


def cmd_create_alert_rule(args):
    """创建告警规则文件"""
    if not args.output:
        print("错误: --output 参数必须指定输出文件路径", file=sys.stderr)
        sys.exit(1)
    if not args.group_name:
        print("错误: --group-name 参数必须指定规则组名称", file=sys.stderr)
        sys.exit(1)
    if not args.alert_name:
        print("错误: --alert-name 参数必须指定告警名称", file=sys.stderr)
        sys.exit(1)
    if not args.expr:
        print("错误: --expr 参数必须指定 PromQL 表达式", file=sys.stderr)
        sys.exit(1)

    # 解析额外标签
    extra_labels = {}
    if args.extra_labels:
        for pair in args.extra_labels.split(','):
            if '=' in pair:
                k, v = pair.split('=', 1)
                extra_labels[k.strip()] = v.strip()

    rule = build_alert_rule(
        alert_name=args.alert_name,
        expr=args.expr,
        for_duration=getattr(args, 'for', None),
        keep_firing_for=args.keep_firing_for,
        severity=args.severity,
        extra_labels=extra_labels if extra_labels else None,
        summary=args.summary,
        description=args.description,
        runbook_url=args.runbook_url,
    )

    output_path = create_alert_rule_file(args.output, args.group_name, [rule])
    print(f"✅ 告警规则文件已生成: {output_path}")
    print(f"   规则组: {args.group_name}")
    print(f"   告警名: {args.alert_name}")
    print(f"   表达式: {args.expr}")
    if args.severity:
        print(f"   严重级别: {args.severity}")
    print(f"\n📋 文件内容预览:")
    with open(output_path, 'r', encoding='utf-8') as f:
        print(f.read())


def cmd_append_alert_rule(args):
    """向已有规则文件追加告警规则"""
    if not args.rules_file:
        print("错误: --rules-file 参数必须指定规则文件路径", file=sys.stderr)
        sys.exit(1)
    if not args.group_name:
        print("错误: --group-name 参数必须指定规则组名称", file=sys.stderr)
        sys.exit(1)
    if not args.alert_name:
        print("错误: --alert-name 参数必须指定告警名称", file=sys.stderr)
        sys.exit(1)
    if not args.expr:
        print("错误: --expr 参数必须指定 PromQL 表达式", file=sys.stderr)
        sys.exit(1)

    extra_labels = {}
    if args.extra_labels:
        for pair in args.extra_labels.split(','):
            if '=' in pair:
                k, v = pair.split('=', 1)
                extra_labels[k.strip()] = v.strip()

    rule = build_alert_rule(
        alert_name=args.alert_name,
        expr=args.expr,
        for_duration=getattr(args, 'for', None),
        keep_firing_for=args.keep_firing_for,
        severity=args.severity,
        extra_labels=extra_labels if extra_labels else None,
        summary=args.summary,
        description=args.description,
        runbook_url=args.runbook_url,
    )

    output_path = append_alert_rule_to_file(args.rules_file, args.group_name, rule)
    print(f"✅ 告警规则已追加到: {output_path}")
    print(f"   规则组: {args.group_name}")
    print(f"   告警名: {args.alert_name}")


def cmd_generate_alert_rules(args):
    """使用预设模板生成告警规则"""
    template_name = args.template or 'standard'
    if template_name not in ALERT_TEMPLATES:
        print(f"错误: 未知模板 '{template_name}'", file=sys.stderr)
        print(f"可用模板: {', '.join(ALERT_TEMPLATES.keys())}", file=sys.stderr)
        sys.exit(1)

    if not args.output:
        print("错误: --output 参数必须指定输出文件路径", file=sys.stderr)
        sys.exit(1)

    template = ALERT_TEMPLATES[template_name]
    data = {'groups': template['groups']}
    yaml_content = yaml_serialize(data)

    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(yaml_content + '\n')

    total_rules = sum(len(g['rules']) for g in template['groups'])
    print(f"✅ 告警规则文件已生成: {args.output}")
    print(f"   模板: {template_name} - {template['description']}")
    print(f"   规则组数: {len(template['groups'])}")
    print(f"   总规则数: {total_rules}")
    print(f"\n📋 规则列表:")
    for group in template['groups']:
        print(f"  📋 {group['name']}:")
        for rule in group['rules']:
            sev = rule.get('labels', {}).get('severity', '?')
            icon = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(sev, '⚪')
            print(f"    {icon} [{sev:8s}] {rule['alert']}")


def cmd_validate_rules(args):
    """验证告警规则文件"""
    rules_file = args.rules_file
    rules_dir = args.rules_dir

    if not rules_file and not rules_dir:
        print("错误: 需要指定 --rules-file 或 --rules-dir", file=sys.stderr)
        sys.exit(1)

    files_to_check = []
    if rules_file:
        files_to_check.append(rules_file)
    if rules_dir:
        if os.path.isdir(rules_dir):
            for f in os.listdir(rules_dir):
                if f.endswith(('.yml', '.yaml')):
                    files_to_check.append(os.path.join(rules_dir, f))

    if not files_to_check:
        print("未找到规则文件", file=sys.stderr)
        sys.exit(1)

    all_ok = True
    for filepath in files_to_check:
        print(f"🔍 检查: {filepath}")
        if not os.path.exists(filepath):
            print(f"  ❌ 文件不存在")
            all_ok = False
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        errors = []
        warnings = []

        # 基本语法检查
        if 'groups:' not in content:
            errors.append("缺少 'groups:' 顶级键")
        if '- alert:' not in content and '- record:' not in content:
            errors.append("未找到任何告警规则或 Recording Rule")

        # 检查必要字段
        lines = content.split('\n')
        in_rule = False
        has_expr = False
        current_alert = None
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('- alert:'):
                if in_rule and not has_expr:
                    errors.append(f"第 {i} 行附近: 告警 '{current_alert}' 缺少 'expr' 字段")
                in_rule = True
                has_expr = False
                current_alert = stripped.split(':', 1)[1].strip().strip('"').strip("'")
            elif stripped.startswith('expr:') and in_rule:
                has_expr = True
                expr_val = stripped.split(':', 1)[1].strip()
                # 检查 Counter 类型是否使用了 rate/increase
                if '_total' in expr_val and 'rate(' not in expr_val and 'increase(' not in expr_val:
                    warnings.append(f"第 {i} 行: 指标名含 '_total'（Counter 类型），建议使用 rate() 或 increase()")
            elif stripped.startswith('- alert:') or stripped.startswith('- record:'):
                if in_rule and not has_expr:
                    errors.append(f"告警 '{current_alert}' 缺少 'expr' 字段")
                in_rule = True
                has_expr = False

        if in_rule and not has_expr:
            errors.append(f"告警 '{current_alert}' 缺少 'expr' 字段")

        if errors:
            for err in errors:
                print(f"  ❌ {err}")
            all_ok = False
        if warnings:
            for warn in warnings:
                print(f"  ⚠️  {warn}")
        if not errors and not warnings:
            print(f"  ✅ 语法检查通过")

    if all_ok:
        print(f"\n✅ 所有规则文件检查通过")
    else:
        print(f"\n❌ 部分规则文件存在问题，请修复后重试")
        sys.exit(1)


def cmd_list_rules(args):
    """查看 Prometheus 上的规则"""
    if not args.url:
        print("错误: --url 参数必须指定 Prometheus 地址", file=sys.stderr)
        sys.exit(1)

    url = f"{args.url}/api/v1/rules"
    if args.rule_type:
        url += f"?type={args.rule_type}"

    data = http_get(url)
    if data.get('status') != 'success':
        print(f"查询失败: {data.get('error', '未知错误')}", file=sys.stderr)
        sys.exit(1)

    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    groups = data.get('data', {}).get('groups', [])
    total_rules = sum(len(g.get('rules', [])) for g in groups)
    print(f"规则组: {len(groups)} | 总规则数: {total_rules}")
    if args.rule_type:
        print(f"过滤类型: {args.rule_type}")
    print()

    for g in groups:
        name = g.get('name', '?')
        rules = g.get('rules', [])
        file_path = g.get('file', '?')
        interval = g.get('interval', '?')
        print(f"  📋 {name} ({len(rules)} 条规则) [文件: {file_path}, 间隔: {interval}s]")
        for r in rules:
            rtype = r.get('type', '?')
            rname = r.get('name', '?')
            health = r.get('health', '?')
            state = r.get('state', '')
            icon = '📊' if rtype == 'recording' else '🔔'
            health_icon = '✅' if health == 'ok' else '❌'
            state_info = f" ({state})" if state else ""
            print(f"    {icon} {health_icon} [{rtype:9s}] {rname}{state_info}")
            if rtype == 'alerting' and r.get('query'):
                print(f"       expr: {r['query']}")
            if r.get('duration'):
                print(f"       for: {r['duration']}s")
        print()


def cmd_list_alerts(args):
    """查看活跃告警"""
    if not args.url:
        print("错误: --url 参数必须指定 Prometheus 地址", file=sys.stderr)
        sys.exit(1)

    data = http_get(f"{args.url}/api/v1/alerts")
    if data.get('status') != 'success':
        print(f"查询失败: {data.get('error', '未知错误')}", file=sys.stderr)
        sys.exit(1)

    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    alerts = data.get('data', {}).get('alerts', [])
    print(f"活跃告警数: {len(alerts)}")
    if not alerts:
        print("  (无活跃告警)")
        return

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
        print(f"\n{icon} {sev.upper()} ({len(sev_alerts)}):")
        for a in sev_alerts:
            name = a.get('labels', {}).get('alertname', '?')
            state = a.get('state', '?')
            summary = a.get('annotations', {}).get('summary', '')
            active_at = a.get('activeAt', '')
            print(f"    [{state:8s}] {name}")
            if summary:
                print(f"              {summary}")
            if active_at:
                print(f"              活跃时间: {active_at}")


# ============================================================
# 抓取配置管理
# ============================================================

def build_scrape_config(job_name, targets, scrape_interval=None, scrape_timeout=None,
                        metrics_path=None, scheme=None, labels=None,
                        basic_auth_user=None, basic_auth_pass=None,
                        tls_skip_verify=False):
    """构建单个 scrape_config 的数据结构"""
    config = {'job_name': job_name}

    if scrape_interval:
        config['scrape_interval'] = scrape_interval
    if scrape_timeout:
        config['scrape_timeout'] = scrape_timeout
    if metrics_path and metrics_path != '/metrics':
        config['metrics_path'] = metrics_path
    if scheme and scheme != 'http':
        config['scheme'] = scheme
    if basic_auth_user:
        config['basic_auth'] = {'username': basic_auth_user}
        if basic_auth_pass:
            config['basic_auth']['password'] = basic_auth_pass
    if tls_skip_verify:
        config['tls_config'] = {'insecure_skip_verify': True}

    # 构建 static_configs
    target_labels = {}
    if labels:
        if isinstance(labels, str):
            for pair in labels.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    target_labels[k.strip()] = v.strip()
        elif isinstance(labels, dict):
            target_labels = labels

    static_config = {'targets': targets if isinstance(targets, list) else targets.split(',')}
    if target_labels:
        static_config['labels'] = target_labels

    config['static_configs'] = [static_config]
    return config


def create_scrape_config_file(output_path, scrape_configs, global_config=None):
    """创建 Prometheus 抓取配置文件"""
    data = {}
    if global_config:
        data['global'] = global_config
    data['scrape_configs'] = scrape_configs

    yaml_content = yaml_serialize(data)

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content + '\n')

    return output_path


def create_file_sd_targets(output_path, targets, labels=None):
    """创建文件服务发现的目标文件（JSON 或 YAML 格式）"""
    target_list = targets if isinstance(targets, list) else [t.strip() for t in targets.split(',')]

    target_labels = {}
    if labels:
        if isinstance(labels, str):
            for pair in labels.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    target_labels[k.strip()] = v.strip()
        elif isinstance(labels, dict):
            target_labels = labels

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if output_path.endswith('.json'):
        # JSON 格式
        data = [{'targets': target_list, 'labels': target_labels}]
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        # YAML 格式
        lines = ['- targets:']
        for t in target_list:
            lines.append(f'    - {t}')
        if target_labels:
            lines.append('  labels:')
            for k, v in target_labels.items():
                lines.append(f'    {k}: {yaml_dump_value(v)}')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

    return output_path


# ============================================================
# 抓取配置预设模板
# ============================================================

SCRAPE_TEMPLATES = {
    'infrastructure': {
        'description': '基础设施监控配置（Prometheus + Node Exporter + cAdvisor）',
        'global': {
            'scrape_interval': '15s',
            'scrape_timeout': '10s',
            'evaluation_interval': '15s',
        },
        'scrape_configs': [
            build_scrape_config('prometheus', ['localhost:9090']),
            build_scrape_config('node-exporter', ['node1:9100', 'node2:9100'],
                                scrape_interval='30s', labels={'env': 'production'}),
            build_scrape_config('cadvisor', ['cadvisor:8080'], scrape_interval='15s'),
        ]
    },
    'middleware': {
        'description': '中间件监控配置（Redis + MySQL + Kafka + Nginx）',
        'scrape_configs': [
            build_scrape_config('redis', ['redis-exporter:9121'],
                                labels={'redis_instance': 'redis-master'}),
            build_scrape_config('mysql', ['mysql-exporter:9104'],
                                labels={'mysql_instance': 'mysql-master'}),
            build_scrape_config('kafka', ['kafka-exporter:9308']),
            build_scrape_config('nginx', ['nginx-exporter:9113']),
        ]
    },
    'blackbox': {
        'description': 'Blackbox 探针监控配置',
        'scrape_configs': [
            {
                'job_name': 'blackbox-http',
                'metrics_path': '/probe',
                'params': {'module': ['http_2xx']},
                'static_configs': [
                    {'targets': ['https://example.com', 'https://api.example.com/health']}
                ],
                'relabel_configs': [
                    {
                        'source_labels': ['__address__'],
                        'target_label': '__param_target',
                    },
                    {
                        'source_labels': ['__param_target'],
                        'target_label': 'instance',
                    },
                    {
                        'target_label': '__address__',
                        'replacement': 'blackbox-exporter:9115',
                    },
                ]
            }
        ]
    },
}


def cmd_create_scrape_config(args):
    """创建抓取配置"""
    if not args.output:
        print("错误: --output 参数必须指定输出文件路径", file=sys.stderr)
        sys.exit(1)
    if not args.job_name:
        print("错误: --job-name 参数必须指定任务名称", file=sys.stderr)
        sys.exit(1)
    if not args.targets:
        print("错误: --targets 参数必须指定目标列表", file=sys.stderr)
        sys.exit(1)

    config = build_scrape_config(
        job_name=args.job_name,
        targets=args.targets,
        scrape_interval=args.scrape_interval,
        scrape_timeout=args.scrape_timeout,
        metrics_path=args.metrics_path,
        scheme=args.scheme,
        labels=args.labels,
        basic_auth_user=args.basic_auth_user,
        basic_auth_pass=args.basic_auth_pass,
        tls_skip_verify=args.tls_skip_verify,
    )

    output_path = create_scrape_config_file(args.output, [config])
    target_list = args.targets.split(',') if isinstance(args.targets, str) else args.targets
    print(f"✅ 抓取配置文件已生成: {output_path}")
    print(f"   任务名: {args.job_name}")
    print(f"   目标数: {len(target_list)}")
    if args.scrape_interval:
        print(f"   抓取间隔: {args.scrape_interval}")
    print(f"\n📋 文件内容预览:")
    with open(output_path, 'r', encoding='utf-8') as f:
        print(f.read())


def cmd_append_scrape_config(args):
    """向已有配置文件追加抓取任务"""
    config_file = args.config_file
    if not config_file:
        print("错误: --config-file 参数必须指定配置文件路径", file=sys.stderr)
        sys.exit(1)
    if not args.job_name:
        print("错误: --job-name 参数必须指定任务名称", file=sys.stderr)
        sys.exit(1)
    if not args.targets:
        print("错误: --targets 参数必须指定目标列表", file=sys.stderr)
        sys.exit(1)

    config = build_scrape_config(
        job_name=args.job_name,
        targets=args.targets,
        scrape_interval=args.scrape_interval,
        metrics_path=args.metrics_path,
        scheme=args.scheme,
        labels=args.labels,
    )

    # 构建追加的 YAML 文本
    config_yaml = yaml_serialize({'scrape_configs': [config]})
    # 提取 scrape_configs 下的内容
    lines = config_yaml.split('\n')
    append_lines = []
    in_config = False
    for line in lines:
        if line.strip().startswith('- job_name:'):
            in_config = True
        if in_config:
            append_lines.append(line)

    append_text = '\n'.join(append_lines)

    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.rstrip('\n') + '\n' + append_text + '\n'
    else:
        content = config_yaml + '\n'

    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 抓取配置已追加到: {config_file}")
    print(f"   任务名: {args.job_name}")
    print(f"   目标: {args.targets}")


def cmd_generate_scrape_config(args):
    """使用预设模板生成抓取配置"""
    template_name = args.template or 'infrastructure'
    if template_name not in SCRAPE_TEMPLATES:
        print(f"错误: 未知模板 '{template_name}'", file=sys.stderr)
        print(f"可用模板: {', '.join(SCRAPE_TEMPLATES.keys())}", file=sys.stderr)
        sys.exit(1)

    if not args.output:
        print("错误: --output 参数必须指定输出文件路径", file=sys.stderr)
        sys.exit(1)

    template = SCRAPE_TEMPLATES[template_name]

    # 如果是 blackbox 模板且指定了 probe-targets，替换默认目标
    if template_name == 'blackbox' and args.probe_targets:
        probe_list = [t.strip() for t in args.probe_targets.split(',')]
        template['scrape_configs'][0]['static_configs'][0]['targets'] = probe_list

    data = {}
    if 'global' in template:
        data['global'] = template['global']
    data['scrape_configs'] = template['scrape_configs']

    yaml_content = yaml_serialize(data)

    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(yaml_content + '\n')

    print(f"✅ 抓取配置文件已生成: {args.output}")
    print(f"   模板: {template_name} - {template['description']}")
    print(f"   抓取任务数: {len(template['scrape_configs'])}")
    print(f"\n📋 任务列表:")
    for sc in template['scrape_configs']:
        job = sc.get('job_name', '?')
        targets = []
        for st in sc.get('static_configs', []):
            targets.extend(st.get('targets', []))
        print(f"    📡 {job}: {', '.join(targets)}")


def cmd_create_file_sd_targets(args):
    """创建文件服务发现目标文件"""
    if not args.output:
        print("错误: --output 参数必须指定输出文件路径", file=sys.stderr)
        sys.exit(1)
    if not args.targets:
        print("错误: --targets 参数必须指定目标列表", file=sys.stderr)
        sys.exit(1)

    output_path = create_file_sd_targets(args.output, args.targets, args.labels)
    target_list = [t.strip() for t in args.targets.split(',')] if isinstance(args.targets, str) else args.targets
    fmt = 'JSON' if output_path.endswith('.json') else 'YAML'
    print(f"✅ 文件服务发现目标文件已生成: {output_path}")
    print(f"   格式: {fmt}")
    print(f"   目标数: {len(target_list)}")
    print(f"\n📋 文件内容预览:")
    with open(output_path, 'r', encoding='utf-8') as f:
        print(f.read())


def cmd_validate_config(args):
    """验证 Prometheus 配置文件"""
    config_file = args.config_file
    if not config_file:
        print("错误: --config-file 参数必须指定配置文件路径", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(config_file):
        print(f"❌ 文件不存在: {config_file}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 检查配置文件: {config_file}")

    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()

    errors = []
    warnings = []

    # 基本结构检查
    if 'scrape_configs:' not in content and 'global:' not in content:
        errors.append("缺少 'scrape_configs:' 或 'global:' 顶级键")

    # 检查 job_name 唯一性
    job_names = []
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('job_name:') or stripped.startswith('- job_name:'):
            job = stripped.split(':', 1)[1].strip().strip('"').strip("'")
            if job in job_names:
                errors.append(f"重复的 job_name: {job}")
            job_names.append(job)

    # 检查 scrape_timeout 不大于 scrape_interval
    # （简单检查，不做完整的 YAML 解析）

    if errors:
        for err in errors:
            print(f"  ❌ {err}")
    if warnings:
        for warn in warnings:
            print(f"  ⚠️  {warn}")
    if not errors:
        print(f"  ✅ 基本语法检查通过")
        print(f"  📡 发现 {len(job_names)} 个抓取任务: {', '.join(job_names)}")
    else:
        sys.exit(1)


def cmd_list_targets(args):
    """查看抓取目标状态"""
    if not args.url:
        print("错误: --url 参数必须指定 Prometheus 地址", file=sys.stderr)
        sys.exit(1)

    url = f"{args.url}/api/v1/targets"
    if args.state:
        url += f"?state={args.state}"

    data = http_get(url)
    if data.get('status') != 'success':
        print(f"查询失败: {data.get('error', '未知错误')}", file=sys.stderr)
        sys.exit(1)

    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    active = data.get('data', {}).get('activeTargets', [])
    dropped = data.get('data', {}).get('droppedTargets', [])

    # 按 job 过滤
    if args.job:
        active = [t for t in active if t.get('labels', {}).get('job') == args.job]

    print(f"活跃目标: {len(active)} | 已丢弃: {len(dropped)}")

    # 按 health 分组统计
    health_count = {}
    for t in active:
        h = t.get('health', 'unknown')
        health_count[h] = health_count.get(h, 0) + 1

    if health_count:
        print("\n健康状态统计:")
        for h, c in sorted(health_count.items()):
            icon = '✅' if h == 'up' else '❌'
            print(f"  {icon} {h}: {c}")

    print()
    for t in sorted(active, key=lambda x: (x.get('health', ''), x.get('labels', {}).get('job', ''))):
        health = t.get('health', 'unknown')
        job = t.get('labels', {}).get('job', '?')
        instance = t.get('labels', {}).get('instance', '?')
        scrape_url = t.get('scrapeUrl', '?')
        last_scrape = t.get('lastScrape', '?')
        error = t.get('lastError', '')
        status_icon = '✅' if health == 'up' else '❌'
        line = f"  {status_icon} [{health:6s}] {job:30s} {instance}"
        if error:
            line += f"\n     ⚠️ {error}"
        print(line)


def cmd_show_config(args):
    """查看 Prometheus 当前配置"""
    if not args.url:
        print("错误: --url 参数必须指定 Prometheus 地址", file=sys.stderr)
        sys.exit(1)

    data = http_get(f"{args.url}/api/v1/status/config")
    if data.get('status') != 'success':
        print(f"查询失败: {data.get('error', '未知错误')}", file=sys.stderr)
        sys.exit(1)

    yaml_config = data.get('data', {}).get('yaml', '')

    if args.section:
        # 提取指定 section
        lines = yaml_config.split('\n')
        in_section = False
        section_lines = []
        for line in lines:
            if line.startswith(f'{args.section}:'):
                in_section = True
                section_lines.append(line)
            elif in_section:
                if line and not line[0].isspace() and not line.startswith('#'):
                    break
                section_lines.append(line)
        if section_lines:
            print('\n'.join(section_lines))
        else:
            print(f"未找到 section: {args.section}")
    else:
        print(yaml_config)


def cmd_reload(args):
    """热加载 Prometheus 配置"""
    if not args.url:
        print("错误: --url 参数必须指定 Prometheus 地址", file=sys.stderr)
        sys.exit(1)

    url = f"{args.url}/-/reload"
    print(f"🔄 正在重载 Prometheus 配置: {args.url}")
    result = http_post(url)
    print(f"✅ 配置重载成功")
    print(f"   提示: 需要 Prometheus 启动时添加 --web.enable-lifecycle 参数")


# ============================================================
# Alertmanager 静默管理
# ============================================================

def parse_duration_to_seconds(duration_str: str) -> int:
    """解析时间范围字符串为秒数"""
    if not duration_str:
        return 3600
    unit = duration_str[-1].lower()
    try:
        value = int(duration_str[:-1])
    except ValueError:
        return 3600
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return value * multipliers.get(unit, 3600)


def cmd_create_silence(args):
    """创建 Alertmanager 静默"""
    if not args.url:
        print("错误: --url 参数必须指定 Alertmanager 地址", file=sys.stderr)
        sys.exit(1)

    matchers = []
    if args.alertname:
        matchers.append({
            'name': 'alertname',
            'value': args.alertname,
            'isRegex': False,
            'isEqual': True,
        })
    if args.instance:
        matchers.append({
            'name': 'instance',
            'value': args.instance,
            'isRegex': False,
            'isEqual': True,
        })
    if args.silence_labels:
        for pair in args.silence_labels.split(','):
            if '=' in pair:
                k, v = pair.split('=', 1)
                matchers.append({
                    'name': k.strip(),
                    'value': v.strip(),
                    'isRegex': False,
                    'isEqual': True,
                })

    if not matchers:
        print("错误: 至少需要指定一个匹配条件（--alertname / --instance / --silence-labels）", file=sys.stderr)
        sys.exit(1)

    duration_sec = parse_duration_to_seconds(args.duration or '6h')
    now = datetime.utcnow()
    ends_at = now + timedelta(seconds=duration_sec)

    silence_data = {
        'matchers': matchers,
        'startsAt': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'endsAt': ends_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'createdBy': args.created_by or 'prometheus_config.py',
        'comment': args.comment or '通过 prometheus_config.py 创建的静默',
    }

    url = f"{args.url}/api/v2/silences"
    result = http_post(url, json_data=silence_data)

    silence_id = result.get('silenceID', '?')
    print(f"✅ 静默已创建")
    print(f"   ID: {silence_id}")
    print(f"   开始: {silence_data['startsAt']}")
    print(f"   结束: {silence_data['endsAt']}")
    print(f"   持续: {args.duration or '6h'}")
    print(f"   匹配条件:")
    for m in matchers:
        print(f"     {m['name']} = {m['value']}")
    if args.comment:
        print(f"   备注: {args.comment}")


def cmd_list_silences(args):
    """查看 Alertmanager 静默列表"""
    if not args.url:
        print("错误: --url 参数必须指定 Alertmanager 地址", file=sys.stderr)
        sys.exit(1)

    data = http_get(f"{args.url}/api/v2/silences")

    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not isinstance(data, list):
        data = data.get('data', []) if isinstance(data, dict) else []

    active_silences = [s for s in data if s.get('status', {}).get('state') == 'active']
    expired_silences = [s for s in data if s.get('status', {}).get('state') != 'active']

    print(f"静默总数: {len(data)} (活跃: {len(active_silences)}, 过期: {len(expired_silences)})")

    if active_silences:
        print(f"\n🔇 活跃静默:")
        for s in active_silences:
            sid = s.get('id', '?')
            created_by = s.get('createdBy', '?')
            comment = s.get('comment', '')
            starts_at = s.get('startsAt', '?')
            ends_at = s.get('endsAt', '?')
            matchers = s.get('matchers', [])
            matcher_str = ', '.join(f"{m['name']}={m['value']}" for m in matchers)
            print(f"    ID: {sid}")
            print(f"    匹配: {matcher_str}")
            print(f"    时间: {starts_at} ~ {ends_at}")
            print(f"    创建者: {created_by}")
            if comment:
                print(f"    备注: {comment}")
            print()


def cmd_delete_silence(args):
    """删除 Alertmanager 静默"""
    if not args.url:
        print("错误: --url 参数必须指定 Alertmanager 地址", file=sys.stderr)
        sys.exit(1)
    if not args.silence_id:
        print("错误: --silence-id 参数必须指定静默 ID", file=sys.stderr)
        sys.exit(1)

    url = f"{args.url}/api/v2/silence/{args.silence_id}"
    http_delete(url)
    print(f"✅ 静默已删除: {args.silence_id}")


def cmd_list_am_alerts(args):
    """查看 Alertmanager 告警"""
    if not args.url:
        print("错误: --url 参数必须指定 Alertmanager 地址", file=sys.stderr)
        sys.exit(1)

    data = http_get(f"{args.url}/api/v2/alerts")

    if args.format == 'json':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not isinstance(data, list):
        data = data.get('data', []) if isinstance(data, dict) else []

    print(f"Alertmanager 告警数: {len(data)}")
    for a in data:
        labels = a.get('labels', {})
        annotations = a.get('annotations', {})
        status = a.get('status', {}).get('state', '?')
        alertname = labels.get('alertname', '?')
        severity = labels.get('severity', '?')
        summary = annotations.get('summary', '')
        icon = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}.get(severity, '⚪')
        print(f"  {icon} [{status:10s}] [{severity:8s}] {alertname}")
        if summary:
            print(f"     {summary}")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Prometheus 配置管理工具 - 告警规则创建/配置、抓取规则配置',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建告警规则
  %(prog)s --action create-alert-rule --output /tmp/rules.yml \\
    --group-name "test" --alert-name "HighCPU" \\
    --expr 'cpu > 80' --for 5m --severity warning

  # 使用模板生成告警规则
  %(prog)s --action generate-alert-rules --template standard --output /tmp/rules.yml

  # 验证规则文件
  %(prog)s --action validate-rules --rules-file /tmp/rules.yml

  # 创建抓取配置
  %(prog)s --action create-scrape-config --output /tmp/scrape.yml \\
    --job-name "my-app" --targets "app1:8080,app2:8080"

  # 创建文件服务发现目标
  %(prog)s --action create-file-sd-targets --output /tmp/targets.json \\
    --targets "app1:8080,app2:8080" --labels "job=my-app,env=prod"

  # 查看规则/告警/目标
  %(prog)s --url http://localhost:9090 --action list-rules
  %(prog)s --url http://localhost:9090 --action list-alerts
  %(prog)s --url http://localhost:9090 --action list-targets

  # 热加载配置
  %(prog)s --url http://localhost:9090 --action reload

  # Alertmanager 静默管理
  %(prog)s --url http://localhost:9093 --action create-silence \\
    --alertname "HighCPU" --duration 6h --comment "维护窗口"
  %(prog)s --url http://localhost:9093 --action list-silences
  %(prog)s --url http://localhost:9093 --action delete-silence --silence-id <id>
        """
    )

    # 通用参数
    parser.add_argument('--url', '-u', help='Prometheus 或 Alertmanager 地址')
    parser.add_argument('--action', '-a', required=True,
                        choices=[
                            # 告警规则管理
                            'create-alert-rule', 'append-alert-rule',
                            'generate-alert-rules', 'validate-rules',
                            'list-rules', 'list-alerts',
                            # 抓取配置管理
                            'create-scrape-config', 'append-scrape-config',
                            'generate-scrape-config', 'create-file-sd-targets',
                            'validate-config', 'list-targets', 'show-config',
                            # 通用操作
                            'reload',
                            # Alertmanager 静默管理
                            'create-silence', 'list-silences', 'delete-silence',
                            'list-am-alerts',
                        ],
                        help='执行的操作')
    parser.add_argument('--format', '-f', choices=['json', 'table'], default='table',
                        help='输出格式（默认 table）')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--username', '-U', help='Basic Auth 用户名')
    parser.add_argument('--password', '-P', help='Basic Auth 密码')
    parser.add_argument('--timeout', '-t', type=int, default=30, help='请求超时（秒）')

    # 告警规则参数
    alert_group = parser.add_argument_group('告警规则参数')
    alert_group.add_argument('--group-name', help='规则组名称')
    alert_group.add_argument('--alert-name', help='告警名称')
    alert_group.add_argument('--expr', help='PromQL 表达式')
    alert_group.add_argument('--for', dest='for', help='持续时间阈值（如 5m）')
    alert_group.add_argument('--keep-firing-for', help='告警保持触发时间（Prometheus 2.42+）')
    alert_group.add_argument('--severity', choices=['critical', 'warning', 'info'],
                             help='告警严重级别')
    alert_group.add_argument('--summary', help='告警摘要（支持 Go 模板）')
    alert_group.add_argument('--description', help='告警描述（支持 Go 模板）')
    alert_group.add_argument('--runbook-url', help='运维手册 URL')
    alert_group.add_argument('--extra-labels', help='额外标签（格式: key1=val1,key2=val2）')
    alert_group.add_argument('--template', help='预设模板名称')
    alert_group.add_argument('--rules-file', help='规则文件路径')
    alert_group.add_argument('--rules-dir', help='规则文件目录')
    alert_group.add_argument('--rule-type', choices=['alert', 'record'],
                             help='规则类型过滤')

    # 抓取配置参数
    scrape_group = parser.add_argument_group('抓取配置参数')
    scrape_group.add_argument('--job-name', help='抓取任务名称')
    scrape_group.add_argument('--targets', help='目标列表（逗号分隔）')
    scrape_group.add_argument('--scrape-interval', help='抓取间隔（如 15s, 30s）')
    scrape_group.add_argument('--scrape-timeout', help='抓取超时')
    scrape_group.add_argument('--metrics-path', help='指标路径（默认 /metrics）')
    scrape_group.add_argument('--scheme', choices=['http', 'https'], help='协议')
    scrape_group.add_argument('--labels', help='标签（格式: key1=val1,key2=val2）')
    scrape_group.add_argument('--basic-auth-user', help='抓取目标的 Basic Auth 用户名')
    scrape_group.add_argument('--basic-auth-pass', help='抓取目标的 Basic Auth 密码')
    scrape_group.add_argument('--tls-skip-verify', action='store_true',
                              help='跳过 TLS 证书验证')
    scrape_group.add_argument('--config-file', help='Prometheus 配置文件路径')
    scrape_group.add_argument('--state', choices=['active', 'dropped', 'any'],
                              help='目标状态过滤')
    scrape_group.add_argument('--job', help='按 job 名称过滤目标')
    scrape_group.add_argument('--section', help='配置文件 section 名称')
    scrape_group.add_argument('--probe-targets', help='探针目标列表（逗号分隔，用于 blackbox 模板）')

    # Alertmanager 静默参数
    silence_group = parser.add_argument_group('Alertmanager 静默参数')
    silence_group.add_argument('--alertname', help='告警名称（静默匹配）')
    silence_group.add_argument('--instance', help='实例名称（静默匹配）')
    silence_group.add_argument('--silence-labels', help='静默匹配标签（格式: key1=val1,key2=val2）')
    silence_group.add_argument('--duration', help='静默持续时间（如 6h, 1d）')
    silence_group.add_argument('--comment', help='静默备注')
    silence_group.add_argument('--created-by', help='静默创建者')
    silence_group.add_argument('--silence-id', help='静默 ID（用于删除）')

    args = parser.parse_args()
    if args.url:
        args.url = args.url.rstrip('/')

    # 初始化认证
    init_auth(args.username, args.password)

    # 动作路由
    action_handlers = {
        # 告警规则管理
        'create-alert-rule': cmd_create_alert_rule,
        'append-alert-rule': cmd_append_alert_rule,
        'generate-alert-rules': cmd_generate_alert_rules,
        'validate-rules': cmd_validate_rules,
        'list-rules': cmd_list_rules,
        'list-alerts': cmd_list_alerts,
        # 抓取配置管理
        'create-scrape-config': cmd_create_scrape_config,
        'append-scrape-config': cmd_append_scrape_config,
        'generate-scrape-config': cmd_generate_scrape_config,
        'create-file-sd-targets': cmd_create_file_sd_targets,
        'validate-config': cmd_validate_config,
        'list-targets': cmd_list_targets,
        'show-config': cmd_show_config,
        # 通用操作
        'reload': cmd_reload,
        # Alertmanager 静默管理
        'create-silence': cmd_create_silence,
        'list-silences': cmd_list_silences,
        'delete-silence': cmd_delete_silence,
        'list-am-alerts': cmd_list_am_alerts,
    }

    handler = action_handlers.get(args.action)
    if handler:
        handler(args)
    else:
        print(f"未知操作: {args.action}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
