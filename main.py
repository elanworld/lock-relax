# 强制锁频休息
import ctypes
import sys
import time

import PySimpleGUI
import pyautogui

from common import python_box


def lock_screen(duration=0.2, passwd=None, **kwargs):
    key_input = "input"
    key_quit = "确认"
    bk_color = "#3C3F41"
    user32 = ctypes.windll.user32
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    timer = PySimpleGUI.Text(time.strftime("%Y-%m-%d", time.localtime()),
                             key="_time_",
                             background_color=bk_color,
                             size=(10, 1),
                             text_color="")
    gui_input = PySimpleGUI.Input(key=("%s" % key_input))
    btn_quit = PySimpleGUI.Button(button_color=('black', 'orange'), button_text=key_quit)

    column = [[timer], [gui_input, btn_quit], ]
    layout = [[PySimpleGUI.Column(column, background_color=bk_color)]]

    window = PySimpleGUI.Window('Stand Up And Drink Water',
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
    while True:
        event, values = window.Read(timeout=3000)
        pyautogui.keyDown("esc")
        pyautogui.keyUp("esc")
        if time.time() - start > duration * 60 or values.get(key_input) == passwd:
            window.close()
            break


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
                                    {lock_time: 5, ("%s" % unlock_time): 25, ("%s" % loop): 10, ("%s" % passwd): 123,
                                     ("%s" % day_limit): 1}, )
    if not config:
        print("请配置并重新运行")
        sys.exit(0)
    for _ in range(int(config.get(loop))):
        lock_screen(duration=float(config.get(lock_time)), passwd=config.get(passwd))
        day_config = python_box.read_config(config_log_ini)
        if day_config.get(today != _get_today()):
            day_config.update[today] = _get_today()
            day_config.update[day_time] = 0
        if float(day_config.get(day_time)) < float(config.get(day_limit)):
            r = float(config.get(unlock_time))
            time.sleep(r * 60)
            day_config[day_time] = float(day_config.get(day_time)) + r
        python_box.write_config(day_config, config_log_ini)
