# 通用网络运维故障排查思路与步骤

## 通用故障排查方法论（PDA 模型）

### 第一步：Problem（明确问题）
1. 故障现象是什么？（无法访问/丢包/慢/断流）
2. 故障范围？（单点/局部/全网）
3. 何时开始发生？
4. 发生前有过什么变更？（割接/升级/配置修改）
5. 业务影响程度？（关键业务/非关键业务）

### 第二步：Diagnose（分层诊断）
按 OSI 七层模型从底层往上层排查：

| 层级 | 排查重点 | 排查命令/方法 |
|------|---------|--------------|
| 物理层 | 端口物理状态/链路/光功率 | display interface / show interface status |
| 数据链路层 | VLAN配置/MAC地址表/STP | display mac-address / show spanning-tree |
| 网络层 | IP连通性/路由表/ARP | ping / tracert / display ip routing-table |
| 传输层 | TCP/UDP 端口/会话状态 | telnet / netstat / display session table |
| 应用层 | 协议/域名/认证/证书 | nslookup / curl 测试 |

### 第三步：Action（行动解决）
1. 最小化变更验证原则
2. 变更前备份配置
3. 变更后完整验证
4. 记录故障根因与解决方案（更新到知识库）

---

## 网络常用基础命令参考

### Huawei 设备常用命令

```bash
display version           # 查看版本
display device            # 查看设备面板
display interface GigabitEthernet 0/0/1
display ip interface brief
display mac-address
display arp
display ip routing-table
display current-configuration
save                      # 保存配置
```

### Cisco 设备常用命令

```bash
show version
show inventory
show ip interface brief
show interface status
show mac address-table
show arp
show ip route
show running-config
write memory
```

### Linux 主机网络常用命令

```bash
ip addr
ip route
ping -c 4 8.8.8.8
traceroute -m 30 目标IP
netstat -anpt
tcpdump -i eth0 host 10.0.0.1
curl -v http://目标IP
nslookup www.example.com
systemctl status network
```

---

## 故障信息收集模板

收集完以下信息后，再寻求二线/厂家支持：

```
[ ] 1. 故障发生的准确时间（精确到分钟）
[ ] 2. 完整组网拓扑图（含网关/防火墙/路由）
[ ] 3. 故障点IP地址/VLAN信息
[ ] 4. ping/traceroute 截图
[ ] 5. 相关设备接口状态/计数
[ ] 6. 设备日志（Log）
[ ] 7. 最近的变更记录（72小时内）
[ ] 8. 是否可以复现？
```
