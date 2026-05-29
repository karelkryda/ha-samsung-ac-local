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
  __init__.py       - Integration setup and teardown
  api.py            - DTLS/CoAP client (blocking, thread-safe)
  config_flow.py    - UI configuration flow
  const.py          - Constants, enums, resource paths
  coordinator.py    - DataUpdateCoordinator for polling
  data.py           - Runtime data types
  climate.py        - Climate entity
  sensor.py         - Sensor entities
  switch.py         - Switch entities
  binary_sensor.py  - Binary sensor entities
  manifest.json     - Integration manifest
  translations/     - UI strings
```

## Testing the client

You can test the DTLS client against a live AC without running HA:

```python
import importlib.util
import sys
from pathlib import Path

# Load api module directly (avoids HA dependency in __init__.py)
for module_name, file_name in [("samsung_ac_local.const", "const.py"), ("samsung_ac_local.api", "api.py")]:
    spec = importlib.util.spec_from_file_location(module_name, f"custom_components/samsung_ac_local/{file_name}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)

from samsung_ac_local.api import SamsungACClient

client = SamsungACClient(
    "192.168.x.x",
    Path("path/to/client_cert.pem").read_text(),
    Path("path/to/client_key.pem").read_text(),
)
client.connect()
print(client.get_status())
client.disconnect()
```

## Reporting issues

Please include:

- Your AC model
- Home Assistant version
- Relevant log entries (enable debug logging for `custom_components.samsung_ac_local`)
