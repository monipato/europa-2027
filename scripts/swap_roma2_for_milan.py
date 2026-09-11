"""One-off follow-up to restructure_2027_plan.py: in "1 mes por Europa"
(sheet4), the second Roma stop (the 3-night post-cruise stay with Coliseo +
Vaticano tours, disembark-side of the cruise) is replaced with Milán —
reusing the real Duomo ticket and Alpine Wonders (Swiss Alps day trip)
pricing already quoted for "Italia" (sheet14), since both options now visit
Milán. The cruise's own Roma port call (Civitavecchia) is untouched — this
only removes the *second* Roma visit.

Run once from the project root:
    python3 scripts/swap_roma2_for_milan.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manage_item import ROOT, Workbook, confirmed_date_text, build_note  # noqa: E402

SHEET = 4

FULL_REBUILD = {
    49: dict(category="Vuelos y Trenes", place="Italia", date_text="17 May 2027",
             title="Tren Venecia → Milán, directo", currency="COP", unit_amount=0, quantity=3,
             note="Pendiente cotizar — nueva ruta tras reemplazar la segunda parada en Roma por Milán.", link=None),
    51: dict(category="Traslados", place="Italia", date_text="17 May 2027",
             title="Traslado estación → hotel, Milán", currency="COP", unit_amount=0, quantity=1,
             note="Pendiente cotizar — transfer estación Milano Centrale → hotel.", link=None),
    52: dict(category="Alojamiento", place="Milán, Italia", date_text="17 – 20 May (3 noches)",
             title="Hotel Milán — costo por noche", currency="COP", unit_amount=0, quantity=1,
             note="Pendiente cotizar — nueva ciudad tras reorganizar el itinerario (antes Roma).", link=None),
    55: dict(category="Tours y Excursiones", place="Milán", date_text="18 May 2027",
             title="Duomo di Milano y terrazas (entrada)", currency="EUR", unit_amount=16, quantity=3,
             note="Entrada terrazas con ascensor, precio oficial.",
             link="https://ticket.duomomilano.it/en/categoria/terrazze/"),
    57: dict(category="Tours y Excursiones", place="Milán", date_text="19 May 2027",
             title="Alpine Wonders: almuerzo en Diavolezza y tren Bernina", currency="USD", unit_amount=250, quantity=3,
             note="Excursión de día completo desde Milán, tren panorámico Bernina.",
             link="https://www.tripadvisor.com/AttractionProductReview-g187849-d15090556-From_Milan_Alpine_Wonders_Lunch_at_Diavolezza_and_Bernina_Train-Milan_Lombardy.html"),
    58: dict(category="Vuelos y Trenes", place="Italia / Francia", date_text="20 May 2027",
             title="Vuelo interno Milán → París", currency="COP", unit_amount=0, quantity=3,
             note="Pendiente cotizar — nueva ruta tras reorganizar el itinerario.", link=None),
    59: dict(category="Traslados", place="Italia", date_text="20 May 2027",
             title="Traslado hotel → aeropuerto, Milán", currency="COP", unit_amount=0, quantity=1,
             note="Pendiente cotizar — transfer al aeropuerto de Milán.", link=None),
}

# Same-day meal rows that just need their place label swapped from Roma to
# Milán — the amount (a generic per-day meal estimate) doesn't depend on city.
TEXT_PATCHES = {
    56: {"B": "Milán"},
    88: {"B": "Milán"},
    # Leftover from restructure_2027_plan.py: this note's date range was
    # never updated to match the new 7-9 May Barcelona stay (still said "6-8
    # may", the old dates) — fixed here while touching the same sheet.
    27: {"L": "Sagrada Familia, 2 noches (7-9 may). https://www.booking.com/hotel/es/sagradafamilia.es.html?aid=2311236&label=es-co-booking-desktop-vjGZbEFOhRc3a9njxeT3IwS652829002024%3Apl%3Ata%3Ap1%3Ap2%3Aac%3Aap%3Aneg%3Afi%3Atikwd-65526620%3Alp9246960%3Ali%3Adec%3Adm&sid=f6a1a9bb810c453f7b5f1225205f1f26&all_sr_blocks=9118812_91908190_0_2_0&checkin=2027-05-07&checkout=2027-05-09&dest_id=-372490&dest_type=city&dist=0&group_adults=3&group_children=0&hapos=1&highlighted_blocks=9118812_91908190_0_2_0&hpos=1&matching_block_id=9118812_91908190_0_2_0&no_rooms=1&req_adults=3&req_children=0&room1=A%2CA%2CA&sb_price_type=total&sr_order=popularity&sr_pri_blocks=9118812_91908190_0_2_0__37600&srepoch=1787875557&srpvid=a2d600b07c230149&type=total&ucfs=1"},
}


def patch_cell(wb: Workbook, row_no: int, col: str, new_text: str) -> None:
    import re
    idx = wb.get_or_add_shared_string(new_text)
    key = f"xl/worksheets/sheet{SHEET}.xml"
    raw = wb.files[key].decode("utf-8")
    pattern = re.compile(rf'(<c r="{col}{row_no}"[^>]*>)<v>\d+</v>(</c>)')
    new_raw, n = pattern.subn(lambda m: f"{m.group(1)}<v>{idx}</v>{m.group(2)}", raw, count=1)
    if n != 1:
        raise RuntimeError(f"{col}{row_no}: expected exactly 1 match, got {n}")
    wb.files[key] = new_raw.encode("utf-8")


def rebuild_row(wb: Workbook, row_no: int, spec: dict) -> None:
    note_with_link = build_note(spec["note"], spec.get("link"))
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

    for row_no, spec in FULL_REBUILD.items():
        rebuild_row(wb, row_no, spec)

    for row_no, cols in TEXT_PATCHES.items():
        for col, text in cols.items():
            patch_cell(wb, row_no, col, text)

    wb.save(new_refs=0)

    print(f"Rebuilt {len(FULL_REBUILD)} rows, patched {len(TEXT_PATCHES)} cells-groups.")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
