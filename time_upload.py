# 强制锁频休息
import sys
import time

import paho.mqtt.client as mqtt

from common import python_box
from tools.server_box.mqtt.homeassistant_mq_entity import HomeAssistantEntity
from tools.server_box.mqtt.mqtt_utils import MqttBase


class UpTimer:
    @staticmethod
    def get_today():
        return python_box.date_format(fmt="%Y%m%d")

    def will_set(self, client: mqtt.Client):
        tmp = HomeAssistantEntity(None, "upload")
        client.will_set(tmp.status_topic, "offline")

    @staticmethod
    def log_msg(msg):
        python_box.log(msg, file="config/log_up_time_console.log")

    def run(self):
        # 初始化
        if not config:
            self.log_msg("请配置并重新运行")
            sys.exit(0)
        send_state = config.get(message) == 1
        self.log_msg(f"config: {config}")
        if send_state:
            try:
                base = MqttBase(config.get(host), config.get(port), None, self.will_set)
                entity_up_time = HomeAssistantEntity(base, "upload")
                entity_up_time.send_sensor_config_topic("up_time", "开机时间", "分钟", keep=True, expire_after=None)
                entity_online = HomeAssistantEntity(base, "upload")
                entity_online.send_switch_config_topic("up_state", "开机在线")
            except Exception as e:
                self.log_msg(e)
                send_state = False
        if day_time not in day_config:
            day_config[day_time] = 0
            python_box.write_config(day_config, config_log_ini)
        while True:
            if send_state:
                entity_up_time.send_sensor_state(day_config[day_time])
                entity_online.send_switch_state(True)
            time.sleep(60)
            day_config[day_time] = float(day_config.get(day_time)) + 1
            python_box.write_config(day_config, config_log_ini)


if __name__ == '__main__':
    config_log_ini = "config/log_up_time.ini"
    conf_file = "config/config_up_time.ini"
    loop = "loop"
    lock_time = "lock_time"
    unlock_time = "unlock_time"
    today = "today"
    day_limit = "day_limit"
    passwd = "passwd"
    host = "mq host"
    port = "mq port"
    message = "send message"
    day_time = "day_time" + UpTimer.get_today()
    day_config = python_box.read_config("%s" % config_log_ini, {("%s" % day_time): 0})
    config = python_box.read_config("%s" % conf_file,
                                    {("%s" % host): "localhost",
                                     ("%s" % port): "1883",
                                     ("%s" % message): "0#是否发送消息1 0"}, )
    try:
        UpTimer().run()
    except Exception as e:
        UpTimer.log_msg(e)
