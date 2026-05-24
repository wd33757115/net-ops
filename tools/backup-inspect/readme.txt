#导入设备信息到sqllite
python device_manager.py --import-excel --devices test.xlsx
#执行巡检脚本
python ssh_device.py --group 你的分组名 --log-level INFO



#环境安装
1.先到python官网下载python3.10版本以上，安装到自己电脑上；如果堡垒机已安装了python且版本大于3.10下载和堡垒机版本已知的python安装包
https://www.python.org/downloads/windows/
2.#升级pip
在有网的电脑上下载
mkdir C:\wheels_pip
python -m pip download pip==26.0.1 --no-deps -d C:\wheels_pip
拷贝到堡垒机离线升级
python -m pip install --no-index --find-links D:\wheels_pip pip==26.0.1
python -m pip --version
#在有网的电脑上下载netmiko pandas openpyxl filelock安装包
mkdir C:\wheels
pip download netmiko pandas openpyxl -d C:\wheels
拷贝到堡垒机安装
cd C:\wheels
pip install --no-index --find-links C:\wheels netmiko pandas openpyxl


#导入设备信息到sqllite
python device_manager.py --import-excel --devices test.xlsx
#执行巡检脚本
cd c:\ssh1
python ssh_device.py --group 你的分组名 --log-level INFO
存在多个python脚本用绝对路径调用python.exe
