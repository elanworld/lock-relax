# 强制锁频休息
import ctypes
import sys
import time

import PySimpleGUI as sg
import keyboard
import paho.mqtt.client as mqtt

from common import python_box
from tools.server_box.homeassistant_mq_entity import HomeAssistantEntity
from tools.server_box.mqtt_utils import MqttBase


def lock_screen(duration=0.2, passwd=None, **kwargs) -> bool:
    """
    锁屏ui
    :param duration: 锁屏时长：分
    :param passwd:
    :param kwargs:
    :return: 是否密码解锁
    """
    if duration == 0:
        return False
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
    keyboard.hook_key("windows", lambda x: print(x), True)
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


def will_set(client: mqtt.Client):
    tmp = HomeAssistantEntity(None, "lock")
    client.will_set(tmp.status_topic, "offline")


if __name__ == '__main__':
    loop = "loop"
    lock_time = "lock_time"
    unlock_time = "unlock_time"
    day_time = "day_time" + _get_today()
    today = "today"
    config_log_ini = "config/log.ini"
    day_config = python_box.read_config("%s" % config_log_ini, {("%s" % day_time): 0, ("%s" % today): _get_today()})
    day_limit = "day_limit"
    passwd = "passwd"
    host = "mq host"
    port = "mq port"
    message = "send message"
    config = python_box.read_config("config/config.ini",
                                    {("%s" % host): "localhost",
                                     ("%s" % port): "1883",
                                     ("%s" % message): "0#是否发送消息1 0", lock_time: 5, ("%s" % unlock_time): 25,
                                     ("%s" % loop): 48, ("%s" % passwd): 123,
                                     ("%s" % day_limit): 100}, )
    try:
        if not config:
            print("请配置并重新运行")
            sys.exit(0)
        send_state = config.get(message) == "1"
        if send_state:
            try:
                base = MqttBase(config.get(host), int(config.get(port)), None, will_set)
                entity_lock = HomeAssistantEntity(base, "lock")
                entity_lock.send_sensor_config_topic("lock", "锁屏时间", "分钟", keep=True, expire_after=None)
                entity_online = HomeAssistantEntity(base, "lock")
                entity_online.send_switch_config_topic("lock_state", "锁屏在线")
            except Exception as e:
                print(e)
                send_state = False
        for _ in range(int(config.get(loop))):
            # 首次运行
            first_run = None
            use_passwd = None
            day_config = python_box.read_config(config_log_ini)
            if day_time not in day_config:
                day_config[day_time] = 0
            if send_state:
                entity_lock.send_sensor_state(day_config[day_time])
                entity_online.send_switch_state(True)
            if day_config.get(today) != _get_today():
                day_config[today] = _get_today()
                day_config[day_time] = 0
                first_run = True
            # 锁屏
            if not first_run:
                first_run = False
                if float(config.get(lock_time)) != 0:
                    use_passwd = lock_screen(duration=float(config.get(lock_time)), passwd=config.get(passwd))
            # 解锁
            r = float(config.get(unlock_time))
            for i in range(int(r if r >= 1 else 1)):  # 测试:默认不为0
                if not use_passwd and float(day_config.get(day_time)) >= float(config.get(day_limit)):  # 判断解锁时间是否超过
                    break  # 不使用密码超过则直接退出循环
                time.sleep(60 if r >= 1 else 4)  # 测试:默认不为0
                day_config[day_time] = float(day_config.get(day_time)) + 1
                python_box.write_config(day_config, config_log_ini)
                if send_state:
                    entity_lock.send_sensor_state(day_config[day_time])
                python_box.write_config(day_config, config_log_ini)
    except Exception as e:
        for i in range(50):
            lock_screen(duration=30, passwd=config.get(passwd))
