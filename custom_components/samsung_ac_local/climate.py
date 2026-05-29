"""
Climate platform for the Samsung AC Local integration.

Exposes the air conditioner as a ClimateEntity with HVAC modes,
fan speed, swing, preset (convenient) modes, and target temperature.
"""

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ConvenientMode,
    FanMode,
    Power,
    SwingMode,
)
from .const import (
    HvacMode as SamsungHvacMode,
)
from .coordinator import SamsungACCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import ACStatus
    from .data import SamsungACConfigEntry, SamsungACData

# Samsung HVAC mode -> HA HVACMode
_HVAC_MODE_MAP: dict[SamsungHvacMode, HVACMode] = {
    SamsungHvacMode.AUTO: HVACMode.AUTO,
    SamsungHvacMode.COOL: HVACMode.COOL,
    SamsungHvacMode.DRY: HVACMode.DRY,
    SamsungHvacMode.FAN: HVACMode.FAN_ONLY,
    SamsungHvacMode.HEAT: HVACMode.HEAT,
}
_HVAC_MODE_REVERSE: dict[HVACMode, SamsungHvacMode] = {
    v: k for k, v in _HVAC_MODE_MAP.items()
}

# Samsung fan mode -> HA fan mode string
_FAN_MODE_MAP: dict[FanMode, str] = {
    FanMode.AUTO: "auto",
    FanMode.LOW: "low",
    FanMode.MID: "medium",
    FanMode.HIGH: "high",
    FanMode.TURBO: "turbo",
}
_FAN_MODE_REVERSE: dict[str, FanMode] = {v: k for k, v in _FAN_MODE_MAP.items()}

# Samsung swing mode -> HA swing mode string
_SWING_MODE_MAP: dict[SwingMode, str] = {
    SwingMode.FIX: "off",
    SwingMode.VERTICAL: "vertical",
    SwingMode.HORIZONTAL: "horizontal",
    SwingMode.ALL: "both",
}
_SWING_MODE_REVERSE: dict[str, SwingMode] = {v: k for k, v in _SWING_MODE_MAP.items()}

# Samsung convenient mode -> HA preset string
_PRESET_MODE_MAP: dict[ConvenientMode, str] = {
    ConvenientMode.OFF: "none",
    ConvenientMode.SLEEP: "sleep",
    ConvenientMode.QUIET: "quiet",
    ConvenientMode.SMART: "smart",
    ConvenientMode.SPEED: "boost",
    ConvenientMode.WINDFREE: "windfree",
    ConvenientMode.WINDFREE_SLEEP: "windfree_sleep",
    ConvenientMode.DRY_COMFORT: "comfort",
}
_PRESET_MODE_REVERSE: dict[str, ConvenientMode] = {
    v: k for k, v in _PRESET_MODE_MAP.items()
}


async def async_setup_entry(
    _hass: Any,
    entry: SamsungACConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Samsung AC climate entity."""
    data: SamsungACData = entry.runtime_data
    async_add_entities([SamsungACClimateEntity(data.coordinator, data)])


class SamsungACClimateEntity(CoordinatorEntity[SamsungACCoordinator], ClimateEntity):
    """Climate entity for Samsung AC Local."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: SamsungACCoordinator, data: SamsungACData) -> None:
        """
        Initialize the climate entity.

        Args:
            coordinator: The data update coordinator.
            data: Runtime data with client and device info.

        """
        super().__init__(coordinator)
        self._client = data.client
        device_id = data.device_info.mac_wifi or data.client.host
        self._attr_unique_id = f"{device_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": "Samsung AC",
            "manufacturer": "Samsung",
            "model": data.device_info.model_id,
            "sw_version": data.device_info.firmware_version,
        }
        self._update_from_status(coordinator.data)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return available HVAC modes."""
        modes = [HVACMode.OFF]
        if self.coordinator.data:
            for samsung_mode in self.coordinator.data.supported_modes:
                ha_mode = _HVAC_MODE_MAP.get(samsung_mode)
                if ha_mode:
                    modes.append(ha_mode)

        return modes

    @property
    def fan_modes(self) -> list[str]:
        """Return available fan modes."""
        return list(_FAN_MODE_MAP.values())

    @property
    def swing_modes(self) -> list[str]:
        """Return available swing modes."""
        return list(_SWING_MODE_MAP.values())

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        modes = ["none"]
        if self.coordinator.data:
            for conv_mode in self.coordinator.data.supported_convenient:
                preset = _PRESET_MODE_MAP.get(conv_mode)
                if preset and preset != "none":
                    modes.append(preset)

        return modes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self._update_from_status(self.coordinator.data)

        self.async_write_ha_state()

    def _update_from_status(self, status: ACStatus | None) -> None:
        """Update internal attributes from AC status."""
        if not status:
            return

        # HVAC mode (OFF when power is off)
        if status.power == Power.OFF:
            self._attr_hvac_mode = HVACMode.OFF
        elif status.hvac_mode:
            self._attr_hvac_mode = _HVAC_MODE_MAP.get(status.hvac_mode)

        # Temperature
        self._attr_current_temperature = status.current_temperature
        self._attr_target_temperature = status.target_temperature
        self._attr_current_humidity = status.humidity

        if status.temperature_min is not None:
            self._attr_min_temp = status.temperature_min

        if status.temperature_max is not None:
            self._attr_max_temp = status.temperature_max

        if status.temperature_step is not None:
            self._attr_target_temperature_step = status.temperature_step

        # Fan
        if status.fan_mode:
            self._attr_fan_mode = _FAN_MODE_MAP.get(status.fan_mode)

        # Swing
        if status.swing_mode:
            self._attr_swing_mode = _SWING_MODE_MAP.get(status.swing_mode)

        # Preset
        if status.convenient_mode:
            self._attr_preset_mode = _PRESET_MODE_MAP.get(status.convenient_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.hass.async_add_executor_job(self._client.set_power, Power.OFF)
        else:
            # Turn on if currently off
            if self._attr_hvac_mode == HVACMode.OFF:
                await self.hass.async_add_executor_job(self._client.set_power, Power.ON)

            samsung_mode = _HVAC_MODE_REVERSE.get(hvac_mode)
            if samsung_mode:
                await self.hass.async_add_executor_job(
                    self._client.set_hvac_mode, samsung_mode
                )

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.hass.async_add_executor_job(
                self._client.set_target_temperature, float(temp)
            )
            await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        samsung_fan = _FAN_MODE_REVERSE.get(fan_mode)
        if samsung_fan:
            await self.hass.async_add_executor_job(
                self._client.set_fan_mode, samsung_fan
            )
            await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        samsung_swing = _SWING_MODE_REVERSE.get(swing_mode)
        if samsung_swing:
            await self.hass.async_add_executor_job(
                self._client.set_swing_mode, samsung_swing
            )
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset (convenient) mode."""
        samsung_preset = _PRESET_MODE_REVERSE.get(preset_mode)
        if samsung_preset:
            await self.hass.async_add_executor_job(
                self._client.set_convenient_mode, samsung_preset
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        await self.hass.async_add_executor_job(self._client.set_power, Power.ON)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        await self.hass.async_add_executor_job(self._client.set_power, Power.OFF)
        await self.coordinator.async_request_refresh()
