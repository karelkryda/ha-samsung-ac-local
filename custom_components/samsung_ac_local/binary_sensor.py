"""
Binary sensor platform for the Samsung AC Local integration.

Exposes boolean states: cloud connection, outdoor unit, auto-clean activity,
freeze wash activity, AI sleep, and mute once.
"""

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SamsungACCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import ACStatus
    from .data import SamsungACConfigEntry, SamsungACData

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="cloud_connected",
        translation_key="cloud_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="auto_clean_active",
        translation_key="auto_clean_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="freeze_wash_active",
        translation_key="freeze_wash_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="outdoor_connected",
        translation_key="outdoor_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="ai_sleep_active",
        translation_key="ai_sleep_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="mute_once",
        translation_key="mute_once",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:volume-mute",
    ),
)


async def async_setup_entry(
    _hass: object,
    entry: SamsungACConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung AC binary sensor entities."""
    data: SamsungACData = entry.runtime_data
    device_id = data.device_info.mac_wifi or data.client.host
    async_add_entities(
        SamsungACBinarySensor(data.coordinator, description, device_id)
        for description in BINARY_SENSORS
    )


class SamsungACBinarySensor(
    CoordinatorEntity[SamsungACCoordinator], BinarySensorEntity
):
    """Binary sensor entity for Samsung AC Local."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungACCoordinator,
        description: BinarySensorEntityDescription,
        device_id: str,
    ) -> None:
        """
        Initialize the binary sensor.

        Args:
            coordinator: The data update coordinator.
            description: Entity description defining the sensor type.
            device_id: Device identifier (MAC or host).

        """
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_id)}}

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        status: ACStatus | None = self.coordinator.data
        if status is None:
            return None

        return getattr(status, self.entity_description.key, None)
