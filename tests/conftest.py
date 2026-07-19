"""
Shared pytest fixtures for the Samsung AC Local integration tests.

Uses ``pytest-homeassistant-custom-component`` which provides the
``hass`` fixture, mock config-entry helpers and a full HA test bed.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from custom_components.samsung_ac_local.api import ACStatus, DeviceInfo, SamsungACClient
from custom_components.samsung_ac_local.const import (
    AutoCleanSetting,
    BeepVolume,
    ConvenientMode,
    FanMode,
    HvacMode,
    LightMode,
    Power,
    SwingMode,
)


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom_components in every test."""


@pytest.fixture
def mock_status() -> ACStatus:
    """Return a fully populated ACStatus for testing."""
    return ACStatus(
        power=Power.ON,
        hvac_mode=HvacMode.COOL,
        current_temperature=24.0,
        target_temperature=22.0,
        fan_mode=FanMode.AUTO,
        swing_mode=SwingMode.FIX,
        humidity=45,
        light=LightMode.ON,
        convenient_mode=ConvenientMode.OFF,
        beep=BeepVolume.ON,
        air_purify=None,
        auto_clean_setting=AutoCleanSetting.ON,
        auto_clean_active=False,
        auto_clean_progress=0,
        filter_usage_hours=120,
        filter_capacity_hours=2000,
        filter_status="Normal",
        energy_wh=15000,
        supported_modes=[
            HvacMode.AUTO,
            HvacMode.COOL,
            HvacMode.DRY,
            HvacMode.FAN,
            HvacMode.HEAT,
        ],
        supported_swing=[SwingMode.FIX, SwingMode.VERTICAL, SwingMode.ALL],
        supported_convenient=[
            ConvenientMode.OFF,
            ConvenientMode.SLEEP,
            ConvenientMode.WINDFREE,
        ],
        outdoor_temperature=35.0,
        outdoor_connected=True,
        duration_on_minutes=90,
        sleep_timer_minutes=0,
        ai_temperature=23.5,
        operation_count=450,
        temperature_min=16.0,
        temperature_max=30.0,
        temperature_step=1.0,
        rssi=-55,
        alarms=[],
        ai_sleep_active=False,
        ai_sleep_elapsed_minutes=0,
        mute_once=False,
        cloud_connected=True,
    )


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return a DeviceInfo for testing."""
    return DeviceInfo(
        firmware_version="ARA-KR-TP1-25-ARXX00_11260120",
        firmware_update_available=False,
        model_id="AR70F09C1AWNEU",
        os_version="4.0.1",
        one_ui_version=None,
        mac_wifi="AA:BB:CC:DD:EE:FF",
        mac_ble="AA:BB:CC:DD:EE:00",
        capabilities=["cooling", "heating", "windfree"],
    )


@pytest.fixture
def mock_client(mock_status: ACStatus, mock_device_info: DeviceInfo) -> MagicMock:
    """Return a mocked SamsungACClient with basic stubs."""
    client = MagicMock(spec=SamsungACClient)
    client.host = "192.168.1.100"
    client.connected = True
    client.connect.return_value = None
    client.disconnect.return_value = None
    client.get_status.return_value = mock_status
    client.get_device_info.return_value = mock_device_info
    client.set_power.return_value = True
    client.set_hvac_mode.return_value = True
    client.set_target_temperature.return_value = True
    client.set_fan_mode.return_value = True
    client.set_swing_mode.return_value = True
    client.set_convenient_mode.return_value = True
    client.set_beep.return_value = True
    client.set_light.return_value = True
    client.set_auto_clean.return_value = True
    client.set_auto_clean_action.return_value = True
    client.set_air_purify.return_value = True
    return client


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Mock async_setup_entry to isolate config flow tests."""
    with patch(
        "custom_components.samsung_ac_local.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_samsung_client() -> Generator[MagicMock]:
    """Mock the SamsungACClient class for config flow tests."""
    with patch(
        "custom_components.samsung_ac_local.config_flow.SamsungACClient",
    ) as mock_cls:
        client_instance = MagicMock(spec=SamsungACClient)
        client_instance.connect.return_value = None
        client_instance.disconnect.return_value = None
        mock_cls.return_value = client_instance
        yield client_instance
