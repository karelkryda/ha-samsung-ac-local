"""
Button platform for the Samsung AC Local integration.

Exposes one-shot actions: start/stop auto-clean cycle.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, AutoCleanAction
from .coordinator import SamsungACCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import SamsungACClient
    from .data import SamsungACConfigEntry, SamsungACData


@dataclass(frozen=True, kw_only=True)
class SamsungACButtonDescription(ButtonEntityDescription):
    """Extended button description with Samsung-specific action."""

    method: str
    argument: Any


BUTTONS: tuple[SamsungACButtonDescription, ...] = (
    SamsungACButtonDescription(
        key="start_auto_clean",
        translation_key="start_auto_clean",
        method="set_auto_clean_action",
        argument=AutoCleanAction.START,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:vacuum",
    ),
    SamsungACButtonDescription(
        key="stop_auto_clean",
        translation_key="stop_auto_clean",
        method="set_auto_clean_action",
        argument=AutoCleanAction.STOP,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:stop-circle-outline",
    ),
)


async def async_setup_entry(
    _hass: object,
    entry: SamsungACConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung AC button entities."""
    data: SamsungACData = entry.runtime_data
    device_id = data.device_info.mac_wifi or data.client.host
    async_add_entities(
        SamsungACButton(data.coordinator, data.client, description, device_id)
        for description in BUTTONS
    )


class SamsungACButton(CoordinatorEntity[SamsungACCoordinator], ButtonEntity):
    """Button entity for Samsung AC Local."""

    _attr_has_entity_name = True
    entity_description: SamsungACButtonDescription

    def __init__(
        self,
        coordinator: SamsungACCoordinator,
        client: SamsungACClient,
        description: SamsungACButtonDescription,
        device_id: str,
    ) -> None:
        """
        Initialize the button.

        Args:
            coordinator: The data update coordinator.
            client: The Samsung AC client for sending commands.
            description: Entity description defining the button type.
            device_id: Device identifier (MAC or host).

        """
        super().__init__(coordinator)
        self._client = client
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    async def async_press(self) -> None:
        """Execute the button action."""
        desc = self.entity_description
        method = getattr(self._client, desc.method)
        await self.hass.async_add_executor_job(method, desc.argument)
