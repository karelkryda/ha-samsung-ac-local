"""
Tests for Samsung AC Local entity
platforms (climate, sensor, switch, binary_sensor).
"""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    HVACMode,
)
from homeassistant.components.climate.const import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsung_ac_local.const import (
    DOMAIN,
    AirPurifyMode,
    AutoCleanAction,
    AutoCleanSetting,
    BeepVolume,
    ConvenientMode,
    FanMode,
    HvacMode,
    LightMode,
    Power,
    SwingMode,
)

DEVICE_ID = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Samsung AC Local integration with a mocked client."""
    with patch(
        "custom_components.samsung_ac_local.SamsungACClient",
    ) as mock_cls:
        mock_cls.return_value = mock_client
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "192.168.1.100"},
            version=2,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _get_entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Look up entity_id from the entity registry by platform and unique_id."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
    if entity_id is None:
        msg = f"Entity with unique_id '{unique_id}' not found in platform '{platform}'"
        raise ValueError(msg)
    return entity_id


class TestClimateState:
    """Tests for the climate entity state representation."""

    async def test_hvac_mode_cool(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports 'cool' HVAC mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == HVACMode.COOL

    async def test_target_temperature(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports correct target temperature."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["temperature"] == 22.0

    async def test_current_temperature(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports correct current temperature."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["current_temperature"] == 24.0

    async def test_fan_mode(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports correct fan mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["fan_mode"] == "auto"

    async def test_swing_mode(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports correct swing mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["swing_mode"] == "off"

    async def test_preset_mode(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports 'none' preset when no convenient mode active."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["preset_mode"] == "none"

    async def test_humidity(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports current humidity."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["current_humidity"] == 45

    async def test_min_max_temp(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Climate entity reports min/max temperature bounds."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["min_temp"] == 16.0
        assert state.attributes["max_temp"] == 30.0


class TestClimateCommands:
    """Tests for climate entity service calls."""

    async def test_turn_off(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning off calls set_power with Power.OFF."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_power.assert_called_with(Power.OFF)

    async def test_turn_on(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning on calls set_power with Power.ON."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_power.assert_called_with(Power.ON)

    async def test_set_temperature(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Setting temperature calls set_target_temperature."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_temperature",
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 25.0},
            blocking=True,
        )
        mock_client.set_target_temperature.assert_called_once_with(25.0)

    async def test_set_fan_mode(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Setting fan mode calls set_fan_mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_fan_mode",
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: "high"},
            blocking=True,
        )
        mock_client.set_fan_mode.assert_called_once_with(FanMode.HIGH)

    async def test_set_swing_mode(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Setting swing mode calls set_swing_mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_swing_mode",
            {ATTR_ENTITY_ID: entity_id, ATTR_SWING_MODE: "vertical"},
            blocking=True,
        )
        mock_client.set_swing_mode.assert_called_once_with(SwingMode.VERTICAL)

    async def test_set_preset_mode(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Setting preset mode calls set_convenient_mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_preset_mode",
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "sleep"},
            blocking=True,
        )
        mock_client.set_convenient_mode.assert_called_once_with(ConvenientMode.SLEEP)

    async def test_set_hvac_mode_off(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Setting HVAC mode to OFF calls set_power with Power.OFF."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
        mock_client.set_power.assert_called_with(Power.OFF)

    async def test_set_hvac_mode_heat(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Setting HVAC mode to heat calls set_hvac_mode."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "climate", f"{DEVICE_ID}_climate")
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
        mock_client.set_hvac_mode.assert_called_once_with(HvacMode.HEAT)


class TestSensorsState:
    """Tests for sensor entity state values."""

    async def test_outdoor_temperature(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Outdoor temperature sensor reports correct value."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_outdoor_temperature")
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 35.0

    async def test_energy(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Energy sensor reports cumulative consumption in Wh."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_energy_wh")
        state = hass.states.get(entity_id)
        assert state is not None
        assert int(state.state) == 15000

    async def test_filter_usage(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Filter usage sensor reports hours of operation."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_filter_usage_hours")
        state = hass.states.get(entity_id)
        assert state is not None
        assert int(state.state) == 120

    async def test_rssi(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """RSSI sensor reports WiFi signal strength."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_rssi")
        state = hass.states.get(entity_id)
        assert state is not None
        assert int(state.state) == -55

    async def test_duration_on(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Duration on sensor reports minutes."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_duration_on_minutes")
        state = hass.states.get(entity_id)
        assert state is not None
        assert int(state.state) == 90

    async def test_operation_count(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Operation count sensor reports total operations."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_operation_count")
        state = hass.states.get(entity_id)
        assert state is not None
        assert int(state.state) == 450

    async def test_ai_temperature(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """AI temperature sensor reports the computed value."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "sensor", f"{DEVICE_ID}_ai_temperature")
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 23.5


class TestSwitchesState:
    """Tests for switch entity state values."""

    async def test_light_switch_on(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Light switch reports ON when display light is on."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_light")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

    async def test_beep_switch_on(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Beep switch reports ON when volume is not muted."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_beep")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

    async def test_auto_clean_switch_on(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Auto-clean switch reports ON when setting is enabled."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_auto_clean")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

    async def test_air_purify_switch_unknown(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Air purify switch reports unknown when value is None."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_air_purify")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "unknown"


class TestSwitchCommands:
    """Tests for switch entity service calls."""

    async def test_light_turn_on(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning on light switch calls set_light with LightMode.ON."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_light")
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_light.assert_called_with(LightMode.ON)

    async def test_light_turn_off(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning off light switch calls set_light with LightMode.OFF."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_light")
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_light.assert_called_with(LightMode.OFF)

    async def test_beep_turn_off(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning off beep calls set_beep with BeepVolume.OFF."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_beep")
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_beep.assert_called_with(BeepVolume.OFF)

    async def test_auto_clean_turn_off(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning off auto-clean calls set_auto_clean with AutoCleanSetting.OFF."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_auto_clean")
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_auto_clean.assert_called_with(AutoCleanSetting.OFF)

    async def test_air_purify_turn_on(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Turning on air purify calls set_air_purify with AirPurifyMode.ON."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "switch", f"{DEVICE_ID}_air_purify")
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_air_purify.assert_called_with(AirPurifyMode.ON)


class TestBinarySensorsState:
    """Tests for binary sensor entity state values."""

    async def test_cloud_connected(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Cloud connected binary sensor reports ON."""
        _ = setup_integration
        entity_id = _get_entity_id(
            hass, "binary_sensor", f"{DEVICE_ID}_cloud_connected"
        )
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

    async def test_auto_clean_active(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Auto-clean active binary sensor reports OFF when not running."""
        _ = setup_integration
        entity_id = _get_entity_id(
            hass, "binary_sensor", f"{DEVICE_ID}_auto_clean_active"
        )
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    async def test_outdoor_connected(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Outdoor connected binary sensor reports ON."""
        _ = setup_integration
        entity_id = _get_entity_id(
            hass, "binary_sensor", f"{DEVICE_ID}_outdoor_connected"
        )
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_ON

    async def test_ai_sleep_active(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """AI sleep binary sensor reports OFF when not active."""
        _ = setup_integration
        entity_id = _get_entity_id(
            hass, "binary_sensor", f"{DEVICE_ID}_ai_sleep_active"
        )
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    async def test_mute_once(
        self,
        hass: HomeAssistant,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Mute once binary sensor reports OFF when not set."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "binary_sensor", f"{DEVICE_ID}_mute_once")
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF


class TestButtonCommands:
    """Tests for button entity press actions."""

    async def test_start_auto_clean(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Pressing start auto clean calls set_auto_clean_action with START."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "button", f"{DEVICE_ID}_start_auto_clean")
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_auto_clean_action.assert_called_with(AutoCleanAction.START)

    async def test_stop_auto_clean(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        setup_integration: MockConfigEntry,
    ) -> None:
        """Pressing stop auto clean calls set_auto_clean_action with STOP."""
        _ = setup_integration
        entity_id = _get_entity_id(hass, "button", f"{DEVICE_ID}_stop_auto_clean")
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_client.set_auto_clean_action.assert_called_with(AutoCleanAction.STOP)
