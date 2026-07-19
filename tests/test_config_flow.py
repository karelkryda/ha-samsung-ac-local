"""Tests for the Samsung AC Local config flow."""

from unittest.mock import MagicMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsung_ac_local.api import SamsungACConnectionError
from custom_components.samsung_ac_local.const import DOMAIN

CONF_HOST = "host"
CONF_POLL_INTERVAL = "poll_interval"


async def test_full_flow(
    hass: HomeAssistant,
    mock_samsung_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test happy path: form, IP entered, connection OK, entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Samsung AC (192.168.1.100)"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "192.168.1.100"

    mock_samsung_client.connect.assert_called_once()
    mock_samsung_client.disconnect.assert_called_once()
    mock_setup_entry.assert_called_once()


async def test_flow_cannot_connect(
    hass: HomeAssistant,
    mock_samsung_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test connection failure shows error, user retries successfully."""
    mock_samsung_client.connect.side_effect = SamsungACConnectionError("timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # User retries with working connection.
    mock_samsung_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Samsung AC (192.168.1.100)"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    mock_setup_entry.assert_called_once()


async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_samsung_client: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test abort when the same host is already configured."""
    _ = mock_samsung_client  # patches the client class
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    mock_setup_entry.assert_not_called()


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the options flow to modify poll interval."""
    _ = mock_setup_entry  # needed for async_setup to succeed

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="192.168.1.100",
        options={CONF_POLL_INTERVAL: 30},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_POLL_INTERVAL: 60},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_POLL_INTERVAL: 60}
