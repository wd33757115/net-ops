# Linux 系统运维常用命令与故障排查SOP

## 系统常用监控命令

### 快速看系统整体状态

```bash
# 看CPU、内存、负载
top
htop          # 更友好
uptime        # 1/5/15分钟负载
cat /proc/loadavg

# 内存使用
free -h
cat /proc/meminfo

# 看磁盘空间
df -h
df -i               # inode 使用量
du -sh *            # 当前目录各文件夹大小
ncdu               # 交互式磁盘分析

# 看进程
ps auxf
pstree
ps -efL | wc -l    # 线程总数
```

---

### 网络相关排查命令

```bash
# 接口与地址
ip addr
ip link
ip route show
ip neigh          # ARP表

ifconfig         # 旧命令也支持

# 连通性
ping -c 4 -i 0.2 目标IP      # 4个快速包看是否丢包
traceroute -T -p 80 目标IP   # TCP traceroute看端口通断
tracepath                     # UDP 路径

# 会话与端口
netstat -anpt
ss -tanp               # 同 netstat，输出更快
ss -tanp | grep LISTEN | wc -l   # 监听端口数量

lsof -i :80           # 看80端口被哪个进程占用

# 路由表
netstat -rn
route -n

# 域名解析
dig www.example.com
nslookup www.example.com
host www.example.com

# 抓包
tcpdump -i any -w test.pcap host 10.0.0.1 and port 443
tcpdump -i eth0 -nn -X udp port 53
```

---

## 常见故障场景与排查步骤

### 场景一：系统CPU使用率高

**CPU 高定位通用步骤：**

1. **定位哪个进程高**
```bash
top        # 按 P 排序 CPU占比最高
ps aux --sort=-%cpu | head -20
```

2. **该进程是用户态还是内核态？**
```bash
vmstat 1 10   #看 us sy id wa hi si 分项占比
```

3. **进程里的哪个线程高？**
```bash
top -H -p 进程PID    # 看具体线程TID
```

4. **perf 火焰图定位热点函数（生产定位神器）**
```bash
perf record -g -p 进程PID sleep 30
perf script | ./stackcollapse-perf.pl | ./flamegraph.pl > cpu.svg
```

5. **常见CPU高根因：**
| 占比高 | 典型原因 |
|-------|---------|
| us 高 | 死循环/正则回溯/GC/加密/计算密集 |
| sy 高 | 系统调用多/缺页/锁竞争/软中断 |
| wa 高 | IO 阻塞（磁盘IO等） |
| hi/si 高 | 中断多（报文量大） |

---

### 场景二：系统内存不足

```bash
# 内存整体分布
free -h

# 进程维度排序
ps aux --sort=-%mem | head -20

# 虚拟内存统计
vmstat 1

# 内存OOM日志
dmesg | grep -i "killed process\|oom-killer\|Out of memory"
grep -i oom /var/log/messages
```

**内存使用组成：**
- ✅ 进程 RSS
- ✅ Page Cache / Buffer （文件缓存可回收）
- ✅ Slab （内核元数据）

---

### 场景三：磁盘满 / 磁盘IO高

**磁盘满两步定位：**

1. **先看哪个分区满**
```bash
df -h
df -i      # 注意 inode 满也会报 No space left
```

2. **再看分区里哪个目录大**
```bash
du -sh /* 2>/dev/null | sort -hr
# 或用更友好：
ncdu /    # 强烈推荐
```

3. **注意：已删除文件仍占用句柄释放**
```bash
lsof | grep deleted
# 找到后重启相关进程释放
```

---

**磁盘IO高定位：**

1. **看IO 利用率/等待时间**
```bash
iostat -x 1       # %util 是不是100%满负荷
iotop             # 按进程看谁读写多
dstat             # 综合看各种指标
```

2. **内核态IO栈分析**
```bash
vmstat 1          #看 wa 项
pidstat -d 1      #进程维度磁盘IO统计
```

---

### 场景四：网络异常（连接失败/超时/断流）

**排障模型：分层排查法**

1. **二层连通性？（同VLAN内）**
   - 自己/对端 MAC 在 ARP 表中能看到？
   - 交换机端口/VLAN配置正确？

2. **三层可达？**
   - ping 网关通否？
   - `tracert -d`  traceroute 路径上哪跳不可达？
   - `ip route get 目标IP` 路由选路是否正确？
   - 回程路由对否？（防火墙/双网卡环境易踩坑）

3. **四层端口开放否？**
   ```bash
   telnet 目标IP 端口
   nc -zv 目标IP 端口范围
   nc -l 监听IP:端口    # 对端模拟监听看是否可达
   ```
   - SYN 发出去有 SYN+ACK 回来？（tcpdump/wireshark）
   - 还是只有 SYN 没有回包？（防火墙/安全组/路由）

4. **七层正常否？**
   ```bash
   curl -v http://目标IP
   curl -kv https://目标IP:443    # 忽略证书看握手过程
   ```
   - 证书？域名？Host头？编码？Content-Type 匹配？

5. **抓包确认（终极方案）**
```bash
tcpdump -i any -w /tmp/test.pcap host 10.0.0.1
# 拖到 Wireshark 里看包交互时序
```

---

## 日志查看

```bash
# 系统日志路径
/var/log/messages    # CentOS/RHEL
/var/log/syslog      # Debian/Ubuntu
journalctl -xe       # systemd journal

# 服务日志
/var/log/nginx/
/var/log/httpd/
/var/log/mysql/

# 实时监控日志
tail -f /var/log/nginx/access.log
multitail ...

# 日志检索
grep ERROR /var/log/xxx.log | head
awk /统计/分析/
```
