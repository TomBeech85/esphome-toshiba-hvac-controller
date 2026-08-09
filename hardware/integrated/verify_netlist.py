#!/usr/bin/env python3
"""Assert the safety-critical connectivity of the integrated board.

Modes:
  python verify_netlist.py          -> checks netlist.xml (schematic truth)
  python verify_netlist.py --pcb    -> additionally diffs pad nets in the .kicad_pcb
                                       against the schematic netlist

Exit 0 on success, 1 with a failure list otherwise.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
NETLIST = os.path.join(HERE, "netlist.xml")
PCB = os.path.join(HERE, "toshiba_hvac_esp32_integrated.kicad_pcb")

failures = []

def check(cond, msg):
    if cond:
        print(f"  ok: {msg}")
    else:
        failures.append(msg)
        print(f"FAIL: {msg}")

def load_nets():
    """{netname: set((ref, pin))}, with the WROOM grouped GND pin expanded."""
    nets = {}
    for net in ET.parse(NETLIST).getroot().iter("net"):
        nodes = set()
        for n in net.findall("node"):
            ref, pin = n.get("ref"), n.get("pin")
            m = re.fullmatch(r"\[([\d,]+)\]", pin or "")
            if m:
                nodes.update((ref, p) for p in m.group(1).split(","))
            else:
                nodes.add((ref, pin))
        nets[net.get("name")] = nodes
    return nets

def net_of(nets, ref, pin):
    for name, nodes in nets.items():
        if (ref, pin) in nodes:
            return None if name.startswith("unconnected-") else name
    return None

def main():
    nets = load_nets()

    print("== J1 (JST PASK) mapping: the field-proven upstream pinout ==")
    check(net_of(nets, "J1", "1") == "ESP_TX_5V", "J1.1 = ESP_TX_5V")
    check(net_of(nets, "J1", "2") == "GND", "J1.2 = GND")
    check(net_of(nets, "J1", "3") == "+5V_AC", "J1.3 = +5V_AC (indoor unit 5V)")
    check(net_of(nets, "J1", "4") == "ESP_RX_5V", "J1.4 = ESP_RX_5V")
    check(net_of(nets, "J1", "5") is None, "J1.5 = no connect")

    print("== Level shifter pairing (A-side pin must pair with its own B-side channel) ==")
    check(net_of(nets, "U2", "20") == "ESP_TX_5V", "U2.B1 = ESP_TX_5V")
    check(net_of(nets, "U2", "18") == "ESP_RX_5V", "U2.B2 = ESP_RX_5V")
    check(net_of(nets, "U2", "1") == net_of(nets, "U1", "9") == "AC_TX",
          "U2.A1 <-> U1.IO33 (firmware tx_pin GPIO33)")
    check(net_of(nets, "U2", "3") == net_of(nets, "U1", "8") == "AC_RX",
          "U2.A2 <-> U1.IO32 (firmware rx_pin GPIO32)")
    check(net_of(nets, "U2", "2") == "+3V3" and net_of(nets, "U2", "19") == "+5V",
          "U2 VCCA=3V3, VCCB=5V (VCCA <= VCCB per TXS0108E datasheet)")
    check(("R3", "2") in nets.get("SHIFT_OE", set()) and ("R3", "1") in nets.get("+3V3", set()),
          "OE pulled up to 3V3 via R3 (upstream behaviour)")

    print("== Power path ==")
    check(net_of(nets, "D1", "2") == "+5V_AC" and net_of(nets, "D1", "1") == "+5V",
          "D1: anode on AC 5V, cathode on +5V rail (no backfeed into the unit)")
    check(net_of(nets, "D2", "2") == "VBUS" and net_of(nets, "D2", "1") == "+5V",
          "D2: anode on USB VBUS, cathode on +5V rail")
    check(net_of(nets, "U3", "3") == "+5V" and net_of(nets, "U3", "2") == "+3V3",
          "AMS1117: VI on +5V, VO on +3V3")
    check(net_of(nets, "U1", "2") == "+3V3", "WROOM VDD on +3V3")

    print("== USB / programming ==")
    j2_dp = {p for r, p in nets.get("USB_DP", set()) if r == "J2"}
    check(j2_dp == {"A6", "B6"} and ("U4", "3") in nets["USB_DP"],
          "USB D+ : J2 A6+B6 <-> CP2102N D+")
    j2_dm = {p for r, p in nets.get("USB_DM", set()) if r == "J2"}
    check(j2_dm == {"A7", "B7"} and ("U4", "4") in nets["USB_DM"],
          "USB D- : J2 A7+B7 <-> CP2102N D-")
    check(("R6", "1") in nets.get("CC1", set()) and ("R7", "1") in nets.get("CC2", set()),
          "CC1/CC2 have 5.1k pulldowns (USB-C sink)")
    check(net_of(nets, "U4", "20") == net_of(nets, "U1", "35") == "U0TXD",
          "UART cross-connect: CP RXD <- ESP TXD0")
    check(net_of(nets, "U4", "21") == net_of(nets, "U1", "34") == "U0RXD",
          "UART cross-connect: CP TXD -> ESP RXD0")
    check(net_of(nets, "U4", "8") == "VBUS_SENSE"
          and ("R9", "2") in nets["VBUS_SENSE"] and ("R10", "1") in nets["VBUS_SENSE"],
          "CP2102N VBUS behind the R9/R10 divider")

    print("== Auto-reset (DevKitC-V4 topology) ==")
    check(net_of(nets, "Q1", "3") == "EN" and net_of(nets, "Q1", "1") == "RTS"
          and net_of(nets, "Q1", "2") == "Q1_B" and ("R4", "2") in nets["Q1_B"]
          and net_of(nets, "R4", "1") == "DTR",
          "Q1: C=EN, E=RTS, B<-10k<-DTR")
    check(net_of(nets, "Q2", "3") == "IO0" and net_of(nets, "Q2", "1") == "DTR"
          and net_of(nets, "Q2", "2") == "Q2_B" and ("R5", "2") in nets["Q2_B"]
          and net_of(nets, "R5", "1") == "RTS",
          "Q2: C=IO0, E=DTR, B<-10k<-RTS")
    check(net_of(nets, "U4", "23") == "DTR" and net_of(nets, "U4", "19") == "RTS",
          "CP2102N drives DTR/RTS")

    print("== Strapping / support ==")
    en = nets.get("EN", set())
    check(("R1", "2") in en and ("C7", "1") in en and ("SW1", "1") in en and ("U1", "3") in en,
          "EN: 10k pullup + 1uF RC + button")
    io0 = nets.get("IO0", set())
    check(("R2", "2") in io0 and ("SW2", "1") in io0 and ("U1", "25") in io0,
          "IO0: 10k pullup + BOOT button")
    check(net_of(nets, "U1", "14") is None, "IO12 (MTDI) unconnected -> 3.3V flash")
    check(net_of(nets, "U1", "24") == "LED_CTRL" and ("R8", "1") in nets["LED_CTRL"]
          and net_of(nets, "D3", "2") == "LED_A" and net_of(nets, "D3", "1") == "GND",
          "Status LED: IO2 -> 1k -> LED -> GND")
    gnd = nets.get("GND", set())
    for p in ("1", "15", "38", "39"):
        check(("U1", p) in gnd, f"WROOM pad {p} grounded")

    if "--pcb" in sys.argv:
        print("== PCB pad-net parity ==")
        txt = open(PCB, encoding="utf-8").read()
        pads = []
        i = 0
        while True:
            i = txt.find('(footprint', i)
            if i < 0:
                break
            depth, j = 0, i
            while True:
                if txt[j] == '(':
                    depth += 1
                elif txt[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            block = txt[i:j + 1]
            i = j + 1
            refm = re.search(r'\(property "Reference"\s+"([^"]+)"', block)
            if not refm:
                continue
            ref = refm.group(1)
            k = 0
            while True:
                k = block.find('(pad ', k)
                if k < 0:
                    break
                d2, m2 = 0, k
                while True:
                    if block[m2] == '(':
                        d2 += 1
                    elif block[m2] == ')':
                        d2 -= 1
                        if d2 == 0:
                            break
                    m2 += 1
                pb = block[k:m2 + 1]
                k = m2 + 1
                num = re.match(r'\(pad\s+"([^"]*)"', pb).group(1)
                netm = re.search(r'\(net\s+(?:\d+\s+)?"([^"]+)"\)', pb)
                if netm:
                    pads.append((ref, num, netm.group(1)))
        pcb_map = {}
        for ref, pin, net in pads:
            pcb_map.setdefault((ref, pin), set()).add(net)
        mismatches = 0
        for name, nodes in nets.items():
            if name.startswith("unconnected-"):
                continue
            for ref, pin in nodes:
                if ref.startswith("PF"):
                    continue  # PWR_FLAG symbols have no footprint by design
                got = pcb_map.get((ref, pin))
                if got is None:
                    failures.append(f"PCB missing pad {ref}.{pin} (schematic net {name})")
                    mismatches += 1
                elif name not in got:
                    failures.append(f"PCB pad {ref}.{pin}: net {got} != schematic {name}")
                    mismatches += 1
        print(f"  checked {sum(len(n) for n in nets.values())} schematic nodes "
              f"against {len(pads)} PCB pads, {mismatches} mismatches")

    print()
    if failures:
        print(f"{len(failures)} FAILURES")
        sys.exit(1)
    print("all assertions passed")

if __name__ == "__main__":
    main()
