# Integrated ESP32 Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A KiCad 9 project and JLCPCB production files (gerbers, BOM, CPL) for a single-board ESP32-WROOM-32E replacement of the upstream DevKit carrier, per `docs/superpowers/specs/2026-08-08-integrated-esp32-board-design.md`.

**Architecture:** Author `.kicad_sch` and `.kicad_pcb` as KiCad 9 s-expression files in `hardware/integrated/`, reusing the upstream board outline, JST footprint and J1 net mapping. Verification is `kicad-cli sch erc`, `kicad-cli pcb drc`, and a Python script that asserts the netlist (J1 mapping, UART cross-connects, strapping pins) and schematic/PCB net parity.

**Tech Stack:** KiCad 9 (`kicad-cli` + standard symbol/footprint libraries), Python 3.11 for netlist assertions, JLCPCB PCBA (LCSC part numbers).

---

### Task 1: Tooling and reference extraction

**Files:**
- Create: `hardware/integrated/reference/upstream-outline.md` (extracted geometry notes)

- [ ] **Step 1: Confirm kicad-cli is installed and libraries are present**

Run: `kicad-cli version` and check `C:\Program Files\KiCad\9.0\share\kicad\symbols\RF_Module.kicad_sym` exists.
Expected: version 9.x; RF_Module library contains `ESP32-WROOM-32E`.

- [ ] **Step 2: Extract the upstream board geometry**

From `hardware/toshiba_hvac_esp32.kicad_pcb` (upstream, in this fork): parse `(gr_line`/`(gr_rect` on `Edge.Cuts` for the outline, and the `(footprint "CONN_S05B-PASK-2_JST"` block for J1's `(at x y rot)`. Record both in `hardware/integrated/reference/upstream-outline.md` together with the mounting hole positions if any.

- [ ] **Step 3: Extract the upstream J1 net mapping and confirm it matches the spec**

Grep the upstream `.kicad_sch` for the J1 symbol instance pins. Expected mapping: 1 ESP_TX_5V, 2 GND, 3 +5V, 4 ESP_RX_5V, 5 NC. If it differs, STOP and update the spec before continuing.

- [ ] **Step 4: Commit**

```bash
git add hardware/integrated/reference/
git commit -m "hw: extract upstream outline and J1 mapping for integrated board"
```

### Task 2: Verified BOM

**Files:**
- Create: `hardware/integrated/production/bom.csv`

- [ ] **Step 1: Verify every LCSC part number against JLCPCB/LCSC stock**

Target BOM (verify each number by searching jlcpcb.com/parts — numbers below are candidates, not gospel; replace any that are wrong or out of stock with an equivalent):

| Ref | Part | Package | LCSC candidate |
|---|---|---|---|
| U1 | ESP32-WROOM-32E-N4 | SMD module | C701342 |
| U2 | TXS0108EPW | TSSOP-20 | C17206 (upstream-proven) |
| U3 | AMS1117-3.3 | SOT-223 | C6186 |
| U4 | CP2102N-A02-GQFN24 | QFN-24 | C424093 |
| J1 | JST S05B-PASK-2(LF)(SN) | THT | C489718 (upstream-proven) |
| J2 | USB-C 16P HRO TYPE-C-31-M-12 | SMD | C165948 |
| D1, D2 | 1N5819W / B5819W Schottky 1A | SOD-123 | C8598 |
| D3 | LED green 0603 | 0603 | C72043 |
| Q1, Q2 | S8050 NPN | SOT-23 | C2146 |
| SW1, SW2 | TS-1187A tact switch | SMD | C318884 |
| R1–R5 | 10k | 0603 | C25804 (upstream-proven) |
| R6, R7 | 5.1k | 0603 | C23186 |
| R8 | 1k | 0603 | C21190 |
| R9 | 47.5k (VBUS divider hi) | 0603 | C25792 |
| R10 | 22.1k (VBUS divider lo) | 0603 | C31850 |
| C1–C6 | 100nF | 0603 | C14663 |
| C7, C8 | 1uF | 0603 | C15849 |
| C9, C10 | 10uF | 0805 | C15850 |
| C11, C12 | 22uF | 0805 | C45783 |

- [ ] **Step 2: Write `bom.csv` with JLCPCB columns**

Header: `Comment,Designator,Footprint,LCSC`. One row per value-group (JLCPCB format), designators comma-separated inside quotes.

- [ ] **Step 3: Commit**

```bash
git add hardware/integrated/production/bom.csv
git commit -m "hw: verified JLCPCB BOM for integrated board"
```

### Task 3: Schematic

**Files:**
- Create: `hardware/integrated/toshiba_hvac_esp32_integrated.kicad_pro`
- Create: `hardware/integrated/toshiba_hvac_esp32_integrated.kicad_sch`
- Create: `hardware/integrated/fp-lib-table` and `hardware/integrated/sym-lib-table` (pointing at `../footprints/` for the JST part)

- [ ] **Step 1: Author the schematic**

Wire by KiCad symbol **pin name**, never by remembered pin number. Net table (authoritative):

| Net | Connections |
|---|---|
| +5V_AC | J1.3, D1 anode |
| VBUS | J2 VBUS pins, D2 anode, R9 top |
| +5V | D1 cathode, D2 cathode, U2 VCCB, U3 VIN, C11, C5 |
| +3V3 | U3 VOUT, U1 3V3, U2 VCCA, U4 VDD+VREGIN, R1/R2/R3 tops, C4, C6–C10, C12 |
| GND | J1.2, J2 GND+shield, all IC GND/EP, C*, SW* bottoms, R10 bottom, D3 cathode-side resistor |
| ESP_TX_5V | J1.1, U2 B1 |
| ESP_RX_5V | J1.4, U2 B2 |
| AC_TX | U2 A1, U1 IO33 (firmware tx_pin) |
| AC_RX | U2 A2, U1 IO32 (firmware rx_pin) |
| SHIFT_OE | U2 OE, R3 bottom (R3 pulls up to +3V3) |
| USB_D+ / USB_D− | J2 DP1+DP2 / DN1+DN2, U4 D+ / D− |
| CC1 / CC2 | J2 CC1—R6—GND, J2 CC2—R7—GND |
| VBUS_SENSE | U4 VBUS, R9 bottom, R10 top |
| U0TXD | U1 TXD0/IO1, U4 RXD |
| U0RXD | U1 RXD0/IO3, U4 TXD |
| DTR / RTS | U4 DTR—R4—Q1 base; U4 RTS—R5—Q2 base; Q1 C→EN, Q1 E→RTS-side per DevKitC cross-couple; Q2 C→IO0, Q2 E→DTR-side (copy the DevKitC-V4 auto-reset exactly) |
| EN | U1 EN, R1 bottom, C7, SW1 |
| IO0 | U1 IO0, R2 bottom, SW2, Q2 collector |
| LED | U1 IO2—R8—D3 anode, D3 cathode—GND |

All unused WROOM IO pins: no-connect flags. IO12 left unconnected (floats low, correct 3.3V flash voltage).

- [ ] **Step 2: Run ERC**

Run: `kicad-cli sch erc hardware/integrated/toshiba_hvac_esp32_integrated.kicad_sch --exit-code-violations`
Expected: exit 0. Iterate until clean (power flags, no-connects).

- [ ] **Step 3: Netlist assertion script**

Export: `kicad-cli sch export netlist --format kicadxml -o netlist.xml <sch>`. Python script `hardware/integrated/verify_netlist.py` asserts: J1 pin→net mapping (1/2/3/4 = ESP_TX_5V/GND/+5V_AC/ESP_RX_5V), U2 A1↔IO33 and A2↔IO32 paths, U4 RXD on U0TXD net and TXD on U0RXD net (cross-connect), EN/IO0 pullups present.
Run: `python hardware/integrated/verify_netlist.py`
Expected: all assertions pass, exit 0.

- [ ] **Step 4: Commit**

```bash
git add hardware/integrated/
git commit -m "hw: integrated board schematic, ERC clean, netlist asserted"
```

### Task 4: PCB layout

**Files:**
- Create: `hardware/integrated/toshiba_hvac_esp32_integrated.kicad_pcb`

- [ ] **Step 1: Author the PCB with outline, footprints and nets**

Outline + J1 position copied from Task 1 extraction. Placement: J1 on the loom edge as upstream; U2 between J1 and U1; U1 (WROOM) hard against the opposite edge, antenna section outside a keepout zone spanning all copper layers; J2 (USB-C) on an accessible edge; U4 adjacent to J2; U3 + diodes near J1 power entry; SW1/SW2 and D3 on the face that is visible when installed. 2 layers, GND pour both sides.

- [ ] **Step 2: Verify schematic/PCB net parity**

Extend `verify_netlist.py` (add `--pcb` mode) to parse pad nets from the `.kicad_pcb` and diff against the schematic netlist: every schematic net present, no pad on a wrong net.
Run: `python hardware/integrated/verify_netlist.py --pcb`
Expected: parity confirmed, exit 0.

- [ ] **Step 3: Route**

Track plan: USB D+/D− as a short matched pair U4→J2; UART and control signals 0.25mm; +5V/+3V3 0.5mm min; pours stitched with vias. Antenna keepout kept clear of tracks on all layers.

- [ ] **Step 4: Run DRC**

Run: `kicad-cli pcb drc hardware/integrated/toshiba_hvac_esp32_integrated.kicad_pcb --exit-code-violations`
Expected: exit 0 (JLCPCB 2-layer standard rules: 0.127mm clearance min).

- [ ] **Step 5: Commit**

```bash
git add hardware/integrated/
git commit -m "hw: integrated board layout, DRC clean"
```

### Task 5: Production files

**Files:**
- Create: `hardware/integrated/production/gerber.zip`
- Create: `hardware/integrated/production/positions.csv`

- [ ] **Step 1: Plot gerbers + drill with JLCPCB settings**

```bash
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts -o production/gerber/ <pcb>
kicad-cli pcb export drill --format excellon --excellon-separate-th -u mm -o production/gerber/ <pcb>
```
Zip the directory as `production/gerber.zip`.

- [ ] **Step 2: Export CPL and convert to JLCPCB format**

```bash
kicad-cli pcb export pos --format csv --units mm --side both -o production/positions_raw.csv <pcb>
```
Convert headers to `Designator,Mid X,Mid Y,Layer,Rotation`. Note in the README that JLCPCB's viewer must be used to sanity-check rotations for U4 (QFN), U3 (SOT-223), J2 and U1 before ordering — JLC's zero-rotation convention differs from KiCad for some parts.

- [ ] **Step 3: Commit**

```bash
git add hardware/integrated/production/
git commit -m "hw: JLCPCB production files for integrated board"
```

### Task 6: Documentation and push

**Files:**
- Create: `hardware/integrated/README.md`

- [ ] **Step 1: Write README**

Contents: what the board is, one-paragraph diff from the upstream carrier, JLCPCB ordering steps (upload gerber.zip, PCBA with bom.csv + positions.csv, check rotations), first-flash instructions (`esphome run` over USB-C), the optional `status_led:` yaml snippet for GPIO2, and the bench-test checklist from the spec.

- [ ] **Step 2: Push branch**

```bash
git push -u origin integrated-esp32-board
```

## Self-review notes

- Spec coverage: AC interface (T3), power (T2/T3), USB+auto-reset (T3), support circuitry (T3), board rules (T4), deliverables (T5/T6), verification (T3 S2–3, T4 S2/S4, T6 bench checklist). Strapping audit is folded into the T3 netlist assertions (IO0/EN pullups, IO12 NC).
- LCSC candidates in T2 are explicitly marked for verification at execution, not trusted.
- Auto-reset transistor topology is specified as "copy DevKitC-V4 exactly" rather than from memory — the executor must pull the Espressif reference schematic during T3.
