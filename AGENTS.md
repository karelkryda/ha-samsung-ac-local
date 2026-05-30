# AGENTS.md

## Project Overview

Home Assistant custom integration for local control of Samsung OCF air conditioners via DTLS/CoAP. Bypasses Samsung SmartThings cloud entirely using pyOpenSSL for DTLS transport.

## Architecture

- `api.py` - Blocking DTLS/CoAP client. Thread-safe, persistent connection, ~50ms per command. Uses pyOpenSSL (HA core dependency) + cbor2. Called via `async_add_executor_job`.
- `coordinator.py` - DataUpdateCoordinator polling `get_status()` every N seconds (configurable).
- `climate.py` - ClimateEntity with HVAC modes, fan, swing, presets (convenient modes).
- `sensor.py` - 12 sensors (energy, temps, filter, RSSI, timers, etc.)
- `switch.py` - 4 switches (light, beep, air purify, auto clean).
- `binary_sensor.py` - 5 binary sensors (cloud connected, outdoor unit, auto clean active, AI sleep, mute once).
- `config_flow.py` - Setup flow (host + cert paths) + options flow (poll interval).
- `const.py` - All enums, resource paths, protocol constants.
- `data.py` - Typed ConfigEntry runtime data.

## Protocol Details

- Transport: DTLS 1.2 over UDP port 49154 (pyOpenSSL `DTLS_CLIENT_METHOD`)
- Payload: CoAP (RFC 7252) with CBOR-encoded bodies
- Auth: Self-signed EC cert with UUID in subject field, matched against device ACL
- Handshake: ~4-5s initial, then persistent connection
- Responses: Some resources use indefinite-length CBOR with 0xFF break codes
- CoAP payload marker found by walking options structure (not naive byte search)

## Key Design Decisions

- pyOpenSSL over python-mbedtls: HA runs on Alpine (musl), mbedtls has no musl wheels. pyOpenSSL is already in HA core.
- Blocking client + executor: pyOpenSSL DTLS is synchronous. No async DTLS lib exists for Python.
- Class-level timeouts: 10s handshake, 3s recv - not configurable, they're protocol physics.
- Token validation in responses: UDP can deliver stale/reordered packets.
- Samsung uses Fahrenheit for outdoor temp in options array despite device locale.
- `_get()` guards against non-dict CBOR responses (firmware quirk, returns None).

## Samsung Protocol Quirks

- Values in mode options array are strings (`"0"` not `0`), need `_to_int()`/`_to_float()`.
- `x.com.samsung.da.` prefix on some keys, bare on others - `_samsung_val()` tries both.
- `OutdoorTemp` value is in Fahrenheit, converted to Celsius in client.
- `remotedatacontrol/vs/0` occasionally returns malformed CBOR (0xFF break as payload).
- Fan modes use integer indices (0-4), not string names.
- AC doesn't verify TLS cert chains - only extracts UUID from subject and checks ACL.

## Testing

Client can be tested standalone without HA using importlib trick (see CONTRIBUTING.md).
Live AC at 192.168.40.16:49154. Certs in samsung_ac_project/final_access/.

## Ruff Config

`select = ["ALL"]` with minimal ignores. Python 3.14 target. No `from __future__ import annotations` needed.
