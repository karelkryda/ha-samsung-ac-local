"""
Config flow for the Samsung AC Local integration.

Handles initial setup (host + certificate paths) and options flow
(poll interval) for post-setup configuration changes.
"""

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .api import SamsungACClient, SamsungACConnectionError
from .const import DOMAIN, LOGGER
from .coordinator import DEFAULT_POLL_INTERVAL

CONF_HOST = "host"
CONF_CERT_PATH = "cert_path"
CONF_KEY_PATH = "key_path"
CONF_POLL_INTERVAL = "poll_interval"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_CERT_PATH, default="/config/samsung_ac/client_cert.pem"): str,
        vol.Required(CONF_KEY_PATH, default="/config/samsung_ac/client_key.pem"): str,
    }
)


class SamsungACLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Samsung AC Local."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return SamsungACOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """
        Handle the user setup step.

        Asks for AC host IP and paths to certificate/key files,
        then validates the connection with a DTLS handshake.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self.hass.async_add_executor_job(
                self._validate_input, user_input
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Samsung AC ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    def _validate_input(self, user_input: dict[str, Any]) -> str | None:
        """
        Validate the user input by attempting a DTLS connection.

        This is a blocking method called via async_add_executor_job.
        Returns an error key on failure, None on success.
        """
        cert_path = Path(user_input[CONF_CERT_PATH])
        if not cert_path.is_file():
            return "cert_not_found"

        key_path = Path(user_input[CONF_KEY_PATH])
        if not key_path.is_file():
            return "key_not_found"

        try:
            cert_pem = cert_path.read_text()
            key_pem = key_path.read_text()
        except OSError:
            LOGGER.exception("Failed to read certificate files")
            return "cert_read_error"

        client = SamsungACClient(user_input[CONF_HOST], cert_pem, key_pem)
        try:
            client.connect()
        except SamsungACConnectionError:
            return "cannot_connect"
        finally:
            client.disconnect()

        return None


class SamsungACOptionsFlow(OptionsFlow):
    """Options flow for Samsung AC Local (poll interval)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """
        Initialize the options flow.

        Args:
            config_entry: The config entry to modify options for.

        """
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POLL_INTERVAL, default=current_interval): vol.All(
                        int, vol.Range(min=5, max=300)
                    ),
                }
            ),
        )
