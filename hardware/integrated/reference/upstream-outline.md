# Upstream geometry reference (extracted from hardware/toshiba_hvac_esp32.kicad_pcb)

## Board outline (Edge.Cuts)

Rectangle, corners (35.052, 32.512) to (64.008, 82.804) in KiCad page coordinates.
Size: 28.956 mm x 50.292 mm. No mounting holes on the board outline itself; the JST footprint
carries two np_thru_hole retention holes.

Orientation: the JST connector sits near the BOTTOM edge (y = 82.804); the DevKit pin sockets run
along the left (x = 36.826) and right (x = 62.230) edges from y = 34.704 downward. The TOP edge
(y = 32.512) is free of connectors, so the integrated board puts the WROOM antenna there.

## J1 (JST S05B-PASK-2) placement

- Footprint `CONN_S05B-PASK-2_JST:CONN_S05B-PASK-2_JST`, front copper, at (45.847051, 74.353301),
  rotation 0.
- Pad 1 at footprint origin, pads on 2.0 mm pitch running +x; two 1.0922 mm np_thru_hole
  retention holes at (-1.5, +2.1) and (+9.5, +2.1) relative to origin.

## J1 net mapping (verified against upstream PCB pad nets AND schematic)

| Pad | Net |
|---|---|
| 1 | ESP_TX_5V |
| 2 | GND |
| 3 | +5V (from indoor unit) |
| 4 | ESP_RX_5V |
| 5 | no connect |

Matches the spec table exactly. The integrated board reuses this footprint, position and mapping
verbatim.

## Upstream level shifter wiring (for parity)

TXS0108EPW: B1 = ESP_TX_5V, B2 = ESP_RX_5V (5 V side); A1 = TXD, A2 = RXD (3.3 V side);
OE pulled to VCCA through 10k (R4). VCCB = +5V, VCCA = +3.3V, 100nF on each.
Firmware (esphome/template_v3.yaml): tx_pin GPIO33, rx_pin GPIO32.
