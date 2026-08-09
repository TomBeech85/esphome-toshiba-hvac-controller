#!/usr/bin/env python3
"""Build toshiba_hvac_esp32_integrated.kicad_pcb with the pcbnew API.

Run with KiCad's bundled python:
  %LOCALAPPDATA%/Programs/KiCad/10.0/bin/python.exe build_pcb.py

Reads netlist.xml (exported from the ERC-clean schematic) for pad->net truth, so the PCB can
never drift from the schematic without verify_netlist.py --pcb noticing.
"""
import os
import re
import xml.etree.ElementTree as ET

import pcbnew
from pcbnew import VECTOR2I, VECTOR2I_MM as MM, EDA_ANGLE

HERE = os.path.dirname(os.path.abspath(__file__))
SHARE = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\share\kicad\footprints")
JST_LIB = os.path.join(HERE, "..", "footprints", "Conn_JST_S05B-PASK-2", "footprints.pretty")
OUT = os.path.join(HERE, "toshiba_hvac_esp32_integrated.kicad_pcb")

# board outline, from the upstream carrier (reference/upstream-outline.md)
X0, Y0, X1, Y1 = 35.052, 32.512, 64.008, 82.804

# ── pad -> net map from the schematic netlist ───────────────────────────────────────────────────

def load_netmap():
    netmap = {}
    netnames = set()
    for net in ET.parse(os.path.join(HERE, "netlist.xml")).getroot().iter("net"):
        name = net.get("name")
        if name.startswith("unconnected-"):
            continue
        netnames.add(name)
        for n in net.findall("node"):
            ref, pin = n.get("ref"), n.get("pin")
            m = re.fullmatch(r"\[([\d,]+)\]", pin or "")
            for p in (m.group(1).split(",") if m else [pin]):
                netmap[(ref, p)] = name
    return netmap, netnames

# ── placement table ─────────────────────────────────────────────────────────────────────────────
# ref: (lib, footprint, x, y, rot_deg, side)  -- side "F" or "B"
PLACE = {
    "U1":  ("RF_Module", "ESP32-WROOM-32E", 49.530, 45.900, 0, "F"),
    "U2":  ("Package_SO", "TSSOP-20_4.4x6.5mm_P0.65mm", 41.500, 62.900, 0, "F"),
    "U3":  ("Package_TO_SOT_SMD", "SOT-223-3_TabPin2", 60.100, 75.600, 90, "F"),
    "U4":  ("Package_DFN_QFN", "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", 50.000, 64.500, 0, "F"),
    "J1":  (JST_LIB, "CONN_S05B-PASK-2_JST", 45.847, 74.353, 0, "F"),
    "J2":  ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", 58.900, 64.700, 270, "F"),
    "D1":  ("Diode_SMD", "D_SOD-123", 37.600, 73.500, 90, "F"),   # AC 5V -> +5V
    "D2":  ("Diode_SMD", "D_SOD-123", 40.600, 73.500, 90, "F"),   # VBUS -> +5V
    "D3":  ("LED_SMD", "LED_0603_1608Metric", 40.500, 68.500, 90, "F"),
    # back side: switches, auto-reset pair, passives
    "SW1": ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", 39.500, 44.500, 0, "B"),
    "SW2": ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", 39.500, 51.500, 0, "B"),
    "Q1":  ("Package_TO_SOT_SMD", "SOT-23", 47.500, 55.000, 270, "B"),
    "Q2":  ("Package_TO_SOT_SMD", "SOT-23", 52.750, 59.200, 180, "B"),
    "R4":  ("Resistor_SMD", "R_0603_1608Metric", 48.600, 58.700, 90, "B"),    # DTR -> Q1_B
    "R5":  ("Resistor_SMD", "R_0603_1608Metric", 52.400, 61.750, 0, "B"),    # RTS -> Q2_B
    "R1":  ("Resistor_SMD", "R_0603_1608Metric", 45.300, 43.500, 270, "B"),   # EN pullup
    "C7":  ("Capacitor_SMD", "C_0603_1608Metric", 47.000, 43.200, 90, "B"),  # EN 1u
    "C1":  ("Capacitor_SMD", "C_0603_1608Metric", 44.300, 52.200, 90, "B"),  # WROOM 100n
    "C9":  ("Capacitor_SMD", "C_0805_2012Metric", 44.300, 48.600, 90, "B"),  # WROOM 10u
    "R2":  ("Resistor_SMD", "R_0603_1608Metric", 56.500, 55.500, 270, "B"),   # IO0 pullup
    "R3":  ("Resistor_SMD", "R_0603_1608Metric", 38.500, 59.000, 0, "B"),    # OE pullup
    "C2":  ("Capacitor_SMD", "C_0603_1608Metric", 38.500, 57.200, 0, "B"),   # VCCA 100n
    "C3":  ("Capacitor_SMD", "C_0603_1608Metric", 42.500, 63.000, 270, "B"),   # VCCB 100n
    "C4":  ("Capacitor_SMD", "C_0603_1608Metric", 44.200, 59.700, 90, "B"),   # U4 VDD 100n
    "C8":  ("Capacitor_SMD", "C_0603_1608Metric", 44.200, 63.400, 90, "B"),   # U4 1u
    "C5":  ("Capacitor_SMD", "C_0603_1608Metric", 44.000, 55.600, 90, "B"),   # U4 VREGIN 100n
    "C10": ("Capacitor_SMD", "C_0805_2012Metric", 60.600, 79.800, 270, "B"),   # U4 10u
    "R9":  ("Resistor_SMD", "R_0603_1608Metric", 48.600, 69.300, 0, "B"),    # VBUS div hi
    "R10": ("Resistor_SMD", "R_0603_1608Metric", 48.600, 71.050, 180, "B"),    # VBUS div lo
    "R6":  ("Resistor_SMD", "R_0603_1608Metric", 59.900, 71.700, 90, "B"),   # CC1
    "R7":  ("Resistor_SMD", "R_0603_1608Metric", 58.200, 71.700, 90, "B"),   # CC2
    "R8":  ("Resistor_SMD", "R_0603_1608Metric", 40.500, 68.500, 90, "B"),   # LED (mirrors D3)
    "C6":  ("Capacitor_SMD", "C_0603_1608Metric", 60.900, 75.500, 0, "B"),  # +3V3 100n
    "C12": ("Capacitor_SMD", "C_0805_2012Metric", 62.600, 78.000, 90, "B"),  # +3V3 22u
    "C11": ("Capacitor_SMD", "C_0805_2012Metric", 44.900, 70.300, 90, "B"),  # +5V 22u
}
BACK_HIDDEN_REFS = {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10",
                    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12",
                    "Q1", "Q2"}

VALUES = {
    "U1": "ESP32-WROOM-32E-N8", "U2": "TXS0108EPW", "U3": "AMS1117-3.3",
    "U4": "CP2102N-A02-GQFN24", "J1": "S05B-PASK-2LFSN", "J2": "TYPE-C-31-M-12",
    "Q1": "S8050", "Q2": "S8050", "D1": "B5819W", "D2": "B5819W", "D3": "LED_Red",
    "SW1": "EN", "SW2": "BOOT",
    "R1": "10k", "R2": "10k", "R3": "10k", "R4": "10k", "R5": "10k",
    "R6": "5.1k", "R7": "5.1k", "R8": "1k", "R9": "22k", "R10": "47k",
    "C1": "100nF", "C2": "100nF", "C3": "100nF", "C4": "100nF", "C5": "100nF", "C6": "100nF",
    "C7": "1uF", "C8": "1uF", "C9": "10uF", "C10": "10uF", "C11": "22uF", "C12": "22uF",
}

def build():
    board = pcbnew.CreateEmptyBoard()

    ds = board.GetDesignSettings()
    # JLCPCB 2-layer capabilities: these two defaults are stricter than the fab needs.
    # Edge clearance 0.1mm lets the USB-C sit flush with the routed edge; min through drill
    # 0.2mm admits the WROOM EP's 0.2mm thermal vias (JLC drills down to 0.15mm).
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.1)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.2)
    # JLCPCB 2-layer: 5mil (0.127mm) clearance, NPTH-to-copper 0.2mm
    ds.m_MinClearance = pcbnew.FromMM(0.127)
    ds.m_HoleClearance = pcbnew.FromMM(0.2)
    ds.m_TrackMinWidth = pcbnew.FromMM(0.15)
    ds.m_ViasMinSize = pcbnew.FromMM(0.4)
    ds.m_ViasMinAnnularWidth = pcbnew.FromMM(0.07)
    # SaveBoard regenerates the project file, so pin the default netclass clearance here
    try:
        ds.m_NetSettings.GetDefaultNetclass().SetClearance(pcbnew.FromMM(0.127))
    except AttributeError:
        ds.GetNetClasses().GetDefault().SetClearance(pcbnew.FromMM(0.127))

    netmap, netnames = load_netmap()
    nets = {}
    for name in sorted(netnames):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    # outline
    for (sx, sy, ex, ey) in [(X0, Y0, X1, Y0), (X1, Y0, X1, Y1), (X1, Y1, X0, Y1), (X0, Y1, X0, Y0)]:
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(MM(sx, sy))
        seg.SetEnd(MM(ex, ey))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)

    # footprints
    unassigned = []
    for ref, (lib, name, x, y, rot, side) in PLACE.items():
        libpath = lib if os.path.isabs(lib) else os.path.join(SHARE, lib + ".pretty")
        fp = pcbnew.FootprintLoad(libpath, name)
        if fp is None:
            raise RuntimeError(f"footprint {lib}:{name} not found")
        fp.SetReference(ref)
        fp.SetValue(VALUES.get(ref, ""))
        if ref == "U1":
            # The library footprint's courtyard encodes Espressif's ideal RF keepout (+-24mm),
            # unsatisfiable on this 29mm-wide outline (the upstream DevKit carrier violates it
            # identically and is field-proven). Trim it to the module body; the antenna copper
            # keepout below is the guarantee we do keep.
            for item in list(fp.GraphicalItems()):
                if item.GetLayer() == pcbnew.F_CrtYd:
                    fp.Remove(item)
            rect = pcbnew.PCB_SHAPE(fp)
            rect.SetShape(pcbnew.SHAPE_T_RECTANGLE)
            rect.SetStart(MM(-9.3, -13.05))
            rect.SetEnd(MM(9.3, 13.3))
            rect.SetLayer(pcbnew.F_CrtYd)
            rect.SetWidth(pcbnew.FromMM(0.05))
            rect.SetFilled(False)
            fp.Add(rect)
        if ref in BACK_HIDDEN_REFS:
            fp.Reference().SetVisible(False)
        board.Add(fp)
        if side == "B":
            try:
                fp.Flip(MM(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            except AttributeError:
                fp.Flip(MM(x, y), True)
        fp.SetPosition(MM(x, y))
        fp.SetOrientation(EDA_ANGLE(rot, pcbnew.DEGREES_T))
        for pad in fp.Pads():
            key = (ref, str(pad.GetNumber()))
            net = netmap.get(key)
            if net:
                pad.SetNet(nets[net])
            elif pad.GetNumber():
                unassigned.append(key)

    print(f"pads without nets (NC): {len(unassigned)}")

    # tracks and vias from routes.py
    import routes
    layer_of = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
    for net, layer, width, pts in routes.TRACKS:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(MM(x1, y1))
            t.SetEnd(MM(x2, y2))
            t.SetWidth(pcbnew.FromMM(width))
            t.SetLayer(layer_of[layer])
            t.SetNet(nets[net])
            board.Add(t)
    for net, x, y, od, drill in routes.VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(MM(x, y))
        v.SetWidth(pcbnew.FromMM(od))
        v.SetDrill(pcbnew.FromMM(drill))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[net])
        board.Add(v)
    print(f"routed {sum(len(p)-1 for _,_,_,p in routes.TRACKS)} segments, {len(routes.VIAS)} vias")

    # antenna keepout: all-layer, no copper/zone fill, spanning the module antenna band
    ant = pcbnew.ZONE(board)
    ant.SetIsRuleArea(True)
    ant.SetDoNotAllowZoneFills(True)
    ant.SetDoNotAllowTracks(True)
    ant.SetDoNotAllowVias(True)
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    ant.SetLayerSet(ls)
    pts = [(40.4, Y0), (58.7, Y0), (58.7, 39.8), (40.4, 39.8)]
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for px, py in pts:
        chain.Append(pcbnew.FromMM(px), pcbnew.FromMM(py))
    chain.SetClosed(True)
    ant.Outline().AddOutline(chain)
    board.Add(ant)

    # GND pours, both layers
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(nets["GND"])
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for px, py in [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]:
            chain.Append(pcbnew.FromMM(px), pcbnew.FromMM(py))
        chain.SetClosed(True)
        z.Outline().AddOutline(chain)
        z.SetLocalClearance(pcbnew.FromMM(0.2))
        z.SetMinThickness(pcbnew.FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(pcbnew.FromMM(0.3))
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
        board.Add(z)

    board.SetFileName(OUT)
    pcbnew.SaveBoard(OUT, board)
    print(f"saved {OUT}")

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    print("zones filled and saved")

if __name__ == "__main__":
    build()
