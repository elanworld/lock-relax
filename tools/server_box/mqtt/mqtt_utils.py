# generate from base common code
import paho.mqtt.client as mqtt
import time
import logging
from common import python_box
import re
class MqttBase:
    def __init__(self, host, port, client_id=None, before_connect_func=None, username=None, password=None,
                 connect_now=True):
        """
        MqttBase
        :param host:
        :param port:
        :param client_id:
        :param before_connect_func: func(client: mqtt.Client)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        if client_id:
            self.client_id = client_id
        else:
            self.client_id = python_box.random_str()
        self.timeout = 10
        self.subscribe_topics = []
        self.subscribe_topics_fun = {}
        self.client = None  # type: mqtt.Client
        self.is_debug = False
        self.before_connect_func = before_connect_func
        if connect_now:
            self.connect()

    def connect(self):
        client = mqtt.Client(self.client_id)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_subscribe = self.on_subscribe
        client.on_disconnect = self.on_disconnect
        if self.before_connect_func:
            self.before_connect_func(client)
        if self.username or self.password:
            client.username_pw_set(self.username, self.password)
        client.connect(self.host, self.port)
        self.client = client
        client.loop_start()
        time_time = time.time()
        while not client.is_connected() and (time.time() - time_time) < self.timeout:
            time.sleep(0.1)

    def close(self):
        if self.client:
            self.client.loop_stop()
            self.client = None

    def subscribe_topic(self, topic, consumer_fun=None):
        self.subscribe_topics.append(topic)
        self.subscribe_topics_fun[topic] = consumer_fun
        if self.client:
            self.client.subscribe(topic)
        else:
            logging.warning("client not inited")

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        logging.info(" Connected with result code " + str(rc))
        for topic in self.subscribe_topics:
            client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")

            if self.is_debug:
                logging.debug(f"Received on topic {msg.topic}: {payload}")

            # 遍历所有订阅主题，看是否匹配当前主题
            for topic_pattern, callback in self.subscribe_topics_fun.items():
                # 使用正则表达式匹配通配符
                pattern = topic_pattern.replace("+", "[^/]+").replace("#", ".*")
                if re.fullmatch(pattern, msg.topic):
                    python_box.thread_runner(callback, payload=payload, topic=msg.topic)
        except Exception as e:
            logging.error(f"message error: {e}")

    def on_subscribe(self, client, userdata, mid, granted_qos):
        logging.info(" On Subscribed: qos = %d" % granted_qos)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logging.info(" Unexpected disconnection %s" % rc)

    def __str__(self):
        return f"""{self.__class__} host:{self.host}"""