# Samsung AC Local

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Local control of Samsung OCF air conditioners via DTLS/CoAP - no cloud, no SmartThings dependency.

## Features

- Direct local communication over DTLS (encrypted UDP)
- Persistent connection with ~50ms command latency
- Full climate entity (HVAC modes, temperature, fan, swing, presets)
- WindFree, Sleep, Quiet, Smart, Speed, DryComfort preset modes
- Sensors: outdoor temperature, energy consumption, filter usage, WiFi RSSI
- Switches: display light, beep, air purify, auto-clean
- Binary sensors: cloud connection status, auto-clean activity

## Requirements

- Samsung OCF air conditioner (WindFree, AR series, etc.) paired with SmartThings
- Client certificate with ACL access on the AC (see [Setup guide](#setup-guide))
- AC on the same local network as Home Assistant

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "Samsung AC Local"
3. Restart Home Assistant

### Manual

Copy `custom_components/samsung_ac_local` to your HA `config/custom_components/` directory.

## Setup guide

### Certificate preparation

The AC accepts any self-signed certificate that contains a UUID matching its ACL. After normal SmartThings pairing, the Samsung cloud server UUID has full access:

```bash
openssl req -new -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
    -keyout client_key.pem -out client_cert.pem -days 3650 -nodes \
    -subj "/OU=uuid:ab0b0ac4-aae9-4958-a04d-8ec36fe1b2f9/CN=local"
```

Place the files in `/config/samsung_ac/` on your HA instance:

- `/config/samsung_ac/client_cert.pem`
- `/config/samsung_ac/client_key.pem`

### Configuration

1. Go to Settings > Devices & Services > Add Integration
2. Search for "Samsung AC Local"
3. Enter the AC's IP address and certificate file paths
4. The integration will test the connection during setup

### Options

- **Polling interval** (default 30s): configurable via integration options after setup

## Supported models

Tested on Samsung WindFree 2 (AR70F09C1AWNEU). Should work with any Samsung OCF air conditioner that uses DTLS/CoAP on port 49154 after SmartThings pairing.

## Credits

Built on reverse-engineering research of the Samsung OCF protocol, including BLE pairing flow capture, Frida hooking of SmartThings APK, and IoTivity protocol analysis.
