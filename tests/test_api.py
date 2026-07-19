"""
Comprehensive tests for the Samsung AC Local api.py module.

Tests cover CoAP message building/parsing, module-level helpers,
status polling, post validation, connection management, and token validation.
All tests are pure unit tests - no Home Assistant fixtures required.
"""

import struct
from unittest.mock import MagicMock, patch

import cbor2
import pytest

from custom_components.samsung_ac_local.api import (
    ACStatus,
    SamsungACClient,
    SamsungACConnectionError,
    SamsungACRequestError,
    _parse_beep,
    _parse_enum,
    _parse_enum_list,
    _parse_mode_options,
    _samsung_val,
    _to_float,
    _to_int,
)
from custom_components.samsung_ac_local.const import (
    COAP_FORMAT_CBOR,
    COAP_GET,
    COAP_PAYLOAD_MARKER,
    COAP_POST,
    SAMSUNG_PREFIX,
    AirPurifyMode,
    AutoCleanSetting,
    BeepVolume,
    ConvenientMode,
    FanMode,
    HvacMode,
    LightMode,
    Power,
    Resource,
    SwingMode,
)

FAKE_CERT = "-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----"
FAKE_KEY = "-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----"


@pytest.fixture
def client() -> SamsungACClient:
    """Return a SamsungACClient instance without connecting."""
    return SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)


class TestBuildMessage:
    """Tests for _build_message CoAP frame construction."""

    def test_get_simple_path(self, client: SamsungACClient) -> None:
        """GET request has correct header, token, and URI-Path options."""
        msg = client._build_message(COAP_GET, "power/vs/0")

        # Version 1, Type CON, TKL 1
        assert msg[0] == 0x41
        # Method GET
        assert msg[1] == COAP_GET
        # Message ID (2 bytes big-endian)
        mid = struct.unpack("!H", msg[2:4])[0]
        assert mid == 1  # First message
        # Token (1 byte, low byte of MID)
        assert msg[4] == mid & 0xFF

    def test_uri_path_segments_encoded(self, client: SamsungACClient) -> None:
        """Each path segment is encoded as a separate URI-Path option."""
        msg = client._build_message(COAP_GET, "power/vs/0")
        # After header (4 bytes) + token (1 byte) = offset 5
        # First option: delta=11, length=5 ("power")
        assert msg[5] == (11 << 4) | 5
        assert msg[6:11] == b"power"
        # Second option: delta=0, length=2 ("vs")
        assert msg[11] == (0 << 4) | 2
        assert msg[12:14] == b"vs"
        # Third option: delta=0, length=1 ("0")
        assert msg[14] == (0 << 4) | 1
        assert msg[15:16] == b"0"

    def test_post_with_payload(self, client: SamsungACClient) -> None:
        """POST request includes content-format option and CBOR payload."""
        payload = {"temperature": 22.0}
        msg = client._build_message(COAP_POST, "temperature/desired/0", payload)

        assert msg[1] == COAP_POST
        # Find payload marker
        marker_pos = msg.index(b"\xff")
        # Payload after marker is valid CBOR
        decoded = cbor2.loads(msg[marker_pos + 1 :])
        assert decoded == payload

    def test_content_format_option_before_payload(
        self, client: SamsungACClient
    ) -> None:
        """Content-Format option (12) with value CBOR precedes the payload marker."""
        payload = {"key": "value"}
        msg = client._build_message(COAP_POST, "power/vs/0", payload)

        # After the URI-Path options, content-format option should appear
        # The payload marker 0xFF must exist
        assert COAP_PAYLOAD_MARKER in msg
        marker_pos = msg.index(bytes([COAP_PAYLOAD_MARKER]))
        # The byte before content-format value should be COAP_FORMAT_CBOR (60)
        # Content-format option: delta from 11 to 12 = 1, length = 1
        # Encoded as (1 << 4) | 1 = 0x11, then value byte = 60
        fmt_header = bytes([(1 << 4) | 1, COAP_FORMAT_CBOR])
        assert fmt_header in msg[:marker_pos]

    def test_mid_increments(self, client: SamsungACClient) -> None:
        """Message ID increments with each call."""
        msg1 = client._build_message(COAP_GET, "power/vs/0")
        msg2 = client._build_message(COAP_GET, "power/vs/0")
        mid1 = struct.unpack("!H", msg1[2:4])[0]
        mid2 = struct.unpack("!H", msg2[2:4])[0]
        assert mid2 == mid1 + 1

    def test_mid_wraps_at_16bit(self, client: SamsungACClient) -> None:
        """Message ID wraps around at 0xFFFF."""
        client._mid = 0xFFFE
        msg = client._build_message(COAP_GET, "power/vs/0")
        mid = struct.unpack("!H", msg[2:4])[0]
        assert mid == 0xFFFF

        msg = client._build_message(COAP_GET, "power/vs/0")
        mid = struct.unpack("!H", msg[2:4])[0]
        assert mid == 0

    def test_long_segment_uses_extended_length(self, client: SamsungACClient) -> None:
        """Path segments >= 13 chars use extended length encoding."""
        long_segment = "a" * 20  # 20 chars > 13
        msg = client._build_message(COAP_GET, long_segment)
        # First option at offset 5: delta=11, length=13 (extended)
        # So first byte is (11 << 4) | 13 = 0xBD
        assert msg[5] == 0xBD
        # Extended length byte: 20 - 13 = 7
        assert msg[6] == 7
        # Then the segment itself
        assert msg[7:27] == long_segment.encode()

    def test_no_payload_no_marker(self, client: SamsungACClient) -> None:
        """GET request without payload has no 0xFF marker."""
        msg = client._build_message(COAP_GET, "power/vs/0")
        # Walk past the options - the message should not contain 0xFF as payload marker
        # (It might appear in option bytes, but not as the CoAP marker)
        # Verify by parsing: _find_payload_offset should return None
        assert SamsungACClient._find_payload_offset(msg) is None


class TestParseResponse:
    """Tests for _parse_response code extraction and CBOR decoding."""

    def _make_response(
        self, code_class: int, code_detail: int, payload: dict | None = None
    ) -> bytes:
        """Build a minimal CoAP response frame for testing."""
        code_byte = (code_class << 5) | code_detail
        # Ver=1, Type=ACK, TKL=1
        header = bytes([0x61, code_byte]) + struct.pack("!H", 1) + b"\x01"
        if payload is not None:
            cbor_data = cbor2.dumps(payload)
            # Add a dummy option (content-format) then payload marker
            header += bytes([(12 << 4) | 1, COAP_FORMAT_CBOR])
            header += b"\xff" + cbor_data
        return header

    def test_success_code_extraction(self, client: SamsungACClient) -> None:
        """Response code 2.05 is correctly extracted."""
        data = self._make_response(2, 5, {"key": "value"})
        code, payload = client._parse_response(data)
        assert code == "2.05"
        assert payload == {"key": "value"}

    def test_changed_code(self, client: SamsungACClient) -> None:
        """Response code 2.04 (Changed) is correctly extracted."""
        resp_payload = {"controlResponse": {"result": True}}
        data = self._make_response(2, 4, resp_payload)
        code, payload = client._parse_response(data)
        assert code == "2.04"
        assert payload == resp_payload

    def test_error_code(self, client: SamsungACClient) -> None:
        """Client error 4.04 (Not Found) is correctly extracted."""
        data = self._make_response(4, 4)
        code, payload = client._parse_response(data)
        assert code == "4.04"
        assert payload is None

    def test_no_payload(self, client: SamsungACClient) -> None:
        """Response without payload marker returns None payload."""
        # Just header + token, no options, no payload
        data = bytes([0x61, (2 << 5) | 5]) + struct.pack("!H", 1) + b"\x01"
        code, payload = client._parse_response(data)
        assert code == "2.05"
        assert payload is None

    def test_malformed_cbor_returns_none(self, client: SamsungACClient) -> None:
        """Malformed CBOR after payload marker returns None payload."""
        # Header + token + payload marker + truncated CBOR map (starts map but
        # never finishes - 0xBF is indefinite-length map, 0xFF alone is break)
        data = bytes([0x61, (2 << 5) | 5]) + struct.pack("!H", 1) + b"\x01"
        # 0xBF = start indefinite map, 0x61 = text(1), then cut off
        data += b"\xff\xbf\x61"
        code, payload = client._parse_response(data)
        assert code == "2.05"
        assert payload is None

    def test_non_dict_cbor_returns_value(self, client: SamsungACClient) -> None:
        """Non-dict CBOR payload (e.g. list) is returned but logged."""
        # The _parse_response returns whatever cbor2 decodes, even non-dict
        header = bytes([0x61, (2 << 5) | 5]) + struct.pack("!H", 1) + b"\x01"
        header += b"\xff" + cbor2.dumps([1, 2, 3])
        code, payload = client._parse_response(header)
        assert code == "2.05"
        # Non-dict payloads are still returned (the caller handles None guard)
        assert payload == [1, 2, 3]


class TestFindPayloadOffset:
    """Tests for _find_payload_offset option traversal."""

    def test_simple_options_then_payload(self) -> None:
        """Correctly finds payload after simple options."""
        # Header (4) + token (1) + option (delta=11, len=5, "power") + marker + payload
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xAA])
        option = bytes([(11 << 4) | 5]) + b"power"
        marker = b"\xff"
        payload = cbor2.dumps({"key": "val"})
        data = header + option + marker + payload

        offset = SamsungACClient._find_payload_offset(data)
        assert offset == len(header) + len(option) + 1
        assert cbor2.loads(data[offset:]) == {"key": "val"}

    def test_multiple_options(self) -> None:
        """Correctly walks past multiple options to find payload."""
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xBB])
        # First option: delta=11, len=2
        opt1 = bytes([(11 << 4) | 2]) + b"ab"
        # Second option: delta=0, len=3
        opt2 = bytes([(0 << 4) | 3]) + b"cde"
        marker = b"\xff"
        payload = cbor2.dumps({})
        data = header + opt1 + opt2 + marker + payload

        offset = SamsungACClient._find_payload_offset(data)
        assert offset == len(header) + len(opt1) + len(opt2) + 1

    def test_no_payload_marker(self) -> None:
        """Returns None when no payload marker exists."""
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xCC])
        option = bytes([(11 << 4) | 3]) + b"abc"
        data = header + option

        assert SamsungACClient._find_payload_offset(data) is None

    def test_extended_delta_one_byte(self) -> None:
        """Handles 1-byte extended delta (delta=13)."""
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xDD])
        # delta=13 means extended: next byte + 13. Encode delta=15 (15-13=2), len 2
        opt = bytes([(13 << 4) | 2, 2]) + b"xy"
        marker = b"\xff"
        payload = cbor2.dumps({"x": 1})
        data = header + opt + marker + payload

        offset = SamsungACClient._find_payload_offset(data)
        assert offset is not None
        assert cbor2.loads(data[offset:]) == {"x": 1}

    def test_extended_delta_two_bytes(self) -> None:
        """Handles 2-byte extended delta (delta=14)."""
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xEE])
        # delta=14 means 2-byte extended: next 2 bytes + 269
        # Encode delta=270 (270-269=1) => 0x0001, len 1
        opt = bytes([(14 << 4) | 1, 0x00, 0x01]) + b"z"
        marker = b"\xff"
        payload = cbor2.dumps({"y": 2})
        data = header + opt + marker + payload

        offset = SamsungACClient._find_payload_offset(data)
        assert offset is not None
        assert cbor2.loads(data[offset:]) == {"y": 2}

    def test_extended_length_one_byte(self) -> None:
        """Handles 1-byte extended length (length=13)."""
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xFF])
        # Wait - 0xFF in token position is fine, it's not at option position
        header = bytes([0x41, 0x01, 0x00, 0x01, 0xAB])
        # delta=11, length=13 (extended): next byte + 13. Encode len=20 (20-13=7)
        opt = bytes([(11 << 4) | 13, 7]) + b"a" * 20
        marker = b"\xff"
        payload = cbor2.dumps({})
        data = header + opt + marker + payload

        offset = SamsungACClient._find_payload_offset(data)
        assert offset is not None
        assert cbor2.loads(data[offset:]) == {}

    def test_empty_message_no_options(self) -> None:
        """Message with only header and token returns None."""
        data = bytes([0x41, 0x01, 0x00, 0x01, 0x01])
        assert SamsungACClient._find_payload_offset(data) is None


class TestSamsungVal:
    """Tests for _samsung_val bare and prefixed key lookup."""

    def test_bare_key(self) -> None:
        """Returns value when bare key exists."""
        data = {"power": "On"}
        assert _samsung_val(data, "power") == "On"

    def test_prefixed_key(self) -> None:
        """Returns value when Samsung-prefixed key exists."""
        data = {f"{SAMSUNG_PREFIX}power": "Off"}
        assert _samsung_val(data, "power") == "Off"

    def test_bare_key_takes_priority(self) -> None:
        """Bare key is checked before prefixed key."""
        data = {"power": "On", f"{SAMSUNG_PREFIX}power": "Off"}
        assert _samsung_val(data, "power") == "On"

    def test_missing_key_returns_none(self) -> None:
        """Returns None when neither key exists."""
        data = {"other": "value"}
        assert _samsung_val(data, "power") is None

    def test_empty_dict(self) -> None:
        """Returns None for empty dict."""
        assert _samsung_val({}, "anything") is None


class TestToInt:
    """Tests for _to_int numeric conversion."""

    def test_int_value(self) -> None:
        """Passes through int values."""
        assert _to_int(42) == 42

    def test_string_int(self) -> None:
        """Converts string integers."""
        assert _to_int("123") == 123

    def test_float_to_int(self) -> None:
        """Converts float to int (truncates)."""
        assert _to_int(3.7) == 3

    def test_none_returns_none(self) -> None:
        """Returns None for None input."""
        assert _to_int(None) is None

    def test_invalid_string_returns_none(self) -> None:
        """Returns None for non-numeric strings."""
        assert _to_int("abc") is None

    def test_empty_string_returns_none(self) -> None:
        """Returns None for empty string."""
        assert _to_int("") is None


class TestToFloat:
    """Tests for _to_float numeric conversion."""

    def test_float_value(self) -> None:
        """Passes through float values."""
        assert _to_float(3.14) == 3.14

    def test_string_float(self) -> None:
        """Converts string floats."""
        assert _to_float("22.5") == 22.5

    def test_int_to_float(self) -> None:
        """Converts int to float."""
        assert _to_float(10) == 10.0

    def test_none_returns_none(self) -> None:
        """Returns None for None input."""
        assert _to_float(None) is None

    def test_invalid_string_returns_none(self) -> None:
        """Returns None for non-numeric strings."""
        assert _to_float("not_a_number") is None


class TestParseEnum:
    """Tests for _parse_enum safe enum conversion."""

    def test_valid_value(self) -> None:
        """Converts valid enum value."""
        assert _parse_enum(Power, "On") == Power.ON

    def test_invalid_value_returns_none(self) -> None:
        """Returns None for invalid enum value."""
        assert _parse_enum(Power, "Invalid") is None

    def test_none_returns_none(self) -> None:
        """Returns None for None input."""
        assert _parse_enum(Power, None) is None

    def test_different_enum_types(self) -> None:
        """Works with various enum types."""
        assert _parse_enum(HvacMode, "Cool") == HvacMode.COOL
        assert _parse_enum(FanMode, "Auto") == FanMode.AUTO
        assert _parse_enum(SwingMode, "Fix") == SwingMode.FIX


class TestParseEnumList:
    """Tests for _parse_enum_list list conversion."""

    def test_valid_list(self) -> None:
        """Converts a list of valid enum values."""
        result = _parse_enum_list(HvacMode, ["Auto", "Cool", "Heat"])
        assert result == [HvacMode.AUTO, HvacMode.COOL, HvacMode.HEAT]

    def test_skips_invalid(self) -> None:
        """Skips invalid values without failing."""
        result = _parse_enum_list(HvacMode, ["Auto", "Invalid", "Cool"])
        assert result == [HvacMode.AUTO, HvacMode.COOL]

    def test_non_list_returns_empty(self) -> None:
        """Returns empty list for non-list input."""
        assert _parse_enum_list(HvacMode, None) == []
        assert _parse_enum_list(HvacMode, "Auto") == []

    def test_empty_list(self) -> None:
        """Returns empty list for empty input."""
        assert _parse_enum_list(HvacMode, []) == []


class TestParseModeOptions:
    """Tests for _parse_mode_options option string extraction."""

    def test_outdoor_temp_fahrenheit_to_celsius(self) -> None:
        """Converts outdoor temperature from Fahrenheit to Celsius."""
        status = ACStatus()
        _parse_mode_options(status, ["OutdoorTemp_77"])
        # (77 - 32) * 5/9 = 25.0
        assert status.outdoor_temperature == 25.0

    def test_outdoor_connection(self) -> None:
        """Parses outdoor connection status."""
        status = ACStatus()
        _parse_mode_options(status, ["OutdoorConnection_Connected"])
        assert status.outdoor_connected is True

        status2 = ACStatus()
        _parse_mode_options(status2, ["OutdoorConnection_Disconnected"])
        assert status2.outdoor_connected is False

    def test_duration_on(self) -> None:
        """Parses duration on minutes."""
        status = ACStatus()
        _parse_mode_options(status, ["DurationOn_120"])
        assert status.duration_on_minutes == 120

    def test_sleep_timer(self) -> None:
        """Parses sleep timer minutes."""
        status = ACStatus()
        _parse_mode_options(status, ["Sleep_60"])
        assert status.sleep_timer_minutes == 60

    def test_ai_temp_divided_by_ten(self) -> None:
        """AI temperature value is divided by 10."""
        status = ACStatus()
        _parse_mode_options(status, ["AiTemp_235"])
        assert status.ai_temperature == 23.5

    def test_multiple_options_parsed(self) -> None:
        """Multiple options are all parsed from the same list."""
        status = ACStatus()
        _parse_mode_options(
            status,
            ["OutdoorTemp_95", "DurationOn_45", "Sleep_0", "AiTemp_220"],
        )
        assert status.outdoor_temperature == pytest.approx(35.0)
        assert status.duration_on_minutes == 45
        assert status.sleep_timer_minutes == 0
        assert status.ai_temperature == 22.0

    def test_non_string_items_skipped(self) -> None:
        """Non-string items in options list are skipped."""
        status = ACStatus()
        _parse_mode_options(status, [123, None, "DurationOn_10"])
        assert status.duration_on_minutes == 10

    def test_no_underscore_skipped(self) -> None:
        """Options without underscore separator are skipped."""
        status = ACStatus()
        _parse_mode_options(status, ["NoSeparator"])
        assert status.outdoor_temperature is None
        assert status.duration_on_minutes is None


class TestParseBeep:
    """Tests for _parse_beep volume extraction."""

    def test_beep_on(self) -> None:
        """Extracts Volume_100 as BeepVolume.ON."""
        data = {f"{SAMSUNG_PREFIX}options": ["Volume_100", "OtherOption"]}
        assert _parse_beep(data) == BeepVolume.ON

    def test_beep_off(self) -> None:
        """Extracts Volume_Mute as BeepVolume.OFF."""
        data = {"options": ["Volume_Mute"]}
        assert _parse_beep(data) == BeepVolume.OFF

    def test_no_volume_option(self) -> None:
        """Returns None when no Volume_ option present."""
        data = {"options": ["SomeOther_Option"]}
        assert _parse_beep(data) is None

    def test_no_options_key(self) -> None:
        """Returns None when options key missing."""
        data = {"other": "value"}
        assert _parse_beep(data) is None

    def test_options_not_list(self) -> None:
        """Returns None when options is not a list."""
        data = {"options": "not_a_list"}
        assert _parse_beep(data) is None


class TestStatusPolling:
    """Tests for get_status with mocked _get responses."""

    def _poll(self, get_responses: dict) -> ACStatus:
        """Create a client, mock _get with canned responses, call get_status."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(
            client,
            "_get",
            side_effect=get_responses.get,
        ):
            return client.get_status()

    def test_power_polling(self) -> None:
        """Power state and operation count are populated."""
        status = self._poll(
            {
                Resource.POWER: {
                    f"{SAMSUNG_PREFIX}power": "On",
                    "operationNumber": "450",
                },
            }
        )
        assert status.power == Power.ON
        assert status.operation_count == 450

    def test_mode_polling(self) -> None:
        """HVAC mode, beep, supported modes, and mode options are populated."""
        status = self._poll(
            {
                Resource.MODE: {
                    "workingMode": "Cool",
                    f"{SAMSUNG_PREFIX}supportedModes": ["Auto", "Cool", "Heat"],
                    f"{SAMSUNG_PREFIX}options": [
                        "Volume_100",
                        "OutdoorTemp_86",
                        "DurationOn_30",
                    ],
                },
            }
        )
        assert status.hvac_mode == HvacMode.COOL
        assert status.beep == BeepVolume.ON
        assert status.supported_modes == [HvacMode.AUTO, HvacMode.COOL, HvacMode.HEAT]
        assert status.outdoor_temperature == pytest.approx(30.0)
        assert status.duration_on_minutes == 30

    def test_temperature_polling(self) -> None:
        """Current and target temperatures are populated."""
        status = self._poll(
            {
                Resource.TEMPERATURE_CURRENT: {
                    "temperature": "24.5",
                    "range": ["16.0", "30.0"],
                },
                Resource.TEMPERATURES: {
                    f"{SAMSUNG_PREFIX}items": [
                        {
                            f"{SAMSUNG_PREFIX}desired": "22.0",
                            f"{SAMSUNG_PREFIX}minimum": "16.0",
                            f"{SAMSUNG_PREFIX}maximum": "30.0",
                            f"{SAMSUNG_PREFIX}increment": "1.0",
                        },
                    ],
                },
            }
        )
        assert status.current_temperature == 24.5
        assert status.target_temperature == 22.0
        assert status.temperature_min == 16.0
        assert status.temperature_max == 30.0
        assert status.temperature_step == 1.0

    def test_fan_polling(self) -> None:
        """Fan mode is resolved from index."""
        status = self._poll(
            {
                Resource.WIND_STRENGTH: {f"{SAMSUNG_PREFIX}modes": "2"},
            }
        )
        assert status.fan_mode == FanMode.MID

    def test_swing_polling(self) -> None:
        """Swing mode and supported swings are populated."""
        status = self._poll(
            {
                Resource.WIND_DIRECTION: {
                    f"{SAMSUNG_PREFIX}modes": "Fix",
                    f"{SAMSUNG_PREFIX}supportedModes": ["Fix", "Up_And_Low", "All"],
                },
            }
        )
        assert status.swing_mode == SwingMode.FIX
        assert status.supported_swing == [
            SwingMode.FIX,
            SwingMode.VERTICAL,
            SwingMode.ALL,
        ]

    def test_convenient_polling(self) -> None:
        """Convenient mode and supported modes are populated."""
        status = self._poll(
            {
                Resource.CONVENIENT: {
                    f"{SAMSUNG_PREFIX}modes": "Nano",
                    f"{SAMSUNG_PREFIX}supportedModes": ["Off", "Nano", "Sleep"],
                },
            }
        )
        assert status.convenient_mode == ConvenientMode.WINDFREE
        assert ConvenientMode.SLEEP in status.supported_convenient

    def test_auto_clean_polling(self) -> None:
        """Auto-clean setting, active state, and progress are populated."""
        status = self._poll(
            {
                Resource.AUTO_CLEAN: {
                    f"{SAMSUNG_PREFIX}settingStatus": "On",
                    f"{SAMSUNG_PREFIX}status": "Start",
                    f"{SAMSUNG_PREFIX}progress": "42",
                },
            }
        )
        assert status.auto_clean_setting == AutoCleanSetting.ON
        assert status.auto_clean_active is True
        assert status.auto_clean_progress == 42

    def test_filter_polling(self) -> None:
        """Filter usage, capacity, and status are populated."""
        status = self._poll(
            {
                Resource.FILTER: {
                    f"{SAMSUNG_PREFIX}filterUsage": "120",
                    f"{SAMSUNG_PREFIX}filterCapacity": "2000",
                    f"{SAMSUNG_PREFIX}filterStatus": "Normal",
                },
            }
        )
        assert status.filter_usage_hours == 120
        assert status.filter_capacity_hours == 2000
        assert status.filter_status == "Normal"

    def test_energy_polling(self) -> None:
        """Energy consumption is populated."""
        status = self._poll(
            {
                Resource.ENERGY: {f"{SAMSUNG_PREFIX}cumulativePower": "15000"},
            }
        )
        assert status.energy_wh == 15000

    def test_rssi_polling(self) -> None:
        """WiFi RSSI is populated from list."""
        status = self._poll(
            {
                Resource.RM_WIFI: {"x.com.samsung.rm.rssi": [-55]},
            }
        )
        assert status.rssi == -55

    def test_ai_sleep_polling(self) -> None:
        """AI sleep active and elapsed time are populated."""
        status = self._poll(
            {
                Resource.AI_SLEEP: {f"{SAMSUNG_PREFIX}elapsedTime": "30"},
            }
        )
        assert status.ai_sleep_active is True
        assert status.ai_sleep_elapsed_minutes == 30

    def test_mute_once_polling(self) -> None:
        """Mute once state is populated."""
        status = self._poll(
            {
                Resource.MUTE_ONCE: {"muteonce": "On"},
            }
        )
        assert status.mute_once is True

    def test_cloud_connected_polling(self) -> None:
        """Cloud connection status is populated."""
        status = self._poll(
            {
                Resource.REMOTE_DATA_CONTROL: {
                    f"{SAMSUNG_PREFIX}connectionStatus": "Connected",
                },
            }
        )
        assert status.cloud_connected is True

    def test_missing_resources_leave_none(self) -> None:
        """Fields remain None when resources return None."""
        status = self._poll({})
        assert status.power is None
        assert status.hvac_mode is None
        assert status.current_temperature is None
        assert status.fan_mode is None
        assert status.rssi is None

    def test_humidity_polling(self) -> None:
        """Humidity is populated from Samsung-prefixed key."""
        status = self._poll(
            {
                Resource.HUMIDITY: {f"{SAMSUNG_PREFIX}fivepercentHumidity": 55},
            }
        )
        assert status.humidity == 55

    def test_light_polling(self) -> None:
        """Light mode is populated."""
        status = self._poll(
            {
                Resource.LIGHT: {"mode": "Off"},
            }
        )
        assert status.light == LightMode.OFF

    def test_alarms_polling(self) -> None:
        """Alarms are populated from items list."""
        status = self._poll(
            {
                Resource.ALARMS: {
                    f"{SAMSUNG_PREFIX}items": [
                        {
                            f"{SAMSUNG_PREFIX}code": "E101",
                            f"{SAMSUNG_PREFIX}state": "Active",
                            f"{SAMSUNG_PREFIX}triggeredTime": "2024-01-01T00:00:00",
                        },
                    ],
                },
            }
        )
        assert len(status.alarms) == 1
        assert status.alarms[0]["code"] == "E101"
        assert status.alarms[0]["state"] == "Active"

    def test_air_purify_polling(self) -> None:
        """Air purify mode is populated."""
        status = self._poll(
            {
                Resource.AIR_PURIFY: {f"{SAMSUNG_PREFIX}modes": "On"},
            }
        )
        assert status.air_purify == AirPurifyMode.ON


class TestPostValidation:
    """Tests for _post command response validation logic."""

    def _post(self, code: str, data: dict | None, payload: dict) -> bool:
        """Create a client, mock _request_locked, call _post."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(client, "_request_locked", return_value=(code, data)):
            return client._post(Resource.POWER, payload)

    def test_success_result_true(self) -> None:
        """Accepts 2.04 with controlResponse.result=True."""
        result = self._post(
            "2.04", {"controlResponse": {"result": True}}, {"power": "On"}
        )
        assert result is True

    def test_success_error_code_unchanged(self) -> None:
        """Accepts 2.04 with controlResponse.errorCode='unchanged'."""
        result = self._post(
            "2.04",
            {"controlResponse": {"errorCode": "unchanged"}},
            {"power": "On"},
        )
        assert result is True

    def test_wrong_code_rejected(self) -> None:
        """Rejects non-2.04 response codes."""
        result = self._post(
            "4.00", {"controlResponse": {"result": True}}, {"power": "On"}
        )
        assert result is False

    def test_no_control_response_rejected(self) -> None:
        """Rejects 2.04 without controlResponse."""
        assert self._post("2.04", {"other": "data"}, {"power": "On"}) is False

    def test_none_data_rejected(self) -> None:
        """Rejects 2.04 with None payload."""
        assert self._post("2.04", None, {"power": "On"}) is False

    def test_result_false_rejected(self) -> None:
        """Rejects controlResponse with result=False and no 'unchanged' errorCode."""
        result = self._post(
            "2.04",
            {"controlResponse": {"result": False, "errorCode": "failed"}},
            {"power": "On"},
        )
        assert result is False

    def test_connection_error_returns_false(self) -> None:
        """Returns False on connection error."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(
            client,
            "_request_locked",
            side_effect=SamsungACConnectionError("conn failed"),
        ):
            assert client._post(Resource.POWER, {"power": "On"}) is False

    def test_request_error_returns_false(self) -> None:
        """Returns False on request error."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(
            client,
            "_request_locked",
            side_effect=SamsungACRequestError("no response"),
        ):
            assert client._post(Resource.POWER, {"power": "On"}) is False


class TestConnectionManagement:
    """Tests for connect, disconnect, and reconnect behavior."""

    def test_connect_success(self) -> None:
        """Successful connection sets _conn and _sock."""
        with (
            patch(
                "custom_components.samsung_ac_local.api.socket.socket"
            ) as mock_socket_cls,
            patch("custom_components.samsung_ac_local.api.crypto"),
            patch("custom_components.samsung_ac_local.api.SSL") as mock_ssl,
        ):
            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock

            mock_ctx = MagicMock()
            mock_ssl.Context.return_value = mock_ctx
            mock_ssl.DTLS_CLIENT_METHOD = "dtls_method"
            mock_ssl.VERIFY_NONE = 0

            mock_conn = MagicMock()
            mock_ssl.Connection.return_value = mock_conn
            mock_conn.do_handshake.return_value = None

            client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
            client.connect()

            assert client.connected is True
            mock_sock.connect.assert_called_once_with(("192.168.1.100", 49154))
            mock_conn.set_connect_state.assert_called_once()
            mock_conn.do_handshake.assert_called()

    def test_connect_timeout_raises(self) -> None:
        """Raises SamsungACConnectionError on handshake timeout."""
        with (
            patch(
                "custom_components.samsung_ac_local.api.time.monotonic",
            ) as mock_time,
            patch(
                "custom_components.samsung_ac_local.api.socket.socket",
            ) as mock_socket_cls,
            patch("custom_components.samsung_ac_local.api.crypto"),
            patch(
                "custom_components.samsung_ac_local.api.SSL",
            ) as mock_ssl,
            patch(
                "custom_components.samsung_ac_local.api.select.select",
            ) as mock_select,
        ):
            mock_sock = MagicMock()
            mock_socket_cls.return_value = mock_sock

            mock_ctx = MagicMock()
            mock_ssl.Context.return_value = mock_ctx
            mock_ssl.DTLS_CLIENT_METHOD = "dtls_method"
            mock_ssl.VERIFY_NONE = 0
            mock_ssl.WantReadError = type("WantReadError", (Exception,), {})
            mock_ssl.Error = type("SSLError", (Exception,), {})

            mock_conn = MagicMock()
            mock_ssl.Connection.return_value = mock_conn
            mock_conn.do_handshake.side_effect = mock_ssl.WantReadError()

            mock_select.return_value = ([mock_sock], [], [])

            # Simulate time passing beyond timeout (10s)
            mock_time.side_effect = [0.0, 0.0, 5.0, 11.0]

            client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
            with pytest.raises(SamsungACConnectionError, match="timed out"):
                client.connect()

    def test_disconnect_clears_state(self) -> None:
        """Disconnect clears _conn and _sock."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client._conn = MagicMock()
        client._sock = MagicMock()

        client.disconnect()

        assert client._conn is None
        assert client._sock is None
        assert client.connected is False

    def test_disconnect_when_not_connected(self) -> None:
        """Disconnect is safe to call when not connected."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client.disconnect()  # Should not raise
        assert client.connected is False

    @patch("custom_components.samsung_ac_local.api.select.select")
    def test_request_reconnects_on_failure(self, mock_select: MagicMock) -> None:
        """Request retries with reconnect after first failure."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)

        mock_conn = MagicMock()
        client._conn = mock_conn
        client._sock = MagicMock()

        # First send raises (connection lost)
        mock_conn.send.side_effect = OSError("Connection reset")

        # After reconnect, new connection works
        new_conn = MagicMock()
        new_sock = MagicMock()

        # Build response: ACK, code 2.05, MID matches second _build_message call
        # First attempt: _mid 0->1 (token=0x01), send fails, reconnect
        # Second attempt: _mid 1->2 (token=0x02), send succeeds
        response = bytes([0x61, (2 << 5) | 5, 0x00, 0x02, 0x02])
        response += b"\xff" + cbor2.dumps({"key": "val"})
        new_conn.recv.return_value = response
        new_conn.send.return_value = None

        mock_select.return_value = ([new_sock], [], [])

        with patch.object(client, "_connect_locked") as mock_connect:

            def do_connect() -> None:
                client._conn = new_conn
                client._sock = new_sock

            mock_connect.side_effect = do_connect

            code, data = client._request_locked(COAP_GET, "power/vs/0")

        assert code == "2.05"
        assert data == {"key": "val"}
        # Verify reconnect was triggered
        mock_connect.assert_called_once()

    def test_host_property(self) -> None:
        """Host property returns the configured address."""
        client = SamsungACClient("10.0.0.1", FAKE_CERT, FAKE_KEY)
        assert client.host == "10.0.0.1"

    def test_connected_property_false_initially(self) -> None:
        """Connected property is False before connect()."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        assert client.connected is False


class TestTokenValidation:
    """Tests for _receive_response token matching."""

    @patch("custom_components.samsung_ac_local.api.select.select")
    def test_matching_token_accepted(self, mock_select: MagicMock) -> None:
        """Response with matching token is accepted."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client._mid = 42

        mock_conn = MagicMock()
        mock_sock = MagicMock()
        client._conn = mock_conn
        client._sock = mock_sock

        # Build response with token = 42 (0x2A)
        response = bytes([0x61, (2 << 5) | 5, 0x00, 0x2A, 0x2A])
        mock_conn.recv.return_value = response
        mock_select.return_value = ([mock_sock], [], [])

        code, _payload = client._receive_response()
        assert code == "2.05"

    @patch("custom_components.samsung_ac_local.api.select.select")
    def test_mismatched_token_discarded(self, mock_select: MagicMock) -> None:
        """Response with wrong token is discarded, raises after retries."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client._mid = 42

        mock_conn = MagicMock()
        mock_sock = MagicMock()
        client._conn = mock_conn
        client._sock = mock_sock

        # Response with wrong token (0x99 instead of 0x2A)
        wrong_response = bytes([0x61, (2 << 5) | 5, 0x00, 0x2A, 0x99])
        mock_conn.recv.return_value = wrong_response
        mock_select.return_value = ([mock_sock], [], [])

        with pytest.raises(SamsungACRequestError, match="No response after"):
            client._receive_response()

    @patch("custom_components.samsung_ac_local.api.select.select")
    def test_timeout_no_data_raises(self, mock_select: MagicMock) -> None:
        """Raises SamsungACRequestError when select times out."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client._mid = 1

        mock_sock = MagicMock()
        client._conn = MagicMock()
        client._sock = mock_sock

        # select returns empty (no data ready)
        mock_select.return_value = ([], [], [])

        with pytest.raises(SamsungACRequestError, match="No response after"):
            client._receive_response()

    @patch("custom_components.samsung_ac_local.api.select.select")
    def test_short_response_discarded(self, mock_select: MagicMock) -> None:
        """Response shorter than minimum is discarded."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client._mid = 1

        mock_conn = MagicMock()
        mock_sock = MagicMock()
        client._conn = mock_conn
        client._sock = mock_sock

        # Response too short (only 4 bytes, needs at least 5 for TKL=1)
        mock_conn.recv.return_value = bytes([0x61, 0x45, 0x00, 0x01])
        mock_select.return_value = ([mock_sock], [], [])

        with pytest.raises(SamsungACRequestError, match="No response after"):
            client._receive_response()

    @patch("custom_components.samsung_ac_local.api.select.select")
    def test_second_response_matches(self, mock_select: MagicMock) -> None:
        """First mismatched response discarded, second matching one accepted."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        client._mid = 5
        client._max_retries = 3

        mock_conn = MagicMock()
        mock_sock = MagicMock()
        client._conn = mock_conn
        client._sock = mock_sock

        # First: wrong token (0x99), second: correct token (0x05)
        wrong = bytes([0x61, (2 << 5) | 5, 0x00, 0x05, 0x99])
        correct = bytes([0x61, (2 << 5) | 5, 0x00, 0x05, 0x05])
        mock_conn.recv.side_effect = [wrong, correct]
        mock_select.return_value = ([mock_sock], [], [])

        code, _ = client._receive_response()
        assert code == "2.05"


class TestGetWrapper:
    """Tests for _get convenience wrapper."""

    def test_get_success_returns_dict(self) -> None:
        """Successful GET returns the dict payload."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        expected = {"power": "On"}
        with patch.object(client, "_request_locked", return_value=("2.05", expected)):
            result = client._get(Resource.POWER)
        assert result == expected

    def test_get_non_success_code_returns_none(self) -> None:
        """Non-2.xx code returns None."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(client, "_request_locked", return_value=("4.04", None)):
            result = client._get(Resource.POWER)
        assert result is None

    def test_get_non_dict_payload_returns_none(self) -> None:
        """Non-dict payload (e.g. firmware quirk) returns None."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(client, "_request_locked", return_value=("2.05", [1, 2, 3])):
            result = client._get(Resource.POWER)
        assert result is None

    def test_get_connection_error_returns_none(self) -> None:
        """Connection error returns None without raising."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(
            client,
            "_request_locked",
            side_effect=SamsungACConnectionError("fail"),
        ):
            result = client._get(Resource.POWER)
        assert result is None

    def test_get_request_error_returns_none(self) -> None:
        """Request error returns None without raising."""
        client = SamsungACClient("192.168.1.100", FAKE_CERT, FAKE_KEY)
        with patch.object(
            client,
            "_request_locked",
            side_effect=SamsungACRequestError("timeout"),
        ):
            result = client._get(Resource.POWER)
        assert result is None
