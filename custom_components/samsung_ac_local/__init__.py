"""
Samsung AC Local integration.

Controls Samsung OCF air conditioners locally via DTLS/CoAP,
bypassing the Samsung SmartThings cloud.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .api import SamsungACClient, SamsungACConnectionError
from .config_flow import CONF_CERT_PATH, CONF_HOST, CONF_KEY_PATH, CONF_POLL_INTERVAL
from .coordinator import DEFAULT_POLL_INTERVAL, SamsungACCoordinator
from .data import SamsungACConfigEntry, SamsungACData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: SamsungACConfigEntry) -> bool:
    """
    Set up Samsung AC Local from a config entry.

    Reads certificates, establishes the DTLS connection, fetches device info,
    and starts the polling coordinator.
    """
    cert_pem = await hass.async_add_executor_job(
        Path(entry.data[CONF_CERT_PATH]).read_text
    )
    key_pem = await hass.async_add_executor_job(
        Path(entry.data[CONF_KEY_PATH]).read_text
    )

    client = SamsungACClient(entry.data[CONF_HOST], cert_pem, key_pem)
    try:
        await hass.async_add_executor_job(client.connect)
    except SamsungACConnectionError as err:
        await hass.async_add_executor_job(client.disconnect)
        msg = f"Failed to connect to Samsung AC at {entry.data[CONF_HOST]}"
        raise ConfigEntryNotReady(msg) from err

    device_info = await hass.async_add_executor_job(client.get_device_info)
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator = SamsungACCoordinator(hass, client, poll_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SamsungACData(
        client=client,
        coordinator=coordinator,
        device_info=device_info,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SamsungACConfigEntry) -> bool:
    """Unload a config entry and disconnect from the AC."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.async_add_executor_job(entry.runtime_data.client.disconnect)

    return unloaded


async def _async_options_updated(
    hass: HomeAssistant, entry: SamsungACConfigEntry
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
