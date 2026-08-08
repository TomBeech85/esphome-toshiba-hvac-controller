# Integrated ESP32 Toshiba HVAC Controller Board

**Date:** 2026-08-08
**Status:** Approved
**Base:** fork of [florianbrede-ayet/esphome-toshiba-hvac-controller](https://github.com/florianbrede-ayet/esphome-toshiba-hvac-controller)

## Purpose

The upstream hardware is a carrier PCB that a 38-pin ESP32 DevKit plugs into via two 1x19 pin
sockets. That stack is too tall for some indoor units (the README documents Haori units where the
sockets had to be omitted and the DevKit soldered flat). This project replaces the DevKit and
sockets with an ESP32-WROOM-32E soldered directly to the board, absorbing the support circuitry
the DevKit provided, so the result is a single low-profile board assembled entirely by JLCPCB.

The firmware is unchanged. The ESPHome component drives the AC over UART on GPIO33 (TX) and
GPIO32 (RX), which leaves UART0 (GPIO1/GPIO3) free for the USB bridge exactly as on a DevKit.
`board: esp32dev` still applies. The only (optional) yaml addition is a `status_led` on GPIO2.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| MCU module | ESP32-WROOM-32E (4MB) | Same silicon as the DevKit the project targets; zero firmware changes |
| Programming | Onboard USB-C + CP2102N + auto-reset | DevKit-identical `esphome run` workflow; first flash only, OTA after |
| Power | Diode-OR of AC 5V and USB VBUS into AMS1117-3.3 | Bench-flash on USB, deploy on AC 5V, no jumpers, no backfeed into the AC unit |
| Form factor | Upstream board outline and JST position | Documented install fit in every supported indoor unit holds |
| Extras | EN + BOOT tact switches, status LED on GPIO2 | Recovery when auto-reset misbehaves; WiFi/API state visible during install |
| Destination | Own fork, JLCPCB full PCBA | Personal build; KiCad 9 tooling acceptable |

## Circuit blocks

### AC interface (copied verbatim from upstream)

JST S05B-PASK-2(LF)(SN) (J1), net mapping identical to the upstream schematic, which is proven in
the field:

| J1 pin | Net |
|---|---|
| 1 | ESP_TX_5V |
| 2 | GND |
| 3 | +5V (from the indoor unit) |
| 4 | ESP_RX_5V |
| 5 | NC |

TXS0108EPW (U2) level shifter between the 5V UART and the module: B-side at 5V carries
ESP_TX_5V/ESP_RX_5V, A-side at 3.3V connects to GPIO33 (TX) and GPIO32 (RX). OE pulled up with
10k to VCCA as upstream (shifter is always enabled once 3.3V is up). 100nF decoupling per supply
pin as upstream.

### Power

Two 5V sources, each through a Schottky diode (SS34/B5819W class, >=1A) into a common +5V rail:

- AC 5V from J1 pin 3
- USB VBUS from the USB-C receptacle

The +5V rail feeds the TXS0108E B-side (VCCB) and an AMS1117-3.3 LDO. The LDO output is the +3.3V
rail for the WROOM, CP2102N, TXS0108E A-side (VCCA) and status LED. Bulk capacitance: 22uF on the
LDO input and output (AMS1117 stability requirement), plus 10uF + 100nF at the WROOM's 3V3 pin
(WiFi TX burst demand) and 100nF decoupling at each IC.

### USB and programming

USB-C receptacle (16-pin, USB 2.0 only), CC1/CC2 each pulled down with 5.1k so USB-C sources
offer 5V. D+/D- to the CP2102N-A02-GQFN24. CP2102N powered from +3.3V (self-powered
configuration, VBUS sense via divider per datasheet). TXD/RXD cross-connected to the WROOM's
GPIO3 (U0RXD) and GPIO1 (U0TXD).

Auto-reset: the standard NodeMCU/DevKitC two-transistor circuit (2x S8050 or MMBT2222 + 2x 10k)
from DTR/RTS to EN and IO0, so esptool can enter and leave the bootloader without buttons.

### Module support circuitry (absorbed from the DevKit)

- EN: 10k pullup to 3.3V + 1uF to GND (power-on reset RC), EN tact switch to GND
- IO0: 10k pullup, BOOT tact switch to GND (parallel with the auto-reset transistor)
- Strapping: IO12 (MTDI) left floating/low, IO2 used only for the LED (pulls low at boot are fine)
- Status LED: 0603 LED + 1k from GPIO2 to GND (active high, matching DevKit convention)

### Board

- 2 layers, 1.6mm, HASL or ENIG, upstream outline and JST S05B-PASK-2 position copied from
  `hardware/toshiba_hvac_esp32.kicad_pcb`
- WROOM placed hard against the board edge opposite the JST connector and wiring loom, with a
  copper and plane keepout under the antenna section on all layers
- Ground pour both sides, stitched; thermal pad of the WROOM tied to GND

## Deliverables

New KiCad project at `hardware/integrated/` (the upstream carrier board stays untouched):

- `toshiba_hvac_esp32_integrated.kicad_pro/.kicad_sch/.kicad_pcb`
- `hardware/integrated/production/gerber.zip` (JLCPCB plot settings)
- `hardware/integrated/production/bom.csv` (JLCPCB columns: Comment, Designator, Footprint, LCSC)
- `hardware/integrated/production/positions.csv` (JLCPCB CPL: Designator, Mid X, Mid Y, Layer, Rotation)

Every BOM line carries an LCSC part number verified in stock for JLCPCB assembly at order time.

## Verification

- ERC and DRC clean under KiCad 9 (`kicad-cli`)
- J1 net mapping diffed against the upstream schematic (pin 1 TX / 2 GND / 3 +5V / 4 RX / 5 NC)
- Support circuitry cross-checked against Espressif's ESP32-DevKitC-V4 reference design
- Strapping pin audit: IO0/IO2/IO5/IO12/IO15 states at reset checked against the ESP32 datasheet
- Bench test before install: first flash over USB-C, OTA update, then UART loopback at the JST

## Out of scope

- Upstreaming (may be offered later as a PR, but nothing here is shaped for it)
- External antenna variant, spare GPIO breakout (explicitly declined)
- Firmware changes of any kind
