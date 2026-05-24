# 交换机端口Down故障处理标准操作程序

## 故障现象
交换机某一个或多个端口的物理/协议状态为Down，所连接服务器/设备无法正常通信。

---

## 故障处理步骤

### **Step 1: 确认端口状态并收集基础信息**

**Huawei:**
```bash
display interface GigabitEthernet 0/0/1
display interface brief
display logbuffer | include GigabitEthernet0/0/1
```

**Cisco:**
```bash
show interface GigabitEthernet 0/1
show ip interface brief
show logging | include Gi0/1
```

**收集关键点信息：**
1. 端口物理状态 (physical status)：up/down/!
2. 端口双工模式/速率自协商结果
3. 端口最近一次 up/down 时间
4. 端口入方向/出方向错包计数

---

### **Step 2: 物理层快速排查（80%的端口Down故障在这里）**

| 排查项 | 操作说明 |
|-------|---------|
| **插拔网线/光纤** | 物理重新拔插一次 |
| **更换网线/光纤** | 备用跳线替换，排除跳线问题 |
| **更换设备端口** | 对端设备也换个端口测试 |
| **光模块 DOM 信息** | 光模块查看光功率收/发光是否在阈值内 |

**光功率检查（华为）：**
```bash
display transceiver diagnosis interface GigabitEthernet 0/0/1
# 关注：
#   Tx Power 发送光功率 （正常-5 ~ 0 dBm左右）
#   Rx Power 接收光功率 （正常-12 ~ 0 dBm左右）
# 低于-20dBm 基本是链路衰耗过大
```

---

### **Step 3: 配置与协议层排查**

检查端口配置：
```bash
display current-configuration interface GigabitEthernet 0/0/1
```

**常见配置错误点：**
1. ✅ `shutdown` / `undo shutdown` 确认端口没有手动管理性关闭
2. ✅ 端口所属 VLAN 是否正确
3. ✅ 速率/双工模式强制配置与对端是否匹配
4. ✅ LACP 聚合组配置是否正确
5. ✅ 端口安全配置限制了MAC地址数量
6. ✅ 802.1x 认证端口状态是否正常

---

### **Step 4: 收集信息寻求更高层级支持**

如通过以上步骤仍无法定位根因，请准备好以下信息：

```
[ ] 1. 完整组网图
[ ] 2. display interface 完整信息
[ ] 3. display logbuffer 日志
[ ] 4. display trapbuffer 告警
[ ] 5. 两端设备配置对比
[ ] 6. 故障持续时间与影响业务范围
[ ] 7. 最近是否有割接/配置变更
```

---

## 临时规避方案

如为业务紧急恢复：
1. 有备用端口 → 切换到备用端口
2. 重要业务 → 临时跳纤绕开故障路径
3. 配合抓包确认报文收发方向

---

## 故障闭环

故障解决后：
1. ✅ 记录故障根因（Root Cause）
2. ✅ 记录解决方案及操作步骤
3. ✅ 更新到知识库避免重复踩坑
4. ✅ 涉及硬件故障 → 走返修RMA流程
5. ✅ 一周后再次回顾故障是否复现
