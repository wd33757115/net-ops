
# 常见网络日志模式

## Cisco IOS 日志

### 接口相关
- `%LINK-3-UPDOWN`: 接口状态变化
- `%LINEPROTO-5-UPDOWN`: 协议状态变化
- `%LINK-5-CHANGED`: 接口管理状态变化

### 路由相关
- `%OSPF-5-ADJCHG`: OSPF 邻居关系变化
- `%BGP-5-ADJCHANGE`: BGP 邻居关系变化
- `%Eigrp-5-NBRCHANGE`: EIGRP 邻居变化

### 安全相关
- `%SEC-6-IPACCESSLOGP`: 访问列表命中
- `%SSH-5-USER_AUTH_SUCCESS`: SSH 登录成功
- `%SSH-3-USER_AUTH_FAIL`: SSH 登录失败
- `%SYS-5-CONFIG_I`: 配置变更

## Huawei VRP 日志

### 接口相关
- `IFNET/4/LINKUPDOWN`: 接口状态变化
- `IFNET/4/IF_STATE`: 接口状态变化

### 路由相关
- `OSPF/4/NBR_CHANGE_E`: OSPF 邻居变化
- `BGP/6/ESTABLISHED`: BGP 邻居建立
- `BGP/3/NOTIFICATION`: BGP 通知

### 安全相关
- `SSH/5/SSH_USER_LOGIN`: SSH 登录
- `AAA/5/LOCALACCOUNT`: 本地账户事件

## 常见问题模式

### 频繁接口抖动
```
%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down
%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up
```
可能原因：链路问题、光模块故障、设备硬件问题

### OSPF 邻居频繁变化
```
%OSPF-5-ADJCHG: Process 1, Nbr 10.0.0.1 on GigabitEthernet0/1 from FULL to DOWN, Neighbor Down
%OSPF-5-ADJCHG: Process 1, Nbr 10.0.0.1 on GigabitEthernet0/1 from LOADING to FULL, Loading Done
```
可能原因：链路不稳定、Hello 包丢失、区域配置错误

### 登录失败
```
%SSH-3-USER_AUTH_FAIL: Authentication failed for user 'admin' from 192.168.1.100
```
可能原因：密码错误、账户锁定、权限问题
