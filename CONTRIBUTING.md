# Contributing to Samsung AC Local

## Development setup

1. Clone the repository
2. Open in VS Code with the Dev Containers extension
3. The container will install all dependencies automatically via `scripts/setup`
4. Run `scripts/develop` to start Home Assistant with the integration loaded

## Code standards

- All code must pass `ruff check` with the project's strict ALL config
- All code must pass `ruff format`
- Python 3.14+ (no `from __future__ import annotations`)
- Docstrings on all public classes and methods
- Type annotations on all function signatures

## Project structure

```
custom_components/samsung_ac_local/
  __init__.py         - Integration setup and teardown
  api.py              - DTLS/CoAP client (blocking, thread-safe)
  cert.py             - Bundled client certificate (Samsung cloud UUID)
  config_flow.py      - UI configuration flow
  const.py            - Constants, enums, resource paths
  coordinator.py      - DataUpdateCoordinator for polling
  data.py             - Runtime data types
  climate.py          - Climate entity
  sensor.py           - Sensor entities
  switch.py           - Switch entities
  binary_sensor.py    - Binary sensor entities
  manifest.json       - Integration manifest
  translations/       - UI strings

tests/
  conftest.py         - Shared fixtures
  test_api.py         - CoAP client tests (protocol, parsing, connection)
  test_config_flow.py - Config flow tests
  test_coordinator.py - Coordinator tests
  test_entities.py    - Entity tests (climate, sensor, switch, binary_sensor)
```

## Testing

```bash
# Run all tests
.venv/bin/pytest tests/

# Run with verbose output
.venv/bin/pytest tests/ -v

# Run only API tests
.venv/bin/pytest tests/test_api.py
```

Tests use `pytest-homeassistant-custom-component` for HA integration tests and plain pytest for protocol-level tests. All tests mock the DTLS socket layer and do not require a live AC device.

## How the certificate works

The integration bundles a self-signed EC certificate containing the Samsung global cloud
server UUID. Every Samsung OCF device trusts this UUID after SmartThings pairing because:

1. During SmartThings pairing, the cloud server UUID is added to the device ACL with full access
2. Samsung OCF devices do not verify TLS certificate chains
3. They only extract the UUID from the client certificate subject and check it against the ACL

This means any self-signed certificate with the correct UUID gets full device access on the LAN.
