# Display-light investigation — solved 2026-11-08

Why the `samsung_ac_display_light` switches read `unknown` and never changed
anything, and what the fix is (patch 3 in this directory). Units: 4× Samsung
WindFree, firmware family `TP1X_DA-AC-RAC-01001_0000`, US (ARA-WW) build,
firmware 260327/11260327-era. EU units with the SAME version string behave
differently — see "Why the EU project worked" below.

## The symptom chain

1. HA `switch.samsung_ac_display_light*` always read `unknown` (ON write) or
   settled `off` (OFF write) — regardless of the physical panel.
2. Bridge web-UI / HomeKit "light off" did nothing visible.
3. Every probe below was user-verified against the physical panel.

## What was ruled out (evidence trail)

| Probe | Result |
|---|---|
| HA switch ON/OFF (→ `POST /light/vs/0 {"mode": On/Off}`) | 200 + optimistic state, panel never changed (both directions) |
| 4 payload shapes on `/light/vs/0` × 4 units (bare `mode`, prefixed `x.com.samsung.da.mode`, options array `["Light_Off"]`, SmartThings-style execute on `/mode/vs/0`) | All acked 2.04, none applied |
| Field-name matrix on `/light/vs/0` (`x.com.samsung.da.modes` str+list, `lightMode`, `light`, bare `lightMode`) | All echoed verbatim — the resource parses nothing |
| 15 alternative resource names (`display/panel/led/screen/indicator/…`) | All 4.04 Not Found |
| `GET /light/vs/0` via two independent DTLS/CoAP stacks (karelkryda hand-rolled, `smartthings-local` 0.1.0 with Block2) | `2.05` + **empty map** — no state stored |
| `GET /oic/res` (proper Block2 decode) | 19 advertised resources, **no AC resources at all** — the unit hides its working surface; `/hass/*` advertised but 4.04 |
| `GET /device/0` link walk (the real enumeration) | 37 resources — `/light/vs/0` present, **no other light-named resource** |
| `/configuration/vs/0` option packs | `SingleCommand_1, HOMECARE_WIZARD_V2, PRODUCT_GLOBAL, AI_RAC_GLOBAL_HEATPUMP_3.0, AI_3.0, Auto_To_AI, AI_Heat` — no light pack (NOTE: not conclusive by itself; the list also omits climate features that demonstrably work) |
| `POST /aisleep/vs/0 displayNightMode=On` | Acked, reverted on readback (telemetry-only field) |

## The answer (verified end-to-end on a US unit)

The display light is a **token in `/mode/vs/0`'s options array**, with
**inverted semantics** — the token means "display-off mode active":

- Panel **lit** ⇔ options contains `Light_Off`
- Panel **dark** ⇔ options contains `Light_On`

Write shape (the ONLY shape that sticks — a full-array write gets merged and
the Light token reverted within seconds):

```
POST /mode/vs/0  {"x.com.samsung.da.options": ["Light_On"]}    # panel OFF
POST /mode/vs/0  {"x.com.samsung.da.options": ["Light_Off"]}   # panel ON
```

First successful write held its state on readback (all prior attempts
reverted) and the user confirmed the panel went dark. Same token is the
light's true state, so `ACStatus.light` now parses it (polarity flipped) and
HA's switches report reality.

## Why the EU project worked with a "dedicated" resource

`bonzanni/ha-samsung-ac-windfree` (validated on `AR60F12C1AWNEU`, same
firmware version string) reads/writes a real stateful `/light/vs/0` with
`mode`+`supportedModes`. Its own README pins support per full model-number
hash "another physical unit — even the same retail model — is not supported".
The EU board ships the light feature in the OCF stack; the US ARA-WW board
ships `/light/vs/0` as a hollow stub and carries the control in the mode
options token instead. (`mbillow/localthings` documents both encodings and
the inverted polarity — the decisive pointer.)

## Artifacts

- `probe_display_light.py` — the probe script (read options, flip token,
  verify readback) for any unit IP.
