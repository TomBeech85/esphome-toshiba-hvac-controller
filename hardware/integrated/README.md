# Integrated ESP32 Toshiba HVAC Controller

A single-board replacement for the upstream carrier board + ESP32 DevKit stack. The
ESP32-WROOM-32E is soldered directly to the PCB along with everything the DevKit used to
provide, so the board is a fraction of the height — it fits the Haori units that could not
take the socketed DevKit — and is assembled entirely by JLCPCB.

Same outline and JST connector position as the upstream carrier, so the documented
installation fit holds. Firmware is unchanged (`board: esp32dev`, AC UART on GPIO33/32);
the only optional yaml addition is the status LED:

```yaml
status_led:
  pin: GPIO2
```

## What's on it

- **ESP32-WROOM-32E-N8** with EN/IO0 support circuitry, EN + BOOT tact switches (back side)
- **USB-C + CP2102N** with the DevKitC auto-reset circuit — plug in and `esphome run`,
  first flash only, OTA afterwards
- **TXS0108E** level shifter to the indoor unit's 5V UART (identical wiring to upstream)
- **Diode-OR'd power**: the unit's 5V and USB VBUS both feed an AMS1117-3.3 — bench-flash
  on USB and install without touching anything, no backfeed into the AC
- **Status LED** on GPIO2 (front, red)

## Ordering from JLCPCB

1. Upload `production/gerber.zip`. 2 layers, 1.6mm, any colour; leave defaults.
2. Enable **PCB Assembly**, assembled **both sides** (switches and passives are on the back).
3. Upload `production/bom.csv` and `production/positions.csv`.
4. In the part-placement review, sanity-check the rotations of **U1** (module), **U3**
   (SOT-223), **U4** (QFN) and **J2** (USB-C) against the renders — JLCPCB's zero-rotation
   convention differs from KiCad for some parts and their reviewer tool shows it clearly.
5. J1 (the JST S05B-PASK-2) is through-hole: select "economic" assembly with THT if offered,
   or solder it by hand — it is the only through-hole part.

## Verification status

- ERC: clean. DRC: 0 errors, 0 unconnected (KiCad 10, JLCPCB 2-layer rules).
- `verify_netlist.py` asserts the field-proven J1 pinout (1 TX / 2 GND / 3 +5V / 4 RX),
  shifter channel pairing, UART cross-connects, auto-reset topology and strapping pins;
  `--pcb` additionally diffs every PCB pad net against the schematic.
- Not yet bench-tested. First-article checklist: continuity 5V/3V3/GND, first flash over
  USB-C, OTA update, UART loopback at the JST before connecting to an indoor unit.

## Regenerating

The schematic and board are generated programmatically (KiCad 10):

```
python generate_sch.py                     # schematic from the pin/net map
<KiCad>/bin/python.exe build_pcb.py        # board: placement + routes.py + zones
python verify_netlist.py --pcb             # assertions + schematic/PCB parity
```
