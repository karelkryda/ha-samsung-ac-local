"""
Switch platform for the Samsung AC Local integration.

Exposes toggleable features: display light, beep, air purify, auto-clean.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, AirPurifyMode, AutoCleanSetting, BeepVolume, LightMode
from .coordinator import SamsungACCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import ACStatus, SamsungACClient
    from .data import SamsungACConfigEntry, SamsungACData


@dataclass(frozen=True, kw_only=True)
class SamsungACSwitchDescription(SwitchEntityDescription):
    """Extended switch description with Samsung-specific methods."""

    status_attr: str
    on_value: Any
    off_value: Any


SWITCHES: tuple[SamsungACSwitchDescription, ...] = (
    SamsungACSwitchDescription(
        key="light",
        translation_key="display_light",
        status_attr="light",
        on_value=LightMode.ON,
        off_value=LightMode.OFF,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:lightbulb",
    ),
    SamsungACSwitchDescription(
        key="beep",
        translation_key="beep",
        status_attr="beep",
        on_value=BeepVolume.ON,
        off_value=BeepVolume.OFF,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:volume-high",
    ),
    SamsungACSwitchDescription(
        key="air_purify",
        translation_key="air_purify",
        status_attr="air_purify",
        on_value=AirPurifyMode.ON,
        off_value=AirPurifyMode.OFF,
        icon="mdi:air-purifier",
    ),
    SamsungACSwitchDescription(
        key="auto_clean",
        translation_key="auto_clean",
        status_attr="auto_clean_setting",
        on_value=AutoCleanSetting.ON,
        off_value=AutoCleanSetting.OFF,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:vacuum",
    ),
)

# Map switch key to the client method name
_SET_METHODS: dict[str, str] = {
    "light": "set_light",
    "beep": "set_beep",
    "air_purify": "set_air_purify",
    "auto_clean": "set_auto_clean",
}


async def async_setup_entry(
    _hass: object,
    entry: SamsungACConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung AC switch entities."""
    data: SamsungACData = entry.runtime_data
    device_id = data.device_info.mac_wifi or data.client.host
    async_add_entities(
        SamsungACSwitch(data.coordinator, data.client, description, device_id)
        for description in SWITCHES
    )


class SamsungACSwitch(CoordinatorEntity[SamsungACCoordinator], SwitchEntity):
    """Switch entity for Samsung AC Local."""

    _attr_has_entity_name = True
    entity_description: SamsungACSwitchDescription

    def __init__(
        self,
        coordinator: SamsungACCoordinator,
        client: SamsungACClient,
        description: SamsungACSwitchDescription,
        device_id: str,
    ) -> None:
        """
        Initialize the switch.

        Args:
            coordinator: The data update coordinator.
            client: The Samsung AC client for sending commands.
            description: Entity description defining the switch type.
            device_id: Device identifier (MAC or host).

        """
        super().__init__(coordinator)
        self._client = client
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        status: ACStatus | None = self.coordinator.data
        if status is None:
            return None

        value = getattr(status, self.entity_description.status_attr, None)
        if value is None:
            return None

        return value == self.entity_description.on_value

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._async_set(self.entity_description.on_value)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._async_set(self.entity_description.off_value)

    async def _async_set(self, value: Any) -> None:
        """Send command and update optimistically on success."""
        desc = self.entity_description
        method = getattr(self._client, _SET_METHODS[desc.key])
        if await self.hass.async_add_executor_job(method, value):
            self.coordinator.async_update_optimistic(**{desc.status_attr: value})
