# 强制锁频休息
import ctypes
import sys

from screeninfo import get_monitors
sys.dont_write_bytecode = True
import time
import tkinter as tk
from tkinter import simpledialog
import keyboard
import paho.mqtt.client as mqtt

from common import python_box
from tools.server_box.mqtt.homeassistant_mq_entity import HomeAssistantEntity
from tools.server_box.mqtt.mqtt_utils import MqttBase


def show_countdown_warning(countdown_duration=30):
    """显示30秒倒计时警告窗口，提示即将进入锁屏。
    用户可以点击"开始"提前进入，或等待倒计时结束自动进入。
    
    :param countdown_duration: 倒计时秒数（默认30）
    :return: True 表示用户点击了"开始"或倒计时结束
    """
    result = {'ready': False}
    
    root = tk.Tk()
    root.title("锁屏警告")
    root.geometry("400x200")
    root.attributes('-topmost', True)
    
    # 居中显示
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 200
    y = (root.winfo_screenheight() // 2) - 100
    root.geometry(f"+{x}+{y}")
    
    # 倒计时标签
    countdown_var = tk.StringVar(value=str(countdown_duration))
    lbl_countdown = tk.Label(root, textvariable=countdown_var, 
                             font=('Arial', 72, 'bold'), fg='red')
    lbl_countdown.pack(pady=20)
    
    # 提示文字
    lbl_info = tk.Label(root, text='即将进入锁屏\n点击"开始"或等待倒计时结束', 
                        font=('Arial', 14))
    lbl_info.pack(pady=10)
    
    # 按钮框
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=20)
    
    def on_start():
        result['ready'] = True
        try:
            root.destroy()
        except Exception:
            pass
    
    btn_start = tk.Button(btn_frame, text="开始", font=('Arial', 12, 'bold'), 
                          command=on_start, width=15, bg='#FF6B6B', fg='white')
    btn_start.pack(side=tk.LEFT, padx=10)
    
    # 倒计时逻辑
    remaining = [countdown_duration]
    
    def update_countdown():
        if remaining[0] <= 0:
            result['ready'] = True
            try:
                root.destroy()
            except Exception:
                pass
            return
        
        countdown_var.set(str(remaining[0]))
        remaining[0] -= 1
        root.after(1000, update_countdown)
    
    root.after(1000, update_countdown)
    try:
        root.mainloop()
    except Exception:
        pass
    
    return result['ready']

def lock_screen(duration=0.2, passwd=None, require_confirm=False, alpha=1, mut_monitor=True, **kwargs) -> bool:
    """
    锁屏ui (tkinter 实现，替代 PySimpleGUI)
    :param duration: 锁屏时长：分
    :param passwd: 密码
    :param require_confirm: 是否需要点击确认按钮才能关闭（默认False）
    :param kwargs:
    :return: 是否密码解锁
    """
    if duration == 0:
        return False
        
    bk_color = "#3C3F41"
    
    unlocked = {'v': False}
    root_tk = tk.Tk()
    for i, m in enumerate(get_monitors()):
        if i == 0:
            root = root_tk
        else:
            if not mut_monitor:
                break
            root = tk.Toplevel(root_tk)
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
        
        if alpha < 1 and alpha >= 0:
            root.attributes("-alpha", alpha)
        root.configure(background=bk_color)
        font_size = max(12, int(m.width / 15))
        
        # 日期时间标签
        time_var = tk.StringVar(value=time.strftime("%Y-%m-%d", time.localtime()))
        lbl = tk.Label(root, textvariable=time_var, font=('Arial', font_size), 
                    bg=bk_color, fg="white")
        lbl.pack(expand=True, pady=20)
        
        # 密码输入框
        entry_var = tk.StringVar()
        entry = tk.Entry(root, textvariable=entry_var, show='*', 
                        font=('Arial', int(font_size/10)), width=30)
        entry.pack(pady=30)
        entry.focus_set()

        keyboard.hook_key("windows", lambda x: print(x), True)
        keyboard.hook_key("alt", lambda x: print(x), True)
        
        def close():
            try:
                keyboard.unhook_key("windows")
                keyboard.unhook_key("alt")
            except Exception:
                pass
            try:
                root_tk.destroy()
            except Exception:
                pass

        
        btn_confirm = tk.Button(root, text="确认", font=('Arial', 12, 'bold'), 
                            command=close, width=15, bg='#2196F3', fg='white', state=tk.DISABLED)
        
        start_ts = time.time()
        def check_input(entry=entry, entry_var=entry_var, start_ts=start_ts, duration=duration, passwd=passwd, require_confirm=require_confirm, time_var=time_var, btn_confirm=btn_confirm, i=i):
            # Check password
            if entry_var.get() == str(passwd):
                unlocked['v'] = True
                # 如果需要确认，等待用户点击按钮；否则直接关闭
                close()
                return
            
            # Check timeout
            if time.time() - start_ts > duration * 60:
                if not require_confirm:
                    close()
                    return
                else:
                    if btn_confirm['state'] == tk.DISABLED:
                        btn_confirm['state'] = tk.NORMAL
                        btn_confirm.pack(pady=20)
                        entry['show'] = ''
                        entry_var.set("⏱ 时间已到，请点击确认")
            
            # Update time label
            time_var.set(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            root.after(300, check_input, entry, entry_var, start_ts, duration, passwd, require_confirm, time_var, btn_confirm, i)
        
        root.after(300, check_input, entry, entry_var, start_ts, duration, passwd, require_confirm, time_var, btn_confirm, i)
    try:
        root_tk.mainloop()
    except Exception:
        pass
    
    return bool(unlocked['v'])


def _get_today():
    return python_box.date_format(fmt="%Y%m%d")


def will_set(client: mqtt.Client):
    tmp = HomeAssistantEntity(None, "lock")
    client.will_set(tmp.status_topic, "offline")


def log_msg(msg):
    python_box.log(msg, file="config/log_lock_relax_console.log")

def for_generate_code():
    MqttBase
    python_box.read_config
    python_box.random_str

def main():
    loop = "loop"
    lock_time = "lock_time"
    unlock_time = "unlock_time"
    day_time = "day_time" + _get_today()
    today = "today"
    data_save = "config/data_lock_relax.ini"
    startup_count = "startup count"
    day_limit = "day_limit"
    passwd = "passwd"
    host = "mq host"
    port = "mq port"
    message = "send message"
    restore_status = "restore status"
    alpha = "alpha"
    mut_monitor = "muti monitor"
    print("Lock Relax started.")
    day_config = python_box.read_config("%s" % data_save, {("%s" % day_time): 0, ("%s" % today): _get_today(), startup_count: 0})
    config = python_box.read_config("config/config_lock_relax.ini",
                                        {("%s" % host): "localhost",
                                         ("%s" % port): "1883",
                                         ("%s" % message): "0#是否发送消息1 0", lock_time: 5, ("%s" % unlock_time): 25,
                                         ("%s" % loop): 48, ("%s" % passwd): 123,
                                         ("%s" % day_limit): 100,
                                        ("%s" % restore_status): 1, ("%s" % alpha): 1, ("%s" % mut_monitor): 1}, )
    try:
        if not config:
            log_msg("请配置并重新运行")
            sys.exit(0)
        send_state = config.get(message) == 1
        day_config[startup_count] = day_config.get(startup_count, 0) + 1
        log_msg(fr"config: {config}")
        if send_state:
            try:
                base = MqttBase(config.get(host), config.get(port), None, will_set)
                entity_lock = HomeAssistantEntity(base, "lock")
                entity_lock.send_sensor_config_topic("lock", "锁屏时间", "分钟", keep=True, expire_after=None)
                entity_start_count = HomeAssistantEntity(base, "lock")
                entity_start_count.send_sensor_config_topic("start", "锁屏启动次数", "次", keep=True, expire_after=None)
                entity_online = HomeAssistantEntity(base, "lock")
                entity_online.send_switch_config_topic("lock_state", "锁屏在线")
            except Exception as e:
                log_msg(e)
                send_state = False
        for _ in range(int(config.get(loop))):
            # 首次运行
            first_run = None
            use_passwd = None
            if day_time not in day_config:
                day_config[day_time] = 0
            if send_state:
                entity_lock.send_sensor_state(day_config[day_time])
                entity_start_count.send_sensor_state(day_config[startup_count])
                entity_online.send_switch_state(True)
            if str(day_config.get(today)) != _get_today():
                day_config[today] = _get_today()
                day_config[day_time] = 0
                first_run = True
            else:
                if day_config[day_time] == 0:
                    first_run = True
            python_box.write_config(day_config, data_save)
            # 锁屏 - 显示倒计时警告后进入锁屏
            if not first_run:
                first_run = False
                restore_lock = True if config.get(restore_status) != 1 else float(day_config.get(day_time, 0)) % float(config.get(unlock_time)) == 0 or float(day_config.get(day_time)) >= float(config.get(day_limit)) # 恢复状态 解锁时间处于周期边界
                if float(config.get(lock_time)) != 0 and restore_lock == True:
                    # 显示30秒倒计时警告
                    show_countdown_warning(countdown_duration=30)
                    use_passwd = lock_screen(duration=float(config.get(lock_time)), passwd=config.get(passwd), require_confirm=True, alpha=float(config.get(alpha)), mut_monitor=config.get(mut_monitor))
                    day_config[day_time] = float(day_config.get(day_time)) + 1
            # 解锁
            unlock_duration = float(config.get(unlock_time))
            for i in range(int(unlock_duration if unlock_duration >= 1 else 1)):  # 测试至少循环一次
                if not use_passwd and float(day_config.get(day_time)) >= float(config.get(day_limit)):  # 判断解锁时间是否超过
                    break  # 不使用密码超过则直接退出循环
                if config.get(restore_status) == 1 and float(day_config.get(day_time, 0)) != 0 and float(day_config.get(day_time, 0)) % float(config.get(unlock_time)) == 0:
                    break  # 解锁周期边界
                time.sleep(60 if unlock_duration >= 1 else unlock_duration * 60)
                day_config[day_time] = float(day_config.get(day_time)) + 1
                python_box.write_config(day_config, data_save)
                if send_state:
                    entity_lock.send_sensor_state(day_config[day_time])
    except Exception as e:
        log_msg(e)
        for i in range(100):
            res = lock_screen(duration=30, passwd=config.get(passwd), require_confirm=True, alpha=float(config.get(alpha)), mut_monitor=config.get(mut_monitor) )
            if res:
                time.sleep(10 * 60)




if __name__ == '__main__':
    main()