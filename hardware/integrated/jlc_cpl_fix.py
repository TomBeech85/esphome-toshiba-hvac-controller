"""Regenerate production/positions.csv with JLCPCB-convention corrections.

JLCPCB's pick-and-place interprets the CPL against ITS part library's zero-orientation and
centroid, which differ from KiCad's footprint conventions for some parts. Corrections below
were derived from JLCPCB's placement-reviewer renders (2026-08-09):

- U1  ESP32-WROOM-32E: JLC's library part has a different zero-orientation from the KiCad
      footprint, so their preview drew the antenna pointing west instead of north. +270.
- J1  JST S05B-PASK: our footprint origin is pad 1, but JLC's CPL wants the part CENTROID, so
      their preview drew the connector ~4 mm west, on top of D1/D2. Mid X/Y moved to the body centre.
- J2  USB-C: NOT corrected here. Their preview was faithful - the board itself had the connector
      backwards, which is fixed in the layout (see build_pcb.py's orientation guard).

Run with KiCad's python OR system python (only needs kicad-cli on PATH_KICAD below).
After re-uploading positions.csv, re-check in the JLC reviewer:
  * U1 antenna over the bare top band (if it is 180 deg out, flip ROT_FIX["U1"] to 90),
  * J2 opening flush with the right edge - should now be right with no correction,
  * J1 pins on the through-holes with the body toward the bottom edge,
  * U4's pin-1 dot against the silkscreen arrow (square part, can't be auto-checked),
  * BOTTOM side: Q1/Q2 (SOT-23) leads matching their silk outlines - a 180° error there
    breaks the auto-reset transistors.
"""
import csv
import io
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_CLI = os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe")
PCB = os.path.join(HERE, "toshiba_hvac_esp32_integrated.kicad_pcb")
RAW = os.path.join(HERE, "production", "positions_raw.csv")
OUT = os.path.join(HERE, "production", "positions.csv")

# ref -> degrees to ADD to KiCad's reported rotation (mod 360)
ROT_FIX = {
    "U1": 270,   # antenna west -> north
}
# ref -> (dx, dy) shift in CPL axes, mm. Expressed as a DELTA, not an absolute coordinate: the
# CPL's Y axis is inverted with respect to the board, so an absolute value would need flipping too.
# J1's footprint anchor is pad 1; its body centre is +4.00mm along the pad row and +2.35mm into
# the board, which is -2.35 in CPL Y.
POS_DELTA = {
    "J1": (4.00, -2.35),
}

subprocess.run([KICAD_CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm",
                "--side", "both", "--use-drill-file-origin", "-o", RAW, PCB], check=True)

rows = list(csv.reader(io.open(RAW, encoding="utf-8")))
out = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]]
for ref, val, pkg, x, y, rot, side in rows[1:]:
    x, y, rot = float(x), float(y), float(rot)
    rot = (rot + ROT_FIX.get(ref, 0)) % 360
    if ref in POS_DELTA:
        dx, dy = POS_DELTA[ref]
        x, y = x + dx, y + dy
    out.append([ref, f"{x:.4f}", f"{y:.4f}", "Top" if side == "top" else "Bottom", f"{rot:.1f}"])
with io.open(OUT, "w", encoding="utf-8", newline="") as f:
    csv.writer(f).writerows(out)
os.remove(RAW)
print(f"wrote {OUT}: {len(out) - 1} placements "
      f"({len(ROT_FIX)} rotation fixes, {len(POS_DELTA)} centroid fixes)")
