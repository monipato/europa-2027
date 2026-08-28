"""Add or update a single line item in the quote workbook.

Run from the project root:
    python3 scripts/manage_item.py add    --option "Crucero para 3" --category "Tours y Excursiones" \
        --place "Zadar" --date "14 May 2027" --title "Tour a pie por el casco antiguo" \
        --currency EUR --unit-amount 15 --quantity 3 \
        --note "Tour guiado 2h, incluye entrada a la catedral" --link "https://example.com/tour"

    python3 scripts/manage_item.py update --option "Crucero para 3" --match-title "SIM card" \
        --currency USD --unit-amount 45 --quantity 1 --note "..." --link "..."

    python3 scripts/manage_item.py delete --option "Crucero para 3" --match-title "Free tour"

This is the only supported way to hand-edit a line item in the workbook — it
edits the raw .xlsx XML directly (same approach as generate_data.py, no
external dependency), keeps every native Excel formula intact, and always
regenerates src/data/generated/itinerary.generated.ts afterward so the app
and the spreadsheet never drift apart. Never hand-edit the .xlsx in a
spreadsheet app for these kinds of changes and never hand-edit the
generated .ts file — use this script instead.

Design notes:
- Currency conversion rates are read live from the 'Tasas de Cambio' sheet
  (never hardcoded), so the amounts always use whatever rate is currently
  in the workbook.
- New rows reuse the sheet's own live Excel formulas (F*G, H*I, J/people)
  instead of writing pre-computed numbers, so the row keeps recalculating
  correctly if it's ever hand-edited in Excel later.
- The note shown in the app (both the "Por día" and "Por rubro" views read
  the exact same field) must be <= 20 words — the single most relevant
  fact about the item. Anything else (a price-confirmation date, an
  internal comment) belongs in column M ("Fecha confirmación precio"),
  which the generator never reads, not in the note.
- A link is optional. If given, it's appended to the end of the note text
  and the app automatically renders it as a "Ver tour o sitio web" button
  that opens in a new tab, in both views. If omitted, no link is shown.
- On `update`, changing `--note` without also passing `--link` keeps the
  row's existing link (extracted back out of its current note+link text) —
  it does not get silently dropped. Pass `--link ""` to explicitly remove
  an existing link while updating the note.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "Europa2027_Cotizacion_plan_completo (1).xlsx"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Option name -> sheet number, matching the mapping in generate_data.py's main().
OPTION_SHEETS = {
    "1 mes por Europa": 4,
    "Zúrich y Crucero": 6,
    "Múnich y Crucero": 8,
    "Crucero para 3": 10,
    "Crucero en pareja": 12,
    "Crucero para 4": 13,
}

# Options whose per-person headcount differs from the workbook-wide
# 'Tasas de Cambio'!C5 value (see scripts/duplicate_option.py /
# scripts/duplicate_option_4p.py) — their K formulas divide by a literal
# number instead of that shared cell.
OPTION_PEOPLE_OVERRIDE = {
    "Crucero en pareja": 2,
    "Crucero para 4": 4,
}

CATEGORIES = {
    "Vuelos y Trenes", "Traslados", "Alojamiento", "Crucero",
    "Tours y Excursiones", "Comidas", "Seguro de Viaje", "Otros y Extras",
}

CURRENCIES = {"EUR", "CHF", "CZK", "USD", "COP"}

MONTHS_ES_LOWER = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Column layout shared by every "Cotización"-style sheet (A..M).
COLUMNS = "ABCDEFGHIJKLM"

# Style ids used by every item row across all 4 sheets (identical template).
STYLES = {
    "A": 29, "B": 29, "C": 30, "D": 32, "E": 33, "F": 34, "G": 33,
    "H": 51, "I": 51, "J": 52, "K": 53, "L": 54,
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def word_count(text: str) -> int:
    return len(text.split())


class Workbook:
    """Thin wrapper around the raw zip/XML editing needed to add or update a
    row. Everything is staged in memory and written back atomically."""

    def __init__(self):
        with zipfile.ZipFile(WORKBOOK) as z:
            self.files = {name: z.read(name) for name in z.namelist()}
        self.shared_strings = self._parse_shared_strings()

    def _parse_shared_strings(self) -> list[str]:
        root = ET.fromstring(self.files["xl/sharedStrings.xml"])
        return ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root.findall("x:si", NS)]

    def cell_value(self, cell: ET.Element) -> str:
        node = cell.find("x:v", NS)
        raw = "" if node is None else (node.text or "")
        if cell.attrib.get("t") == "s" and raw:
            return self.shared_strings[int(raw)]
        return raw

    def sheet_root(self, sheet_no: int) -> ET.Element:
        return ET.fromstring(self.files[f"xl/worksheets/sheet{sheet_no}.xml"])

    def get_or_add_shared_string(self, text: str) -> int:
        for i, s in enumerate(self.shared_strings):
            if s == text:
                return i
        idx = len(self.shared_strings)
        self.shared_strings.append(text)
        return idx

    def read_rate(self, currency: str) -> float:
        """Live lookup from the 'Tasas de Cambio' sheet (sheet3) — never hardcoded."""
        if currency == "COP":
            return 1.0
        sheet = self.sheet_root(3)
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            cells = {c.attrib["r"]: self.cell_value(c) for c in row.findall("x:c", NS)}
            code = cells.get(f"B{row.attrib['r']}", "")
            if code == currency:
                return float(cells.get(f"E{row.attrib['r']}", "0"))
        raise ValueError(f"Currency {currency} not found in 'Tasas de Cambio' sheet")

    def read_people_count(self) -> int:
        sheet = self.sheet_root(3)
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            cells = {c.attrib["r"]: self.cell_value(c) for c in row.findall("x:c", NS)}
            if cells.get(f"B{row.attrib['r']}", "") == "Número de personas":
                return int(float(cells.get(f"C{row.attrib['r']}", "3")))
        return 3

    def find_row_by_title(self, sheet_no: int, match_title: str, match_date: str | None = None) -> int | None:
        """Match by substring, but only ever silently return a result when
        it's unambiguous. Preference order: (1) a case-sensitive exact title
        match — the strongest signal; (2) if none, a case-insensitive exact
        match, but only if exactly one row qualifies (two rows differing
        only by case, e.g. "Tour a pie gratis" vs "tour a pie gratis", must
        not be silently conflated); (3) otherwise substring matches, again
        only if exactly one qualifies. Any ambiguity at (2) or (3) raises
        instead of guessing — two real edits in this project accidentally
        clobbered the wrong row (a substring collision, then a same-modulo-
        case collision) before these checks existed.

        If match_date is given, candidates are filtered to rows whose
        column C (date) exactly matches it *before* the ambiguity checks
        above — needed for a title that's intentionally repeated once per
        day (e.g. "Comida del día (almuerzo y cena)"), where title alone
        can never disambiguate."""
        sheet = self.sheet_root(sheet_no)
        needle = match_title.strip()
        needle_lower = needle.lower()
        exact_ci, substring, case_sensitive_hit = [], [], None
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            rn = int(row.attrib["r"])
            if rn < 5:
                continue
            cells = {c.attrib["r"]: self.cell_value(c) for c in row.findall("x:c", NS)}
            title = cells.get(f"D{rn}", "")
            if not title:
                continue
            if match_date is not None and cells.get(f"C{rn}", "").strip() != match_date.strip():
                continue
            stripped = title.strip()
            if stripped == needle:
                case_sensitive_hit = rn
            if stripped.lower() == needle_lower:
                exact_ci.append((rn, title))
            elif needle_lower in title.lower():
                substring.append((rn, title))
        if case_sensitive_hit is not None:
            return case_sensitive_hit
        if len(exact_ci) > 1:
            listing = "; ".join(f"row {rn}: {t!r}" for rn, t in exact_ci)
            raise SystemExit(f"--match-title {match_title!r} matches {len(exact_ci)} rows that differ only by case, ambiguous: {listing}. Use --match-title with the exact case shown, or add --match-date.")
        if exact_ci:
            return exact_ci[0][0]
        if len(substring) > 1:
            listing = "; ".join(f"row {rn}: {t!r}" for rn, t in substring)
            raise SystemExit(f"--match-title {match_title!r} matches {len(substring)} rows, ambiguous: {listing}. Use a more specific --match-title, or add --match-date.")
        return substring[0][0] if substring else None

    def find_blank_row(self, sheet_no: int) -> int:
        """First existing scaffold row (>=5) with an empty title (column D) —
        every sheet already has hundreds of pre-styled blank rows past its
        last real item, so a brand new item never needs row insertion."""
        sheet = self.sheet_root(sheet_no)
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            rn = int(row.attrib["r"])
            if rn < 5:
                continue
            cells = {c.attrib["r"]: self.cell_value(c) for c in row.findall("x:c", NS)}
            if not cells.get(f"D{rn}", "").strip():
                return rn
        raise RuntimeError(f"sheet{sheet_no}: no blank scaffold row found")

    def build_row_xml(self, row_no: int, *, category: str, place: str, date_text: str,
                       title: str, currency: str, unit_amount: float, quantity: float,
                       note_with_link: str, confirmed_date: str, people_override: int | None = None) -> str:
        rate = self.read_rate(currency)
        people = people_override if people_override is not None else self.read_people_count()

        idx_category = self.get_or_add_shared_string(category)
        idx_place = self.get_or_add_shared_string(place)
        idx_date = self.get_or_add_shared_string(date_text)
        idx_title = self.get_or_add_shared_string(title)
        idx_currency = self.get_or_add_shared_string(currency)
        idx_note = self.get_or_add_shared_string(note_with_link)
        idx_confirmed = self.get_or_add_shared_string(confirmed_date)

        total_original = unit_amount * quantity
        total_cop = total_original * rate
        per_person = total_cop / people

        cells = []
        cells.append(f'<c r="A{row_no}" s="{STYLES["A"]}" t="s"><v>{idx_category}</v></c>')
        cells.append(f'<c r="B{row_no}" s="{STYLES["B"]}" t="s"><v>{idx_place}</v></c>')
        cells.append(f'<c r="C{row_no}" s="{STYLES["C"]}" t="s"><v>{idx_date}</v></c>')
        cells.append(f'<c r="D{row_no}" s="{STYLES["D"]}" t="s"><v>{idx_title}</v></c>')
        cells.append(f'<c r="E{row_no}" s="{STYLES["E"]}" t="s"><v>{idx_currency}</v></c>')
        cells.append(f'<c r="F{row_no}" s="{STYLES["F"]}"><v>{unit_amount}</v></c>')
        cells.append(f'<c r="G{row_no}" s="{STYLES["G"]}"><v>{quantity}</v></c>')
        cells.append(f'<c r="H{row_no}" s="{STYLES["H"]}"><f>IFERROR(F{row_no}*G{row_no},0)</f><v>{total_original}</v></c>')
        cells.append(
            f'<c r="I{row_no}" s="{STYLES["I"]}">'
            f'<f t="array" ref="I{row_no}">IFERROR(INDEX(\'Tasas de Cambio\'!$E$11:$E$15,'
            f'MATCH(E{row_no},\'Tasas de Cambio\'!$B$11:$B$15,0)),0)</f><v>{rate}</v></c>'
        )
        cells.append(f'<c r="J{row_no}" s="{STYLES["J"]}"><f>IFERROR(H{row_no}*I{row_no},0)</f><v>{total_cop}</v></c>')
        k_divisor = str(people_override) if people_override is not None else "'Tasas de Cambio'!$C$5"
        cells.append(
            f'<c r="K{row_no}" s="{STYLES["K"]}">'
            f"<f>IFERROR(J{row_no}/{k_divisor},0)</f><v>{per_person}</v></c>"
        )
        cells.append(f'<c r="L{row_no}" s="{STYLES["L"]}" t="s"><v>{idx_note}</v></c>')
        cells.append(f'<c r="M{row_no}" s="1" t="s"><v>{idx_confirmed}</v></c>')

        return "".join(cells), per_person

    def blank_row_xml(self, row_no: int) -> str:
        """Reset a row back to the same empty scaffold state find_blank_row()
        looks for, so a deleted item's row can be reused by a future add."""
        cells = [f'<c r="{col}{row_no}" s="{STYLES.get(col, 1)}"/>' for col in COLUMNS]
        return "".join(cells)

    def replace_row(self, sheet_no: int, row_no: int, new_cells_xml: str):
        raw = self.files[f"xl/worksheets/sheet{sheet_no}.xml"].decode("utf-8")
        pattern = re.compile(rf'(<row r="{row_no}"[^>]*>).*?(</row>)', re.S)
        match = pattern.search(raw)
        if not match:
            raise RuntimeError(f"sheet{sheet_no}: row {row_no} not found")
        new_row = match.group(1) + new_cells_xml + match.group(2)
        raw = raw[: match.start()] + new_row + raw[match.end() :]
        self.files[f"xl/worksheets/sheet{sheet_no}.xml"] = raw.encode("utf-8")

    def _rebuild_shared_strings_xml(self):
        original = self.files["xl/sharedStrings.xml"].decode("utf-8")
        m = re.search(r'<sst[^>]*uniqueCount="(\d+)"', original)
        old_unique = int(m.group(1))
        new_entries = self.shared_strings[old_unique:]
        if new_entries:
            appended = "".join(f"<si><t>{esc(t)}</t></si>" for t in new_entries)
            original = original.replace("</sst>", appended + "</sst>")
        m2 = re.search(r'<sst[^>]*count="(\d+)" uniqueCount="(\d+)"', original)
        count, unique = int(m2.group(1)), int(m2.group(2))
        new_count = count + self._new_refs
        new_unique = unique + len(new_entries)
        original = original.replace(f'count="{count}" uniqueCount="{unique}"', f'count="{new_count}" uniqueCount="{new_unique}"', 1)
        self.files["xl/sharedStrings.xml"] = original.encode("utf-8")

    def save(self, new_refs: int):
        self._new_refs = new_refs
        self._rebuild_shared_strings_xml()
        new_path = str(WORKBOOK) + ".new"
        with zipfile.ZipFile(WORKBOOK) as zin, zipfile.ZipFile(new_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                zout.writestr(item, self.files[item])
        shutil.move(new_path, WORKBOOK)


def confirmed_date_text() -> str:
    today = date.today()
    return f"{today.day} {MONTHS_ES_LOWER[today.month - 1]} {today.year}"


LINK_RE = re.compile(r"https?://\S+")


def extract_link(note: str) -> str | None:
    match = LINK_RE.search(note)
    return match.group(0).rstrip(".,)") if match else None


def strip_link(note: str) -> str:
    return LINK_RE.sub("", note).strip(" .|")


def build_note(note: str, link: str | None) -> str:
    if word_count(note) > 20:
        raise SystemExit(f"Note is {word_count(note)} words (max 20): {note!r}")
    note = note.strip()
    if link:
        note = note.rstrip(".") + ". " + link.strip()
    return note


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["add", "update", "delete"])
    parser.add_argument("--option", required=True, choices=list(OPTION_SHEETS))
    parser.add_argument("--category", choices=sorted(CATEGORIES))
    parser.add_argument("--place", default="")
    parser.add_argument("--date", dest="date_text", default="", help='e.g. "14 May 2027", or a dateless label like "Durante el viaje"')
    parser.add_argument("--title", help="Required for 'add'; optional for 'update' (keeps the matched title if omitted)")
    parser.add_argument("--match-title", help="Substring to find the row to update (required for 'update')")
    parser.add_argument("--match-date", help="Also filter --match-title candidates by exact column-C date text, for a title repeated once per day (e.g. \"Comida del día\")")
    parser.add_argument("--currency", choices=sorted(CURRENCIES))
    parser.add_argument("--unit-amount", type=float)
    parser.add_argument("--quantity", type=float)
    parser.add_argument("--note", help="Max 20 words — the single most relevant fact about this item")
    parser.add_argument("--link", default=None, help="Optional booking/info URL")
    args = parser.parse_args()

    wb = Workbook()
    sheet_no = OPTION_SHEETS[args.option]

    if args.action == "delete":
        if not args.match_title:
            raise SystemExit("delete requires --match-title")
        row_no = wb.find_row_by_title(sheet_no, args.match_title, args.match_date)
        if row_no is None:
            raise SystemExit(f"No row found in {args.option!r} matching title {args.match_title!r}")
        sheet = wb.sheet_root(sheet_no)
        deleted_title = ""
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            if int(row.attrib["r"]) != row_no:
                continue
            for c in row.findall("x:c", NS):
                if c.attrib["r"][0] == "D":
                    deleted_title = wb.cell_value(c)
        wb.replace_row(sheet_no, row_no, wb.blank_row_xml(row_no))
        wb.save(new_refs=-7)
        print(f"Deleted row {row_no} in sheet{sheet_no} ({args.option}): {deleted_title!r}")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)
        return

    if args.action == "add":
        missing = [f for f in ("category", "title", "currency", "unit_amount", "quantity", "note") if getattr(args, f) is None or getattr(args, f) == ""]
        if missing:
            raise SystemExit(f"add requires: {', '.join(missing)}")
        row_no = wb.find_blank_row(sheet_no)
        action_desc = "Added"
    else:
        if not args.match_title:
            raise SystemExit("update requires --match-title")
        row_no = wb.find_row_by_title(sheet_no, args.match_title, args.match_date)
        if row_no is None:
            raise SystemExit(f"No row found in {args.option!r} matching title {args.match_title!r}")
        # Fill in any field the caller didn't override from the existing row.
        sheet = wb.sheet_root(sheet_no)
        existing = {}
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            if int(row.attrib["r"]) != row_no:
                continue
            for c in row.findall("x:c", NS):
                existing[c.attrib["r"][0]] = wb.cell_value(c)  # keyed by column letter
        args.category = args.category or existing.get("A", "")
        args.place = args.place or existing.get("B", "")
        args.date_text = args.date_text or existing.get("C", "")
        args.title = args.title or existing.get("D", "")
        args.currency = args.currency or existing.get("E", "COP")
        args.unit_amount = args.unit_amount if args.unit_amount is not None else float(existing.get("F", "0") or 0)
        args.quantity = args.quantity if args.quantity is not None else float(existing.get("G", "1") or 1)
        action_desc = "Updated"

    if args.category not in CATEGORIES:
        raise SystemExit(f"Unknown category {args.category!r}. Must be one of: {sorted(CATEGORIES)}")

    # Note and link share one workbook cell (column L), but are two
    # independent CLI flags, so any of the 4 combinations must work as its
    # own flag suggests — updating just one must never silently discard the
    # other:
    #   --note only    -> new note,      existing link kept
    #   --link only    -> existing note, new link applied
    #   both           -> both new
    #   neither        -> row unchanged (update) / blank (add)
    # `is not None` (not truthy) throughout so `--note ""` / `--link ""`
    # explicitly clear that piece instead of being indistinguishable from
    # omitting the flag.
    existing_note_with_link = existing.get("L", "") if args.action == "update" else ""
    bare_note = args.note if args.note is not None else strip_link(existing_note_with_link)
    link = args.link if args.link is not None else extract_link(existing_note_with_link)
    if args.note is not None or args.link is not None or args.action == "add":
        note_with_link = build_note(bare_note, link)
    else:
        note_with_link = existing_note_with_link
    confirmed = confirmed_date_text()

    cells_xml, per_person = wb.build_row_xml(
        row_no,
        category=args.category, place=args.place, date_text=args.date_text, title=args.title,
        currency=args.currency, unit_amount=args.unit_amount, quantity=args.quantity,
        note_with_link=note_with_link, confirmed_date=confirmed,
        people_override=OPTION_PEOPLE_OVERRIDE.get(args.option),
    )
    # A,B,C,D,E,L,M are the 7 shared-string-typed cells per row. An "add" turns 7
    # previously-blank cells into 7 string references (net +7 to sst's `count`);
    # an "update" replaces 7 existing string references with 7 new ones (net 0).
    new_refs = 7 if args.action == "add" else 0

    wb.replace_row(sheet_no, row_no, cells_xml)
    wb.save(new_refs)

    print(f"{action_desc} row {row_no} in sheet{sheet_no} ({args.option}):")
    print(f"  {args.title}  ·  {args.category}")
    print(f"  {args.currency} {args.unit_amount} x {args.quantity} -> $ {per_person:,.0f} COP/persona".replace(",", "."))
    print(f"  Note: {note_with_link}")
    print(f"  Confirmed: {confirmed} (Excel column M only)")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
