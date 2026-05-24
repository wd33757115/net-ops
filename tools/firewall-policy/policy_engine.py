#version1.0-添加工单连续地址合并功能
import logging
from collections import defaultdict
from typing import List, Dict, Tuple

from core import NetworkTopology, parse_ports

logger = logging.getLogger(__name__)

class PolicyProcessor:
    def __init__(self, topology: NetworkTopology):
        self.topology = topology

    def process_policy(self, src_ips: List[str], dst_ips: List[str], proto: str, ports: List[str], action: str,
                       ticket_id: str) -> Dict:
        """支持多端口和范围处理，检查全局 ACL，并记录src_ip到dst_ip的完整路径"""
        proto = proto if proto and str(proto).lower() != 'nan' else ''
        port_list = ports if ports and str(ports).lower() != 'nan' else []
        filtered_ports = parse_ports(port_list) if port_list else set()

        src_domains = self._get_unique_domains(src_ips)
        dst_domains = self._get_unique_domains(dst_ips)

        path_matrix = defaultdict(lambda: defaultdict(lambda: {
            'sources': set(),
            'destinations': set(),
            'proto': proto,
            'ports': filtered_ports,
            'action': action,
            'ticket_id': ticket_id
        }))

        for (src_fw, src_zone), src_group in src_domains.items():
            for (dst_fw, dst_zone), dst_group in dst_domains.items():
                # 计算路径
                path = self.topology.find_shortest_path((src_fw, src_zone), (dst_fw, dst_zone))
                if not path:
                    logger.debug(f"未找到从 {src_fw}.{src_zone} 到 {dst_fw}.{dst_zone} 的路径，跳过")
                    continue

                # 日志记录完整路径
                path_str = " -> ".join([f"{fw}.{domain}" for fw, domain in path])
                for src_ip in src_group:
                    for dst_ip in dst_group:
                        logger.info(f"{src_ip} -> {dst_ip} 的完整路径: {path_str}")

                # 检查路径上每个防火墙并生成规则
                for i in range(len(path) - 1):
                    current_fw, current_zone = path[i]
                    next_fw, next_zone = path[i + 1]

                    # 检查全局 ACL
                    if not self.topology.check_global_acl(current_fw, current_zone, next_fw, next_zone):
                        logger.info(f"防火墙 {current_fw}.{current_zone} -> {next_fw}.{next_zone} 被全局 ACL 禁止，跳过此防火墙策略生成")
                        continue  # 仅跳过当前防火墙的策略生成

                    # 如果当前和下一个节点属于同一防火墙，则生成规则
                    if current_fw != next_fw:  # 跨防火墙跳过
                        continue

                    fw_name = current_fw
                    rule_key = (current_zone, next_zone)

                    path_matrix[fw_name][rule_key]['sources'].update(src_group)
                    path_matrix[fw_name][rule_key]['destinations'].update(dst_group)
                    path_matrix[fw_name][rule_key].update({
                        'proto': proto,
                        'ports': filtered_ports,
                        'action': action,
                        'ticket_id': ticket_id
                    })
                    logger.debug(f"防火墙 {fw_name} 生成规则: {rule_key} - src={src_group}, dst={dst_group}")

        return {
            "firewall_rules": path_matrix,
            "error": None if path_matrix else "未生成任何策略，可能全被 ACL 禁止"
        }

    def _get_unique_domains(self, ips: List[str]) -> Dict[Tuple[str, str], set]:
        """映射 IP 和安全域"""
        domain_map = defaultdict(set)
        for ip in ips:
            owner = self.topology.find_ip_owner(ip)
            if owner:
                domain_map[(owner[0], owner[1])].add(ip)
        return domain_map