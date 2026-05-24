
#version1.0-添加工单连续地址合并功能
import argparse
import re
import logging
from collections import defaultdict
import concurrent.futures
import os
from typing import Dict, List

import pandas as pd
from itertools import combinations

from core import NetworkTopology
from policy_engine import PolicyProcessor
from vendor_config import HuaweiConfigGenerator, H3CConfigGenerator, TopSecConfigGenerator, HillstoneConfigGenerator, \
    H3CF1000ConfigGenerator

logger = logging.getLogger(__name__)


class AdvancedPolicyMerger:
    def __init__(self, topology: NetworkTopology):
        self.topology = topology

    def merge_ips(self, ip_list: List[str]) -> str:
        """合并连续的 IP 地址为范围，CIDR 保持不变，验证安全域一致性"""
        if not ip_list:
            return ""

        # 分离 CIDR 和非 CIDR 地址
        cidr_ips = [ip for ip in ip_list if '/' in ip]
        non_cidr_ips = [ip for ip in ip_list if '/' not in ip]

        # 处理跨子网范围
        ip_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}-\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        cross_subnet_ips = [ip for ip in non_cidr_ips if re.match(ip_pattern, ip) and ip.count('.') == 6]
        single_ips = [ip for ip in non_cidr_ips if not re.match(ip_pattern, ip)]

        # 跨子网范围直接保留
        merged_ips = cidr_ips + cross_subnet_ips

        # 分组单 IP 按前缀，排除 CIDR
        ip_groups = defaultdict(list)
        for ip in sorted(single_ips):
            if '-' in ip and not ip.startswith('range'):
                base = ip.rsplit('.', 1)[0]
                start, end = map(int, ip.split('.')[-1].split('-'))
                ip_groups[base].append((start, end))
            else:
                base = ip.rsplit('.', 1)[0]
                ip_groups[base].append((int(ip.split('.')[-1]), int(ip.split('.')[-1])))

        # 合并单 IP 范围
        for base, ranges in ip_groups.items():
            ranges.sort()
            current_start, current_end = ranges[0]
            for start, end in ranges[1:] + [(None, None)]:
                if start is None or start > current_end + 1:
                    start_ip = f"{base}.{current_start}"
                    end_ip = f"{base}.{current_end}"
                    start_owner = self.topology.find_ip_owner(start_ip)
                    end_owner = self.topology.find_ip_owner(end_ip)
                    valid = True
                    for i in range(current_start, current_end + 1):
                        if self.topology.find_ip_owner(f"{base}.{i}") != start_owner:
                            valid = False
                            break
                    if valid and start_owner and start_owner == end_owner:
                        if current_start == current_end:
                            merged_ips.append(f"{base}.{current_start}")
                        else:
                            merged_ips.append(f"{base}.{current_start}-{current_end}")
                    else:
                        merged_ips.extend([f"{base}.{i}" for i in range(current_start, current_end + 1)])
                    current_start, current_end = start, end
                else:
                    current_end = max(current_end, end)

        return ','.join(merged_ips) if merged_ips else ""

    def merge_policies(self, df: pd.DataFrame) -> pd.DataFrame:
        """合并策略，减少规则条目，跨子网范围不合并"""
        df_clean = df.copy()
        for col in ['src_ip', 'dst_ip', 'port', 'proto', 'action']:
            df_clean[col] = df_clean[col].astype(str).str.strip().str.lower()
        df_clean['port'] = df_clean['port'].replace('nan', '')

        ip_pattern = r'(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:-\d{1,3}(?:\.\d{1,3}\.\d{1,3}\.\d{1,3})?)?)'
        port_pattern = r'(\d+(?:-\d+)?)'

        merged_rows = []
        for (port, proto, action), group_df in df_clean.groupby(['port', 'proto', 'action']):
            current_pairs = set()
            for _, row in group_df.iterrows():
                src_ips = [ip.strip() for ip in re.findall(ip_pattern, row['src_ip']) if ip.strip()]
                dst_ips = [ip.strip() for ip in re.findall(ip_pattern, row['dst_ip']) if ip.strip()]
                for src in src_ips:
                    for dst in dst_ips:
                        current_pairs.add((src, dst))

            src_ips = set(s for s, _ in current_pairs)
            dst_ips = set(d for _, d in current_pairs)

            while current_pairs:
                max_size = 0
                best_src = set()
                best_dst = set()

                for s_size in range(len(src_ips), 0, -1):
                    for src_subset in combinations(src_ips, s_size):
                        src_subset = set(src_subset)
                        for d_size in range(len(dst_ips), 0, -1):
                            for dst_subset in combinations(dst_ips, d_size):
                                dst_subset = set(dst_subset)
                                required = {(s, d) for s in src_subset for d in dst_subset}
                                if required.issubset(current_pairs):
                                    current_size = len(src_subset) * len(dst_subset)
                                    if current_size > max_size:
                                        max_size = current_size
                                        best_src = src_subset
                                        best_dst = dst_subset
                                        if s_size == len(src_ips) and d_size == len(dst_ips):
                                            break
                            if max_size > 0 and d_size < len(dst_ips):
                                break
                    if max_size > 0 and s_size < len(src_ips):
                        break

                merged_src = self.merge_ips(list(best_src))
                merged_dst = self.merge_ips(list(best_dst))
                ports = sorted([p.strip() for p in re.findall(port_pattern, port) if p.strip()])
                merged_rows.append({
                    'src_ip': merged_src,
                    'dst_ip': merged_dst,
                    'port': ','.join(ports) if ports else '',
                    'proto': proto,
                    'action': action
                })

                merged_pairs = {(s, d) for s in best_src for d in best_dst}
                current_pairs -= merged_pairs
                src_ips = {s for s, _ in current_pairs}
                dst_ips = {d for _, d in current_pairs}

        return pd.DataFrame(merged_rows)


def process_single_policy(processor: PolicyProcessor, row, ticket_id: str, user_id: str) -> Dict[str, list]:
    src_ip_str = re.sub(r'[\n;、\s]+', ',', str(row['src_ip']))
    dst_ip_str = re.sub(r'[\n;、\s]+', ',', str(row['dst_ip']))
    ip_pattern = r'(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:-\d{1,3}(?:\.\d{1,3}\.\d{1,3}\.\d{1,3})?)?)'
    src_ips = [ip.strip() for ip in re.findall(ip_pattern, src_ip_str) if ip.strip()]
    dst_ips = [ip.strip() for ip in re.findall(ip_pattern, dst_ip_str) if ip.strip()]

    # 合并 IP 地址，CIDR 不合并
    merger = AdvancedPolicyMerger(processor.topology)
    merged_src_ips = merger.merge_ips(src_ips).split(',')
    merged_dst_ips = merger.merge_ips(dst_ips).split(',')

    port_str = re.sub(r'[;、\s]+', ',', str(row['port']) if pd.notna(row['port']) else '')
    port_pattern = r'(\d+(?:-\d+)?)'
    ports = [p.strip() for p in re.findall(port_pattern, port_str) if p.strip()]

    proto = str(row['proto']) if pd.notna(row['proto']) else 'tcp'
    action = str(row['action']) if pd.notna(row['action']) else 'permit'

    logger.info(
        f"用户 {user_id} 清洗后数据: src_ips={merged_src_ips}, dst_ips={merged_dst_ips}, ports={ports}, proto={proto}, action={action}")

    if not merged_src_ips or any(not ip for ip in merged_src_ips):
        logger.warning(f"用户 {user_id} 策略 {row.name} 的 src_ip 未匹配到有效 IP: {src_ip_str}")
        return {}
    if not merged_dst_ips or any(not ip for ip in merged_dst_ips):
        logger.warning(f"用户 {user_id} 策略 {row.name} 的 dst_ip 未匹配到有效 IP: {dst_ip_str}")
        return {}
    result = processor.process_policy(merged_src_ips, merged_dst_ips, proto, ports, action, ticket_id)
    if result["error"]:
        logger.warning(f"用户 {user_id} 策略 {row.name} 处理失败: {result['error']}")
        return {}

    firewall_rules = defaultdict(list)
    for fw_name, fw_rules in result["firewall_rules"].items():
        for rule_key, rule_data in fw_rules.items():
            firewall_rules[fw_name].append({
                'rule_key': rule_key,
                'sources': rule_data['sources'],
                'destinations': rule_data['destinations'],
                'proto': rule_data['proto'],
                'ports': rule_data['ports'],
                'action': rule_data['action'],
                'ticket_id': rule_data['ticket_id']
            })
    return firewall_rules


def main():
    parser = argparse.ArgumentParser(description="防火墙策略生成工具（支持多用户和多线程）")
    parser.add_argument("-t", "--topology", default="topology.json", help="拓扑JSON文件")
    parser.add_argument("-p", "--policies", required=True, help="策略Excel文件")
    parser.add_argument("-o", "--output", default="configs", help="输出目录")
    parser.add_argument("-u", "--user", default="default_user", help="用户标识")
    parser.add_argument("-w", "--workers", type=int, default=1, help="线程池工作线程数")
    parser.add_argument("-i", "--ticket-id", default=None, help="工单编号（可选，若未提供则使用默认值）")
    args = parser.parse_args()
    
    print(f"[DEBUG] firewall-policy.py - received ticket_id: {args.ticket_id}")
    
    user_output_dir = os.path.join(args.output, args.user)
    os.makedirs(user_output_dir, exist_ok=True)

    topology = NetworkTopology(args.topology)
    processor = PolicyProcessor(topology)
    merger = AdvancedPolicyMerger(topology)

    df = pd.read_excel(args.policies, header=None, skiprows=9,
                       names=['seq', 'src_ip', 'dst_ip', 'port', 'proto', 'start_time', 'end_time', 'action',
                              'long_link'],
                       usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8], engine='openpyxl', dtype={'port': str})

    mask = df.apply(lambda row: row.astype(str).str.contains('策略规则说明：').any(), axis=1)
    if mask.any():
        df = df.loc[:mask.idxmax() - 1]
    df = df.dropna(how='all')

    # 合并策略
    optimized_df = merger.merge_policies(df)
    logger.info(f"合并后策略:\n{optimized_df.to_string(index=False)}")

    ticket_id = args.ticket_id if args.ticket_id else "2025022600001"
    print(f"[DEBUG] firewall-policy.py - final ticket_id for rules: {ticket_id}")
    all_firewall_rules = defaultdict(list)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_row = {
            executor.submit(process_single_policy, processor, row, ticket_id, args.user): row.name
            for _, row in optimized_df.iterrows()
        }
        for future in concurrent.futures.as_completed(future_to_row):
            idx = future_to_row[future]
            try:
                firewall_rules = future.result()
                for fw_name, rules in firewall_rules.items():
                    all_firewall_rules[fw_name].extend(rules)
            except Exception as e:
                logger.error(f"用户 {args.user} 策略 {idx} 处理失败: {str(e)}")

    for fw_name, rules_list in all_firewall_rules.items():
        fw = topology.firewalls[fw_name]
        if fw.type == "华为":
            HuaweiConfigGenerator.generate(user_output_dir, fw_name, rules_list)
        elif fw.type == "H3C":
            H3CConfigGenerator.generate(user_output_dir, fw_name, rules_list)
        elif fw.type == "H3CF1000":
            H3CF1000ConfigGenerator.generate(user_output_dir, fw_name, rules_list)
        elif fw.type == "天融信":
            TopSecConfigGenerator.generate(user_output_dir, fw_name, rules_list)
        elif fw.type == "山石":
            HillstoneConfigGenerator.generate(user_output_dir, fw_name, rules_list)
        else:
            logger.error(f"用户 {args.user} 不支持的防火墙类型: {fw.type}")


if __name__ == "__main__":
    main()