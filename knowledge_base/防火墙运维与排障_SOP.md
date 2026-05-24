# 防火墙运维与故障排障SOP

## 防火墙运维日常健康检查

建议每周/每月巡检必做检查项目：

### **设备运行状态**

| 检查项 | 正常阈值 |
|-------|---------|
| CPU 使用率 | < 70% |
| 内存使用率 | < 80% |
| 会话数量 | < 设备最大会话数70% |
| 主备状态 | 双机环境为热备状态 |
| HA 心跳链路 | 连通正常 |
| 接口丢包率 | < 0.01% |
| IPS/AV 特征库版本 | 在官网有效期内 |

**Huawei USG:**
```bash
display cpu-usage
display memory-usage
display firewall session table
display hrp state
display health
display security-policy rule all
display logbuffer level warning
```

**Palo Alto:**
```bash
show system resources
show session info
show high-availability state
show log system direction equal backward
```

---

## 常见故障场景与排查

### **故障场景1：业务不通/被防火墙阻断**

**排查方法论（按优先级）：**

1. **看会话 (Session)** → 检查会话是否能建立
```bash
display firewall session table source inside 10.0.0.1 destination outside 8.8.8.8
```
  - 有会话 → 防火墙已放行，后续排查路由/NAT/服务器
  - 无会话 → 访问没到墙/被安全策略拒绝，往下看

2. **看安全策略命中数** → 查策略是否匹配
```bash
display security-policy rule name 策略名称
# 看 hit count 计数是否增长
```

3. **看 Policy 日志** → 看系统日志是否有 Deny
```bash
display logbuffer | include policy
display firewall blacklist item   # 检查是否被临时拉黑
```

4. **模拟报文测试 (Policy Test)**
```bash
# USG 策略匹配测试
system-view
security-policy
test policy source 10.0.0.1 destination 8.8.8.8 service 80
# 返回：允许/拒绝，并命中哪条规则
```

---

### **故障场景2：SNAT/DNAT 不生效**

NAT 排障四步：

**Step 1: 检查 NAT 配置是否正确**
- 源NAT：NAT 地址池/不做PAT/直接使用出接口地址
- 目的NAT：Server-Map 表项

**Step 2: 查看 Server Map 表项**
```bash
display firewall server-map
display nat all
display nat address-group 地址池名称
```

**Step 3: 会话表看NAT转换是否生效**
```bash
display firewall session table verbose  # 看 -> 符号前后地址变化
```

**Step 4: 查看是否有命中计数**
```bash
display nat policy rule all
```

---

### **故障场景3：防火墙高可用 HA 切换排查**

**正常HA状态验证标准：**

1. 主备角色正确
```bash
display hrp state
display hrp interface      # 检查心跳接口
```

2. 配置同步正常
```bash
display hrp configuration check
```

3. 会话备份正常 → 切换业务不中断

**发生主备切换后必做检查：**
- 业务是否自动恢复？
- 查看切换原因（断电/手动/报文丢包/接口Down）
- 查看双机热备日志
- 确认会话数量是否逐步恢复

---

### **故障场景4：IPS/AV 特征库误杀阻断**

**怀疑特征库误判时的验证：**

1. 临时 bypass IPS 策略看是否恢复
2. 查看威胁日志：
```bash
display log type threat
```
3. 看威胁ID是否是误判
4. 如确认是误判，加入例外/自定义签名豁免：
```bash
security-policy
  rule name 业务
    profile av exempt 威胁ID列表
```

---

## 信息收集模板（防火墙Case）

联系厂家TAC时请准备好：

```
[ ] 1. display diagnostic-information 完整诊断信息
[ ] 2. 组网图（安全区域/路由/NAT规划）
[ ] 3. display hrp state （双机环境）
[ ] 4. display interface 接口状态
[ ] 5. display cpu/memory 资源使用
[ ] 6. display security-policy 相关策略配置
[ ] 7. display logbuffer 日志
[ ] 8. 测试抓包（PCAP文件）
[ ] 9. 业务影响范围与是否可复现
[ ] 10. 现象描述/时间线
```
