# generate from base common code
from enum import Enum
from .mqtt_utils import MqttBase
import json
import logging
import platform
class HomeAssistantEntity:
    str_homeassistant = "homeassistant"
    str_topic_config = "config"
    str_topic_state = "state"
    str_topic_command = "command"
    str_topic_status = "status"

    class DiscoveryType(Enum):
        sensor = "sensor"
        light = "light"
        switch = "switch"
        button = "button"
        binary_sensor = "binary_sensor"
        input = "input"

    class LightSchema:
        state = None
        brightness = None

        def __init__(self, data=None):
            self.__dict__ = data

    def __init__(self, mqtt_base: MqttBase, special: str = None, device_name=None):
        self.special = special if special else ""
        self.domain = None
        self.topic_state = None
        self.topic_command = None
        self.platform_node = device_name  # entity device name
        self.mq = mqtt_base
        if special:
            self.status_topic = self.join_topic(self.str_homeassistant, self.unique_id(), special,
                                                self.str_topic_status)
        else:
            self.status_topic = self.join_topic(self.str_homeassistant, self.unique_id(), self.str_topic_status)

    def device(self, name=None):
        if name is None:
            name = self.unique_id()
        device = {"model": "TH-1", "manufacturer": "china",
                  "name": name,
                  "identifiers": [
                      name
                  ]}
        return device

    def send_online(self):
        self.mq.client.publish(self.status_topic, "online")

    def _check_set_domain(self, domain: DiscoveryType = None, config=False):
        if not domain:
            raise Exception("there is domain exists")
        if config and self.domain:
            raise Exception("config duplication")
        if not config and self.domain != domain:
            raise Exception("send state domain error")
        if config and not self.domain:
            self.domain = domain

    def send_sensor_config_topic(self, _id, name, unit=None, expire_after: int or float = 70, keep=False):
        self._check_set_domain(self.DiscoveryType.sensor, True)
        topic = self.join_topic(self.str_homeassistant, self.DiscoveryType.sensor.value,
                                self.unique_id() + "_" + _id + self.special, self.str_topic_config)
        self.topic_state = self.join_topic(self.str_homeassistant, self.DiscoveryType.sensor.value,
                                           self.unique_id() + "_" + _id + self.special, self.str_topic_state)
        _config = {
            "name": name,
            "object_id": self.unique_id() + "_" + _id + self.special,
            "unique_id": self.unique_id() + "_" + _id + self.special,
            "device": self.device(name=None),
            "unit_of_measurement": unit if unit else "",
            "state_topic": self.topic_state,
            "value_template": "{{ value[0:255] }}",
        }
        if not keep:
            _config["availability_topic"] = self.status_topic
        if expire_after:
            _config["expire_after"] = expire_after
        self.mq.client.publish(topic, json.dumps(_config), retain=True)
        self.send_online()

    def send_button_config_topic(self, _id, name, consumer_fun=None):
        self._check_set_domain(self.DiscoveryType.button, True)

        def pressed(**kwargs):
            payload = kwargs.get("payload")
            if payload and payload == "PRESS":
                consumer_fun()

        topic = self.join_topic(self.str_homeassistant, self.DiscoveryType.button.value,
                                self.unique_id() + "_" + _id + self.special, self.str_topic_config)
        self.topic_command = self.join_topic(self.str_homeassistant, self.DiscoveryType.button.value,
                                             self.unique_id() + "_" + _id + self.special, self.str_topic_command)
        _config = {
            "name": name,
            "object_id": self.unique_id() + "_" + _id + self.special,
            "unique_id": self.unique_id() + "_" + _id + self.special,
            "device": self.device(name=None),
            "command_topic": self.topic_command,
            "availability_topic": self.status_topic,
        }
        self.mq.client.publish(topic, json.dumps(_config), retain=True)
        self.mq.subscribe_topic(self.topic_command, consumer_fun=pressed)
        self.send_online()

    def send_light_config_topic(self, _id, name, consumer_fun=None):
        self._check_set_domain(self.DiscoveryType.light, True)

        def receive(**kwargs):
            payload = kwargs.get("payload")
            try:
                lightSchema = json.loads(payload, object_hook=self.LightSchema)
                consumer_fun(lightSchema)
                self.mq.client.publish(self.topic_state, payload)
            except Exception as e:
                logging.error(f"light error: {e}, pyload {payload}")

        topic = self.join_topic(self.str_homeassistant, self.DiscoveryType.light.value,
                                self.unique_id() + "_" + _id + self.special, self.str_topic_config)
        self.topic_state = self.join_topic(self.str_homeassistant, self.DiscoveryType.light.value,
                                           self.unique_id() + "_" + _id + self.special, self.str_topic_state)
        self.topic_command = self.join_topic(self.str_homeassistant, self.DiscoveryType.light.value,
                                             self.unique_id() + "_" + _id + self.special, self.str_topic_command)
        _config = {
            "name": name,
            "object_id": self.unique_id() + "_" + _id + self.special,
            "unique_id": self.unique_id() + "_" + _id + self.special,
            "device": self.device(),
            "schema": "json",
            "brightness": True,
            "availability_topic": self.status_topic,
            "state_topic": self.topic_state,
            "command_topic": self.topic_command,
        }
        self.mq.client.publish(topic, json.dumps(_config), retain=True)
        self.mq.subscribe_topic(self.topic_command, consumer_fun=receive)
        self.send_online()

    def send_switch_config_topic(self, _id, name, consumer_fun=None):
        self._check_set_domain(self.DiscoveryType.switch, True)

        def receive(**kwargs):
            payload = kwargs.get("payload")
            try:
                if payload == "ON":
                    consumer_fun(True) if consumer_fun else None
                elif payload == "OFF":
                    consumer_fun(False) if consumer_fun else None
                else:
                    consumer_fun(payload) if consumer_fun else None
            except Exception as e:
                logging.error(f"switch error: {e}, payload {payload}")

        topic = self.join_topic(self.str_homeassistant, self.DiscoveryType.switch.value,
                                self.unique_id() + "_" + _id + self.special, self.str_topic_config)
        self.topic_state = self.join_topic(self.str_homeassistant, self.DiscoveryType.switch.value,
                                           self.unique_id() + "_" + _id + self.special, self.str_topic_state)
        self.topic_command = self.join_topic(self.str_homeassistant, self.DiscoveryType.switch.value,
                                             self.unique_id() + "_" + _id + self.special, self.str_topic_command)
        _config = {
            "name": name,
            "object_id": self.unique_id() + "_" + _id + self.special,
            "unique_id": self.unique_id() + "_" + _id + self.special,
            "device": self.device(),
            "availability_topic": self.status_topic,
            "state_topic": self.topic_state,
            "command_topic": self.topic_command,
        }
        self.mq.client.publish(topic, json.dumps(_config), retain=True)
        self.mq.subscribe_topic(self.topic_command, consumer_fun=receive)
        self.send_online()

    def send_input_config_topic(self, _id, name, consumer_fun=None):
        """
        send input element config
        homeassistant not support this domain
        :param _id:
        :param name:
        :param consumer_fun:
        :return:
        """
        self._check_set_domain(self.DiscoveryType.input, True)

        def receive(**kwargs):
            payload = kwargs.get("payload")
            try:
                consumer_fun(payload=payload) if consumer_fun else None
            except Exception as e:
                logging.error(f"input error: {e}, payload {payload}")

        topic = self.join_topic(self.str_homeassistant, self.DiscoveryType.input.value,
                                self.unique_id() + "_" + _id + self.special, self.str_topic_config)
        self.topic_state = self.join_topic(self.str_homeassistant, self.DiscoveryType.input.value,
                                           self.unique_id() + "_" + _id + self.special, self.str_topic_state)
        self.topic_command = self.join_topic(self.str_homeassistant, self.DiscoveryType.input.value,
                                             self.unique_id() + "_" + _id + self.special, self.str_topic_command)
        _config = {
            "name": name,
            "object_id": self.unique_id() + "_" + _id + self.special,
            "unique_id": self.unique_id() + "_" + _id + self.special,
            "device": self.device(),
            "availability_topic": self.status_topic,
            "state_topic": self.topic_state,
            "command_topic": self.topic_command,
        }
        self.mq.client.publish(topic, json.dumps(_config), retain=True)
        self.mq.subscribe_topic(self.topic_command, consumer_fun=receive)
        self.send_online()

    def send_sensor_state(self, payload):
        self._check_set_domain(self.DiscoveryType.sensor, False)
        self.send_online()
        if self.topic_state:
            self.mq.client.publish(self.topic_state, payload)
        else:
            logging.error("have no topic_state")

    def send_light_state(self, brightness: int):
        self._check_set_domain(self.DiscoveryType.light, False)
        self.send_online()
        state = {"brightness": brightness, "state": "ON" if brightness > 0 else "OFF"}
        self.mq.client.publish(self.topic_state, json.dumps(state, ensure_ascii=False))

    def send_switch_state(self, is_on: bool):
        self._check_set_domain(self.DiscoveryType.switch, False)
        self.send_online()
        self.mq.client.publish(self.topic_state, "ON" if is_on else "OFF")

    def send_input_state(self, payload: str):
        self._check_set_domain(self.DiscoveryType.input, False)
        self.send_online()
        self.mq.client.publish(self.topic_state, payload)

    def unique_id(self):
        if self.platform_node:
            return self.platform_node
        else:
            self.platform_node = platform.node()
            return self.platform_node

    @staticmethod
    def to_json(dictionary: dict):
        return json.dumps(dictionary)

    @staticmethod
    def join_topic(*args):
        return "/".join(args)