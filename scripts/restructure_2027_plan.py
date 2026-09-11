"""One-off migration: reorganize the "1 mes por Europa Zúrich" sheet (sheet4)
into the new "1 mes por Europa" plan — arrival now goes straight to
Barcelona (real Iberia flight, no more Zürich opening), the cruise moves to
the front of the trip, and the trip now ends in Berlín (with Múnich visited
just before it) to match the real return flight out of Berlín.

Run once from the project root:
    python3 scripts/restructure_2027_plan.py

Not meant to be re-run or reused for a future reorganization — like
scripts/duplicate_option_venice.py, this is a one-time migration tailored to
this exact before/after. It edits sheet4's raw XML directly (reusing
manage_item.py's Workbook helper), then regenerates the app's data file.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manage_item import ROOT, Workbook, confirmed_date_text, build_note  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402

SHEET = 4

# Rows whose entire content is now dead weight (the Zürich opening, and the
# two internal legs — Zürich→París, París→Barcelona — that only existed to
# connect it) — blanked back to an empty scaffold row.
DELETE_ROWS = [7, 8, 11, 12, 13, 14, 16, 24, 84]

# Rows kept, but fully rewritten: either real new content (the two
# international flights) or a transport leg whose route changed and has no
# real quote yet for the new pairing (left as "Pendiente cotizar", 0 COP,
# rather than guessing a price) — or a same-city transfer whose mode changed
# (train/flight vs the original) enough that its price/note no longer apply.
FULL_REBUILD = {
    6: dict(category="Vuelos y Trenes", place="Bogota / Barcelona", date_text="7 May 2027",
            title="Vuelo internacional Bogotá → Barcelona (ida y vuelta)", currency="COP",
            unit_amount=2740300, quantity=3,
            note="Iberia IB0156, vía Madrid (MAD). Llegada Barcelona 07 May 08:25. Incluye tramo de regreso."),
    78: dict(category="Vuelos y Trenes", place="Alemania / Colombia", date_text="31 May 2027",
             title="Vuelo internacional Berlín → Bogotá (regreso)", currency="COP",
             unit_amount=0, quantity=1,
             note="Iberia IB0782 + IB0153, vía Madrid. Incluido en la tarifa ida y vuelta del vuelo de ida."),
    58: dict(category="Vuelos y Trenes", place="Italia / Francia", date_text="20 May 2027",
             title="Vuelo interno Roma → París", currency="COP", unit_amount=0, quantity=3,
             note="Pendiente cotizar — nueva ruta tras reorganizar el itinerario (antes Roma → Praga)."),
    15: dict(category="Vuelos y Trenes", place="Francia / Rep. Checa", date_text="23 May 2027",
             title="Vuelo interno París → Praga", currency="COP", unit_amount=0, quantity=3,
             note="Pendiente cotizar — nueva ruta tras reorganizar el itinerario."),
    71: dict(category="Vuelos y Trenes", place="Rep. Checa / Alemania", date_text="26 May 2027",
             title="Tren de alta velocidad Praga → Múnich", currency="COP", unit_amount=0, quantity=3,
             note="Pendiente cotizar — nueva ruta tras reorganizar el itinerario (antes Berlín → Múnich)."),
    65: dict(category="Vuelos y Trenes", place="Alemania", date_text="28 May 2027",
             title="Tren de alta velocidad Múnich → Berlín", currency="COP", unit_amount=0, quantity=3,
             note="Pendiente cotizar — nueva ruta tras reorganizar el itinerario (antes Praga → Berlín)."),
    17: dict(category="Traslados", place="Francia", date_text="20 May 2027",
             title="Traslado aeropuerto → hotel, París", currency="EUR", unit_amount=50, quantity=1,
             note="Estimado: Uber/taxi desde el aeropuerto (CDG/Orly) al hotel, ~45-60 min, €45-60."),
    79: dict(category="Traslados", place="Alemania", date_text="26 May 2027",
             title="Traslado hotel → estación, Múnich", currency="EUR", unit_amount=10, quantity=1,
             note="Estimado: el hotel está muy cerca de la Estación Central, Uber corto o caminando, €8-12."),
}

# A brand-new line item with no existing row to repurpose: Berlín now needs
# its own hotel → airport transfer for the international departure, which
# the old plan never had (Berlín used to be a mid-trip stop, not the end).
ADD_ROWS = [
    dict(category="Traslados", place="Alemania", date_text="31 May 2027",
         title="Traslado hotel → aeropuerto, Berlín", currency="COP", unit_amount=0, quantity=1,
         note="Pendiente cotizar — transfer para el vuelo de regreso."),
]

# Everything else: same content, just re-dated (and occasionally a place
# label tweak) to its new day in the 07–31 May sequence. See the itinerary
# reorg this migration implements: Barcelona (llegada+tour) → Crucero
# (Barcelona→Ravenna, 7 noches) → Venecia (1 noche post-crucero) → Roma (3
# noches) → París (3 noches) → Praga (3 noches) → Múnich (2 noches) →
# Berlín (3 noches + día de vuelo de regreso).
CELL_PATCHES: dict[int, dict[str, str]] = {
    5: {"C": "7 – 31 May 2027 (25 días de cobertura)"},
    26: {"C": "7 May 2027"},
    28: {"C": "7 May 2027"},
    92: {"C": "7 May 2027"},
    27: {"C": "7 – 9 May (2 noches, pre-crucero)"},
    29: {"C": "8 May 2027"},
    30: {"C": "8 May 2027"},
    31: {"C": "8 May 2027"},
    80: {"C": "8 May 2027"},
    32: {"C": "9 May 2027"},
    34: {"C": "9 May 2027"},
    35: {"C": "9 May 2027"},
    33: {"C": "9 – 16 May (7 noches)"},
    82: {"C": "10 May 2027"},
    93: {"C": "10 May 2027"},
    37: {"C": "11 May 2027"},
    38: {"C": "11 May 2027"},
    39: {"C": "12 May 2027"},
    40: {"C": "12 May 2027"},
    41: {"C": "13 May 2027"},
    42: {"C": "13 May 2027"},
    83: {"C": "14 May 2027"},
    94: {"C": "14 May 2027"},
    44: {"C": "15 May 2027"},
    45: {"C": "15 May 2027"},
    36: {"C": "16 May 2027"},
    43: {"C": "16 May 2027"},
    46: {"C": "16 May 2027"},
    53: {"C": "16 May 2027"},
    48: {"C": "16 May 2027"},
    47: {"C": "16 – 17 May (1 noche, post-crucero)"},
    49: {"C": "17 May 2027"},
    50: {"C": "17 May 2027"},
    51: {"C": "17 May 2027"},
    54: {"C": "17 May 2027"},
    52: {"C": "17 – 20 May (3 noches)"},
    55: {"C": "18 May 2027"},
    56: {"C": "18 May 2027"},
    57: {"C": "19 May 2027"},
    88: {"C": "19 May 2027"},
    59: {"C": "20 May 2027"},
    19: {"C": "20 May 2027"},
    18: {"C": "20 – 23 May (3 noches)"},
    20: {"C": "21 May 2027"},
    21: {"C": "21 May 2027"},
    22: {"C": "22 May 2027"},
    23: {"C": "22 May 2027"},
    25: {"C": "23 May 2027"},
    60: {"C": "23 May 2027"},
    85: {"C": "23 May 2027"},
    61: {"C": "23 – 26 May (3 noches)"},
    62: {"C": "24 May 2027"},
    63: {"C": "24 May 2027"},
    64: {"C": "25 May 2027"},
    89: {"C": "25 May 2027"},
    72: {"C": "26 May 2027"},
    74: {"C": "26 May 2027"},
    87: {"C": "26 May 2027"},
    73: {"C": "26 – 28 May (2 noches)"},
    75: {"C": "27 May 2027"},
    76: {"C": "27 May 2027"},
    66: {"B": "Alemania", "C": "28 May 2027"},
    86: {"C": "28 May 2027"},
    67: {"C": "28 – 31 May (3 noches)"},
    68: {"C": "29 May 2027"},
    69: {"C": "29 May 2027"},
    70: {"C": "30 May 2027"},
    90: {"C": "30 May 2027"},
    91: {"B": "Berlín", "C": "31 May 2027"},
}


def patch_cell(wb: Workbook, row_no: int, col: str, new_text: str) -> None:
    idx = wb.get_or_add_shared_string(new_text)
    key = f"xl/worksheets/sheet{SHEET}.xml"
    raw = wb.files[key].decode("utf-8")
    pattern = re.compile(rf'(<c r="{col}{row_no}"[^>]*>)<v>\d+</v>(</c>)')
    new_raw, n = pattern.subn(lambda m: f"{m.group(1)}<v>{idx}</v>{m.group(2)}", raw, count=1)
    if n != 1:
        raise RuntimeError(f"{col}{row_no}: expected exactly 1 match, got {n}")
    wb.files[key] = new_raw.encode("utf-8")


def rebuild_row(wb: Workbook, row_no: int, spec: dict) -> None:
    note_with_link = build_note(spec["note"], None)
    cells_xml, _ = wb.build_row_xml(
        row_no,
        category=spec["category"], place=spec["place"], date_text=spec["date_text"],
        title=spec["title"], currency=spec["currency"], unit_amount=spec["unit_amount"],
        quantity=spec["quantity"], note_with_link=note_with_link,
        confirmed_date=confirmed_date_text(),
    )
    wb.replace_row(SHEET, row_no, cells_xml)


def main() -> None:
    wb = Workbook()

    for row_no in DELETE_ROWS:
        wb.replace_row(SHEET, row_no, wb.blank_row_xml(row_no))

    for row_no, spec in FULL_REBUILD.items():
        rebuild_row(wb, row_no, spec)

    for spec in ADD_ROWS:
        row_no = wb.find_blank_row(SHEET)
        rebuild_row(wb, row_no, spec)

    for row_no, cols in CELL_PATCHES.items():
        for col, text in cols.items():
            patch_cell(wb, row_no, col, text)

    # Net new shared-string references added to the workbook's `count`
    # attribute: rebuilt rows replace 7 existing refs with 7 new ones (net
    # 0), each brand-new ADD row turns 7 blank cells into 7 refs (+7 each),
    # and single-cell patches replace 1 ref with 1 (net 0).
    new_refs = 7 * len(ADD_ROWS)
    wb.save(new_refs)

    print(f"Deleted {len(DELETE_ROWS)} rows, rebuilt {len(FULL_REBUILD)}, added {len(ADD_ROWS)}, patched {len(CELL_PATCHES)} cells-groups.")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
