import sys
import types
from unittest.mock import MagicMock, patch


def _install_dependency_stubs():
    """允许在未安装打包依赖的开发环境中测试纯状态逻辑。"""
    try:
        __import__("keyboard")
    except ModuleNotFoundError:
        keyboard = types.ModuleType("keyboard")
        keyboard.hook_key = MagicMock()
        keyboard.unhook_all = MagicMock()
        sys.modules["keyboard"] = keyboard

    try:
        __import__("paho.mqtt.client")
    except ModuleNotFoundError:
        paho = types.ModuleType("paho")
        paho_mqtt = types.ModuleType("paho.mqtt")
        paho_client = types.ModuleType("paho.mqtt.client")
        paho_client.Client = object
        paho.mqtt = paho_mqtt
        paho_mqtt.client = paho_client
        sys.modules["paho"] = paho
        sys.modules["paho.mqtt"] = paho_mqtt
        sys.modules["paho.mqtt.client"] = paho_client

    homeassistant = types.ModuleType("tools.server_box.mqtt.homeassistant_mq_entity")
    homeassistant.HomeAssistantEntity = MagicMock
    mqtt_utils = types.ModuleType("tools.server_box.mqtt.mqtt_utils")
    mqtt_utils.MqttBase = MagicMock
    sys.modules["tools.server_box.mqtt.homeassistant_mq_entity"] = homeassistant
    sys.modules["tools.server_box.mqtt.mqtt_utils"] = mqtt_utils


_install_dependency_stubs()
import lock_relax


def test_password_unlock_relocks_after_ten_minutes():
    assert lock_relax.should_relock_after_password(
        password_unlocked_at=100,
        relock_delay_minutes=10,
        relock_idle_seconds=60,
        now=700,
        idle_seconds=0,
    )


def test_password_unlock_relocks_after_idle_threshold():
    assert lock_relax.should_relock_after_password(
        password_unlocked_at=100,
        relock_delay_minutes=10,
        relock_idle_seconds=60,
        now=101,
        idle_seconds=60,
    )


def test_password_unlock_stays_open_before_either_threshold():
    assert not lock_relax.should_relock_after_password(
        password_unlocked_at=100,
        relock_delay_minutes=10,
        relock_idle_seconds=60,
        now=699,
        idle_seconds=59,
    )


def test_no_password_unlock_has_no_early_relock():
    assert not lock_relax.should_relock_after_password(
        password_unlocked_at=None,
        relock_delay_minutes=10,
        relock_idle_seconds=60,
        now=1000,
        idle_seconds=1000,
    )


def test_wait_without_password_uses_normal_sleep():
    with patch("lock_relax.time.sleep") as sleep:
        assert not lock_relax.wait_for_password_relock(60, None)
    sleep.assert_called_once_with(60.0)


def test_lock_retry_cycle_reenters_warning_after_password_unlock():
    events = []
    lock_results = iter([True, False])

    def warning_fn(**kwargs):
        events.append(("warning", kwargs))

    def lock_fn(**kwargs):
        events.append(("lock", kwargs))
        return next(lock_results)

    def wait_fn(*args, **kwargs):
        events.append(("wait", kwargs))
        return True

    bypass_count = lock_relax.run_lock_retry_cycle(
        lock_duration=1,
        passwd=123,
        warning_duration=60,
        warning_expanded_duration=3,
        relock_delay_minutes=10,
        relock_idle_seconds=60,
        warning_fn=warning_fn,
        lock_fn=lock_fn,
        wait_fn=wait_fn,
        clock=lambda: 100,
    )

    assert bypass_count == 1
    assert [event[0] for event in events] == [
        "warning", "lock", "wait", "warning", "lock"
    ]


def test_lock_retry_cycle_returns_without_wait_after_completed_rest():
    wait_fn = MagicMock()
    bypass_count = lock_relax.run_lock_retry_cycle(
        lock_duration=1,
        passwd=123,
        warning_fn=MagicMock(),
        lock_fn=MagicMock(return_value=False),
        wait_fn=wait_fn,
    )

    assert bypass_count == 0
    wait_fn.assert_not_called()
