# 强制锁频休息
import ctypes
import sys
import time

import PySimpleGUI as sg

from common import python_box
import keyboard


def lock_screen(duration=0.2, passwd=None, **kwargs) -> bool:
    """
    锁屏ui
    :param duration:
    :param passwd:
    :param kwargs:
    :return: 是否密码解锁
    """
    key_input = "input"
    bk_color = "#3C3F41"
    user32 = ctypes.windll.user32
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    timer = sg.Text(time.strftime("%Y-%m-%d", time.localtime()),
                    key="_time_",
                    justification='center',
                    font=f"any {int(screensize[0] / 10)}",
                    background_color=bk_color
                    )
    gui_input = sg.Input(key=key_input, password_char="*")
    column = [
        [timer, ],
        [gui_input, ],
    ]
    layout = [[sg.VPush(background_color=bk_color)],
              [sg.Push(background_color=bk_color),
               sg.Column(column, element_justification='c', background_color=bk_color),
               sg.Push(background_color=bk_color)],
              [sg.VPush(background_color=bk_color)]]
    window = sg.Window('Stand Up And Drink Water',
                       layout,
                       no_titlebar=True,
                       keep_on_top=True,
                       disable_close=True,
                       disable_minimize=True,
                       grab_anywhere=False,
                       background_color=bk_color,
                       alpha_channel=1,
                       size=screensize
                       )
    start = time.time()
    keyboard.hook_key("windows", lambda x : print(x), True)
    while True:
        event, values = window.Read(timeout=300)
        if time.time() - start > duration * 60:
            window.close()
            keyboard.unhook_key("windows")
            return False
        if values.get(key_input) == passwd:
            window.close()
            keyboard.unhook_key("windows")
            return True


def _get_today():
    return python_box.date_format(fmt="%Y%m%d")


if __name__ == '__main__':
    loop = "loop"
    lock_time = "lock_time"
    unlock_time = "unlock_time"
    day_time = "day_time"
    today = "today"
    config_log_ini = "config/log.ini"
    day_config = python_box.read_config("%s" % config_log_ini, {("%s" % day_time): 0, ("%s" % today): _get_today()})
    day_limit = "day_limit"
    passwd = "passwd"
    config = python_box.read_config("config/config.ini",
                                    {lock_time: 5, ("%s" % unlock_time): 25, ("%s" % loop): 48, ("%s" % passwd): 123,
                                     ("%s" % day_limit): 100}, )
    if not config:
        print("请配置并重新运行")
        sys.exit(0)
    for _ in range(int(config.get(loop))):
        first_run = None
        use_passwd = None
        day_config = python_box.read_config(config_log_ini)
        if day_config.get(today) != _get_today():
            day_config[today] = _get_today()
            day_config[day_time] = 0
            first_run = True
        if not first_run:
            use_passwd = lock_screen(duration=float(config.get(lock_time)), passwd=config.get(passwd))
            first_run = False
        overtime = float(day_config.get(day_time)) >= float(config.get(day_limit))
        if not overtime or use_passwd or (overtime and use_passwd):
            r = float(config.get(unlock_time))
            time.sleep(r * 60)
            day_config[day_time] = float(day_config.get(day_time)) + r
        python_box.write_config(day_config, config_log_ini)
