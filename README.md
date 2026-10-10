## 锁屏休息工具

用途
- 提醒小孩子停止玩电脑，放松休息
- 提醒自己休息
- 有强制锁屏功能
- 可密码解锁

配置
- 运行一次后生成配置文件config.ini
  - lock_time=5 #锁屏时间
  - unlock_time=25 #解锁时间
  - loop=48 #循环次数
  - passwd=123 # 解锁密码
  - day_limit=100 # 每天限制使用时间
  - warning_time=60 # 锁屏前边缘提示持续秒数
  - warning_expanded_time=3 # 完整提示显示秒数，随后缩成细线
  - password_relock_time=10 # 密码解锁后多少分钟再次进入锁屏流程
  - password_relock_idle=60 # 密码解锁后无人操作多少秒再次进入锁屏流程

密码可以立即解锁，但只会延后本次休息；达到延后时间或无人操作阈值后，程序会重新显示边缘提示并进入锁屏。
