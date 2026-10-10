# 强制锁频休息
import ctypes
from ctypes import wintypes
import math
import sys

sys.dont_write_bytecode = True
import time
import tkinter as tk
from tkinter import simpledialog
import keyboard
import paho.mqtt.client as mqtt

from common import python_box
from tools.server_box.mqtt.homeassistant_mq_entity import HomeAssistantEntity
from tools.server_box.mqtt.mqtt_utils import MqttBase


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class _Monitor:
    def __init__(self, width, height, x, y):
        self.width = width
        self.height = height
        self.x = x
        self.y = y


def get_monitors():
    """使用 Windows API 获取显示器边界，避免额外的 screeninfo 运行依赖。"""
    monitors = []
    if sys.platform != "win32":
        return monitors

    monitor_enum_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )

    def append_monitor(_monitor, _hdc, rect_pointer, _data):
        rect = rect_pointer.contents
        monitors.append(_Monitor(
            width=rect.right - rect.left,
            height=rect.bottom - rect.top,
            x=rect.left,
            y=rect.top,
        ))
        return True

    try:
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, monitor_enum_proc(append_monitor), 0
        )
    except (AttributeError, OSError):
        return []
    return monitors


def get_idle_seconds() -> float:
    """返回 Windows 最近一次键鼠输入距现在的秒数；读取失败时按 0 处理。"""
    try:
        info = _LastInputInfo()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint
        tick_count = ctypes.windll.kernel32.GetTickCount()
        return ((tick_count - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except (AttributeError, OSError):
        return 0.0


def classify_password_entry(entry_text, passwd, rest_finished):
    """返回密码解锁的含义：提前绕过、完成休息，或未匹配。"""
    if str(passwd) not in entry_text:
        return None
    return "completed" if rest_finished else "bypass"


def is_cycle_boundary(active_minutes, cycle_minutes):
    """判断累计工作分钟数是否处于周期边界，兼容小数配置。"""
    cycle_minutes = float(cycle_minutes)
    if cycle_minutes <= 0:
        return False
    remainder = float(active_minutes) % cycle_minutes
    tolerance = max(1e-9, abs(cycle_minutes) * 1e-9)
    return (math.isclose(remainder, 0.0, abs_tol=tolerance) or
            math.isclose(remainder, cycle_minutes, abs_tol=tolerance))


def minutes_until_cycle_boundary(active_minutes, cycle_minutes):
    """返回距下一个周期边界的分钟数；已在边界时返回一个完整周期。"""
    cycle_minutes = float(cycle_minutes)
    if cycle_minutes <= 0:
        return 0.0
    remainder = float(active_minutes) % cycle_minutes
    tolerance = max(1e-9, abs(cycle_minutes) * 1e-9)
    if (math.isclose(remainder, 0.0, abs_tol=tolerance) or
            math.isclose(remainder, cycle_minutes, abs_tol=tolerance)):
        return cycle_minutes
    return cycle_minutes - remainder


def should_relock_after_password(password_unlocked_at, relock_delay_minutes=10,
                                 relock_idle_seconds=60, now=None,
                                 idle_seconds=None) -> bool:
    """密码解锁后，达到延后时长或无人操作阈值时请求再次锁屏。"""
    if password_unlocked_at is None:
        return False

    now = time.monotonic() if now is None else now
    delay_minutes = float(relock_delay_minutes)
    idle_limit = float(relock_idle_seconds)
    delay_reached = delay_minutes > 0 and (
        now - password_unlocked_at >= delay_minutes * 60
    )

    idle_reached = False
    if idle_limit > 0:
        idle_seconds = get_idle_seconds() if idle_seconds is None else idle_seconds
        idle_reached = idle_seconds >= idle_limit
    return delay_reached or idle_reached


def wait_for_password_relock(wait_seconds, password_unlocked_at,
                             relock_delay_minutes=10,
                             relock_idle_seconds=60,
                             poll_interval=1) -> bool:
    """等待工作片段；密码解锁后的重锁条件满足时提前返回 True。"""
    wait_seconds = max(0.0, float(wait_seconds))
    if password_unlocked_at is None:
        time.sleep(wait_seconds)
        return False

    end_at = time.monotonic() + wait_seconds
    while True:
        now = time.monotonic()
        if should_relock_after_password(
                password_unlocked_at,
                relock_delay_minutes=relock_delay_minutes,
                relock_idle_seconds=relock_idle_seconds,
                now=now):
            return True
        remaining = end_at - now
        if remaining <= 0:
            return False
        time.sleep(min(max(0.1, float(poll_interval)), remaining))


def _set_edge_window_non_activating(root):
    """让边缘提示不抢焦点，并允许鼠标点击穿透。"""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        hwnd = wintypes.HWND(root.winfo_id())
        parent_hwnd = user32.GetParent(hwnd)
        if parent_hwnd:
            hwnd = parent_hwnd
        gwl_exstyle = -20
        ws_ex_transparent = 0x00000020
        ws_ex_toolwindow = 0x00000080
        ws_ex_noactivate = 0x08000000
        get_window_long = (user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8
                           else user32.GetWindowLongW)
        set_window_long = (user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8
                           else user32.SetWindowLongW)
        get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_ssize_t
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_window_long.restype = ctypes.c_ssize_t
        style = get_window_long(hwnd, gwl_exstyle)
        set_window_long(
            hwnd,
            gwl_exstyle,
            style | ws_ex_transparent | ws_ex_toolwindow | ws_ex_noactivate,
        )
    except (AttributeError, OSError):
        pass


def show_countdown_warning(countdown_duration=60, expanded_duration=3):
    """在屏幕右上边缘短暂提示，然后缩成细线直到进入锁屏。"""
    root = tk.Tk()
    root.title("休息提示")
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    try:
        root.attributes('-alpha', 0.9)
    except tk.TclError:
        pass

    expanded_width = 180
    expanded_height = 34
    line_width = 72
    line_height = 4
    margin = 8
    bg_color = "#343A40"
    line_color = "#78909C"

    root.configure(background=bg_color)
    screen_width = root.winfo_screenwidth()
    x = screen_width - expanded_width - margin
    root.geometry(f"{expanded_width}x{expanded_height}+{x}+{margin}")

    label = tk.Label(
        root,
        text="1分钟后暂停",
        font=('Microsoft YaHei UI', 10),
        bg=bg_color,
        fg="#F1F3F5",
        padx=12,
        pady=6,
    )
    label.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    _set_edge_window_non_activating(root)

    def collapse_to_line():
        try:
            label.pack_forget()
            root.configure(background=line_color)
            line_x = screen_width - line_width - margin
            root.geometry(f"{line_width}x{line_height}+{line_x}+{margin}")
        except tk.TclError:
            pass

    def finish_warning():
        try:
            root.destroy()
        except tk.TclError:
            pass

    duration_ms = max(0, int(float(countdown_duration) * 1000))
    expanded_ms = min(duration_ms, max(0, int(float(expanded_duration) * 1000)))
    root.after(expanded_ms, collapse_to_line)
    root.after(duration_ms, finish_warning)
    try:
        root.mainloop()
    except tk.TclError:
        pass
    return True


def run_lock_retry_cycle(lock_duration, passwd, alpha=1, mut_monitor=True,
                         warning_duration=60, warning_expanded_duration=3,
                         relock_delay_minutes=10, relock_idle_seconds=60,
                         on_active_minute=None, warning_fn=None, lock_fn=None,
                         wait_fn=None, clock=None) -> int:
    """运行一次完整休息；密码解锁只延后，直到正常完成才返回。"""
    warning_fn = show_countdown_warning if warning_fn is None else warning_fn
    lock_fn = lock_screen if lock_fn is None else lock_fn
    wait_fn = wait_for_password_relock if wait_fn is None else wait_fn
    clock = time.monotonic if clock is None else clock
    bypass_count = 0

    while True:
        warning_fn(
            countdown_duration=warning_duration,
            expanded_duration=warning_expanded_duration,
        )
        used_password = lock_fn(
            duration=lock_duration,
            passwd=passwd,
            require_confirm=True,
            alpha=alpha,
            mut_monitor=mut_monitor,
        )
        if not used_password:
            return bypass_count

        bypass_count += 1
        if float(relock_delay_minutes) <= 0 and float(relock_idle_seconds) <= 0:
            return bypass_count
        password_unlocked_at = clock()
        accounted_minutes = 0
        while True:
            relock_requested = wait_fn(
                1,
                password_unlocked_at,
                relock_delay_minutes=relock_delay_minutes,
                relock_idle_seconds=relock_idle_seconds,
            )
            elapsed_minutes = int((clock() - password_unlocked_at) // 60)
            while accounted_minutes < elapsed_minutes:
                if on_active_minute is not None:
                    on_active_minute()
                accounted_minutes += 1
            if relock_requested:
                break

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
    monitors = get_monitors()
    if not monitors:
        monitors = [_Monitor(
            root_tk.winfo_screenwidth(), root_tk.winfo_screenheight(), 0, 0
        )]
    for i, m in enumerate(monitors):
        if i == 0:
            root = root_tk
        else:
            if not mut_monitor:
                break
            root = tk.Toplevel(root_tk)
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.geometry(f"{m.width}x{m.height}{m.x:+d}{m.y:+d}")
        
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

        win_hook = keyboard.hook_key("windows", lambda x: print(x), suppress=True)
        alt_hook = keyboard.hook_key("alt", lambda x: print(x), suppress=True)
        
        def close():
            try:
                root_tk.destroy()
            except Exception:
                pass
            try:
                keyboard.unhook_all()
            except Exception:
                pass

        
        btn_confirm = tk.Button(root, text="确认", font=('Arial', 12, 'bold'), 
                            command=close, width=15, bg='#2196F3', fg='white', state=tk.DISABLED)
        
        start_ts = time.monotonic()
        def check_input(entry=entry, entry_var=entry_var, start_ts=start_ts, duration=duration, passwd=passwd, require_confirm=require_confirm, time_var=time_var, btn_confirm=btn_confirm, i=i):
            rest_finished = time.monotonic() - start_ts >= duration * 60
            password_action = classify_password_entry(
                entry_var.get(), passwd, rest_finished
            )
            if password_action is not None:
                # 计时前输入密码是提前绕过；计时后输入密码则算完整休息。
                unlocked['v'] = password_action == "bypass"
                close()
                return

            if rest_finished:
                if not require_confirm:
                    close()
                    return
                if btn_confirm['state'] == tk.DISABLED:
                    btn_confirm['state'] = tk.NORMAL
                    btn_confirm.pack(pady=20)
                    entry.focus_set()
                # 保持密码框可用，等待密码或确认按钮关闭休息页。
                root.after(300, check_input, entry, entry_var, start_ts, duration, passwd, require_confirm, time_var, btn_confirm, i)
                return

            
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
    warning_time = "warning_time"
    warning_expanded_time = "warning_expanded_time"
    password_relock_time = "password_relock_time"
    password_relock_idle = "password_relock_idle"
    print("Lock Relax started.")
    day_config = python_box.read_config("%s" % data_save, {("%s" % day_time): 0, ("%s" % today): _get_today(), startup_count: 0})
    config = python_box.read_config("config/config_lock_relax.ini",
                                        {("%s" % host): "localhost",
                                         ("%s" % port): "1883",
                                         ("%s" % message): "0#是否发送消息1 0", lock_time: 5, ("%s" % unlock_time): 25,
                                         ("%s" % loop): 48, ("%s" % passwd): 123,
                                         ("%s" % day_limit): 100,
                                         ("%s" % restore_status): 1, ("%s" % alpha): 1, ("%s" % mut_monitor): 1,
                                         warning_time: 60, warning_expanded_time: 3,
                                         password_relock_time: 10, password_relock_idle: 60},
                                    apend_default=True)
    warning_duration_seconds = 60.0
    warning_expanded_seconds = 3.0
    password_relock_minutes = 10.0
    password_relock_idle_seconds = 60.0
    try:
        if not config:
            log_msg("请配置并重新运行")
            sys.exit(0)
        warning_duration_seconds = float(config.get(warning_time, 60))
        warning_expanded_seconds = float(config.get(warning_expanded_time, 3))
        password_relock_minutes = float(config.get(password_relock_time, 10))
        password_relock_idle_seconds = float(config.get(password_relock_idle, 60))
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

        def record_active_minute(minutes=1):
            day_config[day_time] = round(
                float(day_config.get(day_time, 0)) + float(minutes), 10
            )
            python_box.write_config(day_config, data_save)
            if send_state:
                entity_lock.send_sensor_state(day_config[day_time])

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
            completed_lock = False
            if not first_run:
                first_run = False
                restore_lock = (
                    config.get(restore_status) != 1 or
                    is_cycle_boundary(
                        day_config.get(day_time, 0), config.get(unlock_time)
                    ) or
                    float(day_config.get(day_time)) >= float(config.get(day_limit))
                )  # 恢复状态：解锁时间处于周期边界
                if float(config.get(lock_time)) != 0 and restore_lock:
                    # 密码可立即解锁，但只会延后；到时或无人操作后重新走预警和锁屏。
                    run_lock_retry_cycle(
                        lock_duration=float(config.get(lock_time)),
                        passwd=config.get(passwd),
                        alpha=float(config.get(alpha)),
                        mut_monitor=config.get(mut_monitor),
                        warning_duration=warning_duration_seconds,
                        warning_expanded_duration=warning_expanded_seconds,
                        relock_delay_minutes=password_relock_minutes,
                        relock_idle_seconds=password_relock_idle_seconds,
                        on_active_minute=record_active_minute,
                    )
                    use_passwd = False
                    completed_lock = True
            # 解锁
            unlock_duration = float(config.get(unlock_time))
            if config.get(restore_status) == 1 and not completed_lock:
                remaining_work = minutes_until_cycle_boundary(
                    day_config.get(day_time, 0), unlock_duration
                )
            else:
                remaining_work = max(0.0, unlock_duration)
            while remaining_work > 1e-9:
                if not use_passwd and float(day_config.get(day_time)) >= float(config.get(day_limit)):  # 判断解锁时间是否超过
                    break  # 不使用密码超过则直接退出循环
                work_chunk = min(1.0, remaining_work)
                time.sleep(work_chunk * 60)
                record_active_minute(work_chunk)
                remaining_work = max(0.0, remaining_work - work_chunk)
    except Exception as e:
        log_msg(e)
        for i in range(100):
            run_lock_retry_cycle(
                lock_duration=30,
                passwd=config.get(passwd),
                alpha=float(config.get(alpha)),
                mut_monitor=config.get(mut_monitor),
                warning_duration=warning_duration_seconds,
                warning_expanded_duration=warning_expanded_seconds,
                relock_delay_minutes=password_relock_minutes,
                relock_idle_seconds=password_relock_idle_seconds,
            )




if __name__ == '__main__':
    main()
