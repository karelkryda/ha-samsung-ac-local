# AGENTS.md

## Project Overview

Home Assistant custom integration for local control of Samsung OCF air conditioners via DTLS/CoAP. Bypasses Samsung SmartThings cloud entirely using pyOpenSSL for DTLS transport.

## Architecture

- `api.py` - Blocking DTLS/CoAP client. Thread-safe, persistent connection, ~50ms per command. Uses pyOpenSSL (HA core dependency) + cbor2. Called via `async_add_executor_job`.
- `cert.py` - Bundled self-signed EC certificate with the Samsung cloud server UUID. No external cert files needed.
- `coordinator.py` - DataUpdateCoordinator polling `get_status()` every N seconds (configurable).
- `climate.py` - ClimateEntity with HVAC modes, fan, swing, presets (convenient modes).
- `sensor.py` - 12 sensors (energy, temps, filter, RSSI, timers, etc.)
- `switch.py` - 4 switches (light, beep, air purify, auto clean).
- `binary_sensor.py` - 5 binary sensors (cloud connected, outdoor unit, auto clean active, AI sleep, mute once).
- `button.py` - 2 buttons (start/stop auto-clean cycle).
- `config_flow.py` - Setup flow (host only) + options flow (poll interval).
- `const.py` - All enums, resource paths, protocol constants.
- `data.py` - Typed ConfigEntry runtime data.

## Protocol Details

- Transport: DTLS 1.2 over UDP port 49154 (pyOpenSSL `DTLS_CLIENT_METHOD`)
- Payload: CoAP (RFC 7252) with CBOR-encoded bodies
- Auth: Self-signed EC cert with Samsung cloud UUID in subject field - device checks UUID against ACL
- Handshake: ~4-5s initial, then persistent connection
- Responses: Some resources use indefinite-length CBOR with 0xFF break codes
- CoAP payload marker found by walking options structure (not naive byte search)

## Key Design Decisions

- pyOpenSSL over python-mbedtls: HA runs on Alpine (musl), mbedtls has no musl wheels. pyOpenSSL is already in HA core.
- Blocking client + executor: pyOpenSSL DTLS is synchronous. No async DTLS lib exists for Python.
- Bundled certificate: The Samsung cloud UUID is global (same for all Samsung OCF devices) and provisioned into every device's ACL during SmartThings pairing. The AC does not verify cert chains - it only extracts the UUID and checks ACL. This means zero setup beyond providing the AC IP.
- Class-level timeouts: 10s handshake, 3s recv - not configurable, they're protocol physics.
- Token validation in responses: UDP can deliver stale/reordered packets.
- Samsung uses Fahrenheit for outdoor temp in options array despite device locale.
- `_get()` guards against non-dict CBOR responses (firmware quirk, returns None).
- Optimistic state updates: after a confirmed command (2.04 + controlResponse), entities update coordinator data immediately via `async_update_optimistic()`. No post-command polling. The regular poll cycle (configurable, default 30s) serves as reconciliation for side effects and external changes.
- `_post()` validates: code == "2.04" AND controlResponse present AND (result is True OR errorCode == "unchanged"). Returns bool.
- `async_set_updated_data` resets the poll timer, preventing a scheduled poll from overwriting optimistic state with stale data.

## CoAP Observe (Push) - Discovered, Not Yet Implemented

All 18 resources support CoAP Observe (RFC 7641). Tested:

- AC responds with Observe option in GET+Observe initial response.
- Notifications are NON (non-confirmable) with full resource payload (CBOR).
- Push works across connections (command on connection A triggers notification on connection B).
- Notification contains the real new state (arrives after internal propagation).
- Propagation time: 468-705ms for single resource.

Future enhancement: register Observe on all resources for instant push updates, keep polling as fallback for missed UDP packets. Would require client re-architecture (background listener thread for multiplexing notifications and command responses on same socket).

## Samsung Protocol Quirks

- Values in mode options array are strings (`"0"` not `0`), need `_to_int()`/`_to_float()`.
- `x.com.samsung.da.` prefix on some keys, bare on others - `_samsung_val()` tries both.
- `OutdoorTemp` value is in Fahrenheit, converted to Celsius in client.
- `remotedatacontrol/vs/0` occasionally returns malformed CBOR (0xFF break as payload).
- Fan modes use integer indices (0-4), not string names.
- AC doesn't verify TLS cert chains - only extracts UUID from subject and checks ACL.

## Testing

Run `pytest tests/` from the project root. Tests mock the DTLS socket layer and do not require a live AC. Uses `pytest-homeassistant-custom-component` for HA integration tests and plain pytest for protocol-level tests.

## Ruff Config

`select = ["ALL"]` with minimal ignores. Python 3.14 target. No `from __future__ import annotations` needed. Tests exempt from S101/SLF001/PLR2004/ANN201/D1xx/D205/D400/D415/TC001-003.
