#!/usr/bin/env python3
"""Generate toshiba_hvac_esp32_integrated.kicad_sch.

Authors the schematic programmatically: every symbol is extracted from the installed KiCad 10
libraries (extends-derived symbols are flattened against their parents), placed on a coarse grid,
and every pin gets either a global net label or a no_connect marker at its exact connection point.
The NETMAP below is the authoritative netlist from the implementation plan; verify_netlist.py
asserts the result independently.

Usage: python generate_sch.py
"""
import os
import re
import sys
import uuid

KICAD_SHARE = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\share\kicad")
SYMDIR = os.path.join(KICAD_SHARE, "symbols")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toshiba_hvac_esp32_integrated.kicad_sch")
PROJECT = "toshiba_hvac_esp32_integrated"
ROOT_UUID = "0e5f7a10-1111-4222-8333-abcdef012345"

# ── s-expression parser / serialiser ────────────────────────────────────────────────────────────

class Sym(str):
    """A bare (unquoted) atom, as opposed to a quoted string."""

def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            yield c
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            yield '"' + "".join(buf) + '"'
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            yield text[i:j]
            i = j

def parse(text):
    stack = [[]]
    for tok in tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(tok[1:-1])
        else:
            stack[-1].append(Sym(tok))
    return stack[0]

def ser(node, indent=0):
    if isinstance(node, list):
        parts = [ser(x, indent + 1) for x in node]
        joined = " ".join(parts)
        if len(joined) < 100 and "\n" not in joined:
            return "(" + joined + ")"
        pad = "\t" * (indent + 1)
        out = "(" + (parts[0] if parts else "")
        for p in parts[1:]:
            out += "\n" + pad + p
        return out + ")"
    if isinstance(node, Sym):
        return str(node)
    return '"' + str(node) + '"'

# ── symbol library access ───────────────────────────────────────────────────────────────────────

_libcache = {}

def load_lib(libname):
    if libname not in _libcache:
        with open(os.path.join(SYMDIR, libname + ".kicad_sym"), encoding="utf-8") as f:
            _libcache[libname] = parse(f.read())[0]
    return _libcache[libname]

def find_symbol(lib_node, name):
    for item in lib_node:
        if isinstance(item, list) and item and item[0] == "symbol" and item[1] == name:
            return item
    raise KeyError(name)

def get_prop(sym_node, prop):
    for item in sym_node:
        if isinstance(item, list) and item[:1] == [Sym("property")] and item[1] == prop:
            return item
    return None

def deepcopy(node):
    if isinstance(node, list):
        return [deepcopy(x) for x in node]
    return node

def resolve_symbol(libname, name):
    """Return a flattened copy of the symbol (extends resolved), still with its plain name."""
    lib = load_lib(libname)
    sym = find_symbol(lib, name)
    ext = next((i for i in sym if isinstance(i, list) and i[:1] == [Sym("extends")]), None)
    if ext is None:
        return deepcopy(sym)
    parent = resolve_symbol(libname, ext[1])
    # start from the parent, rename it (incl. sub-unit prefixes), then overlay child properties
    out = deepcopy(parent)
    oldname = parent[1]
    out[1] = name
    for item in out:
        if isinstance(item, list) and item[:1] == [Sym("symbol")]:
            item[1] = name + item[1][len(oldname):]
    child_props = [i for i in sym if isinstance(i, list) and i[:1] == [Sym("property")]]
    for cp in child_props:
        existing = get_prop(out, cp[1])
        if existing is not None:
            out[out.index(existing)] = deepcopy(cp)
        else:
            out.append(deepcopy(cp))
    return out

def symbol_pins(sym_node):
    """[(number, name, type, x, y, angle)] across all sub-units."""
    pins = []
    for unit in sym_node:
        if not (isinstance(unit, list) and unit[:1] == [Sym("symbol")]):
            continue
        for item in unit:
            if not (isinstance(item, list) and item[:1] == [Sym("pin")]):
                continue
            ptype = str(item[1])
            at = next(i for i in item if isinstance(i, list) and i[:1] == [Sym("at")])
            name = next(i for i in item if isinstance(i, list) and i[:1] == [Sym("name")])[1]
            number = next(i for i in item if isinstance(i, list) and i[:1] == [Sym("number")])[1]
            pins.append((str(number), str(name), ptype,
                         float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
    return pins

# ── design data ─────────────────────────────────────────────────────────────────────────────────

NC = "<NC>"

COMPONENTS = [
    # ref, lib, symbol, value, footprint, lcsc, (x, y)
    ("U1", "RF_Module", "ESP32-WROOM-32E", "ESP32-WROOM-32E-N8", "RF_Module:ESP32-WROOM-32E", "C701342", (63.5, 88.9)),
    ("U2", "Logic_LevelTranslator", "TXS0108EPW", "TXS0108EPW", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", "C17206", (127.0, 63.5)),
    ("U3", "Regulator_Linear", "AMS1117-3.3", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "C6186", (63.5, 172.72)),
    ("U4", "Interface_USB", "CP2102N-Axx-xQFN24", "CP2102N-A02-GQFN24", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", "C969151", (127.0, 139.7)),
    ("J1", "Connector_Generic", "Conn_01x05", "S05B-PASK-2LFSN", "CONN_S05B-PASK-2_JST:CONN_S05B-PASK-2_JST", "C489718", (177.8, 63.5)),
    ("J2", "Connector", "USB_C_Receptacle_USB2.0_16P", "TYPE-C-31-M-12", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "C165948", (177.8, 139.7)),
    ("Q1", "Transistor_BJT", "S8050", "S8050", "Package_TO_SOT_SMD:SOT-23", "C2146", (63.5, 203.2)),
    ("Q2", "Transistor_BJT", "S8050", "S8050", "Package_TO_SOT_SMD:SOT-23", "C2146", (88.9, 203.2)),
    ("D1", "Device", "D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", "C8598", (152.4, 203.2)),
    ("D2", "Device", "D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", "C8598", (152.4, 218.44)),
    ("D3", "Device", "LED", "LED_Red", "LED_SMD:LED_0603_1608Metric", "C2286", (152.4, 233.68)),
    ("SW1", "Switch", "SW_Push", "EN", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "C318884", (63.5, 226.06)),
    ("SW2", "Switch", "SW_Push", "BOOT", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "C318884", (88.9, 226.06)),
    ("R1", "Device", "R", "10k", "Resistor_SMD:R_0603_1608Metric", "C25804", (38.1, 254.0)),
    ("R2", "Device", "R", "10k", "Resistor_SMD:R_0603_1608Metric", "C25804", (55.88, 254.0)),
    ("R3", "Device", "R", "10k", "Resistor_SMD:R_0603_1608Metric", "C25804", (73.66, 254.0)),
    ("R4", "Device", "R", "10k", "Resistor_SMD:R_0603_1608Metric", "C25804", (91.44, 254.0)),
    ("R5", "Device", "R", "10k", "Resistor_SMD:R_0603_1608Metric", "C25804", (109.22, 254.0)),
    ("R6", "Device", "R", "5.1k", "Resistor_SMD:R_0603_1608Metric", "C23186", (127.0, 254.0)),
    ("R7", "Device", "R", "5.1k", "Resistor_SMD:R_0603_1608Metric", "C23186", (144.78, 254.0)),
    ("R8", "Device", "R", "1k", "Resistor_SMD:R_0603_1608Metric", "C21190", (162.56, 254.0)),
    ("R9", "Device", "R", "22k", "Resistor_SMD:R_0603_1608Metric", "C31850", (180.34, 254.0)),
    ("R10", "Device", "R", "47k", "Resistor_SMD:R_0603_1608Metric", "C25819", (198.12, 254.0)),
    ("C1", "Device", "C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", (38.1, 279.4)),
    ("C2", "Device", "C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", (53.34, 279.4)),
    ("C3", "Device", "C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", (68.58, 279.4)),
    ("C4", "Device", "C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", (83.82, 279.4)),
    ("C5", "Device", "C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", (99.06, 279.4)),
    ("C6", "Device", "C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", (114.3, 279.4)),
    ("C7", "Device", "C", "1uF", "Capacitor_SMD:C_0603_1608Metric", "C15849", (129.54, 279.4)),
    ("C8", "Device", "C", "1uF", "Capacitor_SMD:C_0603_1608Metric", "C15849", (144.78, 279.4)),
    ("C9", "Device", "C", "10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850", (160.02, 279.4)),
    ("C10", "Device", "C", "10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850", (175.26, 279.4)),
    ("C11", "Device", "C", "22uF", "Capacitor_SMD:C_0805_2012Metric", "C45783", (190.5, 279.4)),
    ("C12", "Device", "C", "22uF", "Capacitor_SMD:C_0805_2012Metric", "C45783", (205.74, 279.4)),
    ("PF1", "power", "PWR_FLAG", "PWR_FLAG", "", "", (38.1, 304.8)),
    ("PF2", "power", "PWR_FLAG", "PWR_FLAG", "", "", (63.5, 304.8)),
    ("PF3", "power", "PWR_FLAG", "PWR_FLAG", "", "", (88.9, 304.8)),
    ("PF4", "power", "PWR_FLAG", "PWR_FLAG", "", "", (114.3, 304.8)),
]

# (ref, pin_number) -> net, or NC. Stacked pins listed individually.
NETMAP = {
    # U1 ESP32-WROOM-32E; datasheet pin numbers, names asserted below
    ("U1", "[1,15,38,39]"): "GND",  # grouped GND pin (KiCad 9+ multi-number pin syntax)
    ("U1", "2"): "+3V3",
    ("U1", "3"): "EN",
    ("U1", "8"): "AC_RX",       # IO32 = firmware rx_pin
    ("U1", "9"): "AC_TX",       # IO33 = firmware tx_pin
    ("U1", "24"): "LED_CTRL",   # IO2
    ("U1", "25"): "IO0",
    ("U1", "34"): "U0RXD",      # RXD0/IO3
    ("U1", "35"): "U0TXD",      # TXD0/IO1
    # U2 TXS0108E
    ("U2", "1"): "AC_TX",       # A1 <- upstream: A1 pairs with B1=ESP_TX_5V
    ("U2", "3"): "AC_RX",       # A2
    ("U2", "20"): "ESP_TX_5V",  # B1
    ("U2", "18"): "ESP_RX_5V",  # B2
    ("U2", "10"): "SHIFT_OE",
    ("U2", "2"): "+3V3", ("U2", "19"): "+5V", ("U2", "11"): "GND",
    # U3 AMS1117-3.3 (pin numbers via name assertion: 1=GND 2=VO 3=VI, tab=2)
    ("U3", "1"): "GND", ("U3", "2"): "+3V3", ("U3", "3"): "+5V",
    # U4 CP2102N
    ("U4", "3"): "USB_DP", ("U4", "4"): "USB_DM",
    ("U4", "5"): "+3V3", ("U4", "6"): "+3V3", ("U4", "7"): "+3V3",
    ("U4", "8"): "VBUS_SENSE",
    ("U4", "20"): "U0TXD",      # CP RXD listens to ESP TXD0
    ("U4", "21"): "U0RXD",      # CP TXD drives ESP RXD0
    ("U4", "23"): "DTR", ("U4", "19"): "RTS",
    ("U4", "2"): "GND", ("U4", "25"): "GND",
    # J1 JST PASK (upstream-proven mapping)
    ("J1", "1"): "ESP_TX_5V", ("J1", "2"): "GND", ("J1", "3"): "+5V_AC", ("J1", "4"): "ESP_RX_5V",
    # J2 USB-C
    ("J2", "A4"): "VBUS", ("J2", "A9"): "VBUS", ("J2", "B4"): "VBUS", ("J2", "B9"): "VBUS",
    ("J2", "A5"): "CC1", ("J2", "B5"): "CC2",
    ("J2", "A6"): "USB_DP", ("J2", "B6"): "USB_DP",
    ("J2", "A7"): "USB_DM", ("J2", "B7"): "USB_DM",
    ("J2", "A1"): "GND", ("J2", "B1"): "GND", ("J2", "A12"): "GND", ("J2", "B12"): "GND",
    ("J2", "SH"): "GND",
    # auto-reset pair (DevKitC-V4 topology: Q1 C=EN B<-R4<-DTR E=RTS; Q2 C=IO0 B<-R5<-RTS E=DTR)
    ("Q1", "1"): "RTS", ("Q1", "2"): "Q1_B", ("Q1", "3"): "EN",
    ("Q2", "1"): "DTR", ("Q2", "2"): "Q2_B", ("Q2", "3"): "IO0",
    # diodes (Device:D_Schottky pin 1 = K, pin 2 = A)
    ("D1", "1"): "+5V", ("D1", "2"): "+5V_AC",
    ("D2", "1"): "+5V", ("D2", "2"): "VBUS",
    ("D3", "1"): "GND", ("D3", "2"): "LED_A",
    # switches
    ("SW1", "1"): "EN", ("SW1", "2"): "GND",
    ("SW2", "1"): "IO0", ("SW2", "2"): "GND",
    # resistors
    ("R1", "1"): "+3V3", ("R1", "2"): "EN",
    ("R2", "1"): "+3V3", ("R2", "2"): "IO0",
    ("R3", "1"): "+3V3", ("R3", "2"): "SHIFT_OE",
    ("R4", "1"): "DTR", ("R4", "2"): "Q1_B",
    ("R5", "1"): "RTS", ("R5", "2"): "Q2_B",
    ("R6", "1"): "CC1", ("R6", "2"): "GND",
    ("R7", "1"): "CC2", ("R7", "2"): "GND",
    ("R8", "1"): "LED_CTRL", ("R8", "2"): "LED_A",
    ("R9", "1"): "VBUS", ("R9", "2"): "VBUS_SENSE",
    ("R10", "1"): "VBUS_SENSE", ("R10", "2"): "GND",
    # decoupling / bulk
    ("C1", "1"): "+3V3", ("C1", "2"): "GND",
    ("C2", "1"): "+3V3", ("C2", "2"): "GND",
    ("C3", "1"): "+5V", ("C3", "2"): "GND",
    ("C4", "1"): "+3V3", ("C4", "2"): "GND",
    ("C5", "1"): "+3V3", ("C5", "2"): "GND",
    ("C6", "1"): "+3V3", ("C6", "2"): "GND",
    ("C7", "1"): "EN", ("C7", "2"): "GND",
    ("C8", "1"): "+3V3", ("C8", "2"): "GND",
    ("C9", "1"): "+3V3", ("C9", "2"): "GND",
    ("C10", "1"): "+3V3", ("C10", "2"): "GND",
    ("C11", "1"): "+5V", ("C11", "2"): "GND",
    ("C12", "1"): "+3V3", ("C12", "2"): "GND",
    # PWR_FLAGs onto the passive-driven nets
    ("PF1", "1"): "GND", ("PF2", "1"): "+5V", ("PF3", "1"): "+5V_AC", ("PF4", "1"): "VBUS",
}

# pin-name assertions guarding the number-keyed map above
NAME_ASSERTS = {
    ("U1", "2"): "VDD", ("U1", "3"): "EN", ("U1", "8"): "IO32", ("U1", "9"): "IO33",
    ("U1", "24"): "IO2", ("U1", "25"): "IO0", ("U1", "34"): "RXD0/IO3", ("U1", "35"): "TXD0/IO1",
    ("U2", "1"): "A1", ("U2", "3"): "A2", ("U2", "20"): "B1", ("U2", "18"): "B2", ("U2", "10"): "OE",
    ("U3", "1"): "GND", ("U3", "2"): "VO", ("U3", "3"): "VI",
    ("U4", "3"): "D+", ("U4", "4"): "D-", ("U4", "8"): "VBUS", ("U4", "20"): "RXD",
    ("U4", "21"): "TXD", ("U4", "23"): "~{DTR}", ("U4", "19"): "~{RTS}",
    ("Q1", "1"): "E", ("Q1", "2"): "B", ("Q1", "3"): "C",
    ("D1", "1"): "K", ("D1", "2"): "A", ("D3", "1"): "K", ("D3", "2"): "A",
}

# ── emit ────────────────────────────────────────────────────────────────────────────────────────

def u():
    return str(uuid.uuid4())

def q(s):
    return '"' + s + '"'

def main():
    lib_blocks = {}
    resolved = {}
    for ref, libname, symname, *_ in COMPONENTS:
        key = f"{libname}:{symname}"
        if key not in resolved:
            sym = resolve_symbol(libname, symname)
            resolved[key] = sym
            emb = deepcopy(sym)
            emb[1] = key
            lib_blocks[key] = emb

    body = []
    labels = []
    noconnects = set()
    label_points = set()
    used_map_keys = set()

    for ref, libname, symname, value, footprint, lcsc, (X, Y) in COMPONENTS:
        key = f"{libname}:{symname}"
        pins = symbol_pins(resolved[key])
        if not pins:
            sys.exit(f"FATAL: no pins found for {key}")

        pin_uuid_blocks = "".join(f'\n\t\t(pin "{n}"\n\t\t\t(uuid "{u()}")\n\t\t)' for n, *_ in pins)
        hide = "\n\t\t\t(hide yes)"
        eff = "\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)"
        lcsc_prop = ""
        if lcsc:
            lcsc_prop = (f'\n\t\t(property "LCSC" {q(lcsc)}\n\t\t\t(at {X} {Y} 0){hide}{eff}\n\t\t)')
        body.append(f'''\t(symbol
\t\t(lib_id {q(key)})
\t\t(at {X} {Y} 0)
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom {"no" if ref.startswith("PF") else "yes"})
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{u()}")
\t\t(property "Reference" {q(ref)}
\t\t\t(at {X} {Y - 2.54} 0){eff}
\t\t)
\t\t(property "Value" {q(value)}
\t\t\t(at {X} {Y + 2.54} 0){eff}
\t\t)
\t\t(property "Footprint" {q(footprint)}
\t\t\t(at {X} {Y} 0){hide}{eff}
\t\t)
\t\t(property "Datasheet" ""
\t\t\t(at {X} {Y} 0){hide}{eff}
\t\t){lcsc_prop}{pin_uuid_blocks}
\t\t(instances
\t\t\t(project {q(PROJECT)}
\t\t\t\t(path "/{ROOT_UUID}"
\t\t\t\t\t(reference {q(ref)})
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)''')

        for number, name, ptype, px, py, pang in pins:
            wx = round(X + px, 4)
            wy = round(Y - py, 4)
            mkey = (ref, number)
            want_name = NAME_ASSERTS.get(mkey)
            if want_name is not None and name != want_name:
                sys.exit(f"FATAL: {ref} pin {number} is named {name!r}, expected {want_name!r}")
            net = NETMAP.get(mkey)
            if net is None:
                if ptype == "no_connect" or True:
                    noconnects.add((wx, wy))
                continue
            used_map_keys.add(mkey)
            if net == NC:
                noconnects.add((wx, wy))
                continue
            if (wx, wy) in label_points:
                continue  # stacked pin, already labelled
            label_points.add((wx, wy))
            world_dir = (360 - int(pang)) % 360
            rot = (world_dir + 180) % 360
            justify = "left" if rot in (0, 90) else "right"
            labels.append(f'''\t(global_label {q(net)}
\t\t(shape bidirectional)
\t\t(at {wx} {wy} {rot})
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify {justify})
\t\t)
\t\t(uuid "{u()}")
\t)''')

    unused = set(NETMAP) - used_map_keys
    if unused:
        sys.exit(f"FATAL: NETMAP entries never matched a pin: {sorted(unused)}")

    nc_blocks = [f'\t(no_connect\n\t\t(at {x} {y})\n\t\t(uuid "{u()}")\n\t)'
                 for x, y in sorted(noconnects - label_points)]

    libs = "\n".join("\t" + ser(node, 1) for node in
                     [lib_blocks[k] for k in sorted(lib_blocks)])

    out = f'''(kicad_sch
\t(version 20250610)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "{ROOT_UUID}")
\t(paper "A2")
\t(title_block
\t\t(title "Toshiba HVAC controller, integrated ESP32")
\t\t(date "2026-08-08")
\t\t(rev "1")
\t)
\t(lib_symbols
{libs}
\t)
{chr(10).join(labels)}
{chr(10).join(nc_blocks)}
{chr(10).join(body)}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
'''
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"wrote {OUT}: {len(COMPONENTS)} symbols, {len(labels)} labels, {len(nc_blocks)} no-connects")

if __name__ == "__main__":
    main()
