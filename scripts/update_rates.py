"""Refresh the workbook's exchange rates from a live source, re-price every
line item in every sheet against the new rates, and regenerate the app's
data file — the backing script for the update-rates skill.

Run from the project root: python3 scripts/update_rates.py

What it does:
1. Fetches live USD-based rates from open.er-api.com (free, no API key)
   and derives EUR/CHF/CZK -> COP from them.
2. Writes the new *base* rate into each currency's formula in the
   'Tasas de Cambio' sheet — cell E11:E14 already read
   `=<base rate>*$E$7`, where E7 is a markup factor already sitting at
   1.05 in this workbook. That 5% markup is the user's standing policy
   for this trip ("las tasas siempre súbele un 5% más") and is not
   something this script decides — it only refreshes the base rate the
   formula multiplies by, exactly like editing that cell by hand in
   Excel would. If E7 is ever changed to a different factor, this script
   picks up whatever markup is already there rather than hardcoding 5%
   itself.
3. Updates the "Fecha de actualización de tasas" date to today.
4. Re-prices every line item across every option sheet: any row whose
   currency is EUR/CHF/CZK/USD gets its cached rate/total/per-person
   values (I/J/K) recomputed against the new rate — titles, notes,
   links, unit prices and quantities are untouched, only the values that
   actually depend on the exchange rate change. COP-priced rows are
   already rate-independent and are skipped.
5. Regenerates src/data/generated/itinerary.generated.ts.

Editing style matches duplicate_option.py / manage_item.py: targeted
regex row/cell surgery, not a full-document XML parse — see
duplicate_option.py's module docstring for why a parse/reserialize
round-trip is unsafe on these large sheets.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "Europa2027_Cotizacion_plan_completo (1).xlsx"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

RATE_ROWS = {"EUR": 11, "CHF": 12, "CZK": 13, "USD": 14}
DATE_CELL = "C7"
MARKUP_CELL = "E7"
SHEET_NUMBERS = [4, 6, 8, 10, 12]
# sheet12 is the 2-person duplicate (scripts/duplicate_option.py) — its K
# formulas divide by a literal 2, not the shared people-count cell.
SHEET_K_DIVISOR = {4: "shared", 6: "shared", 8: "shared", 10: "shared", 12: "2"}


def cell_value_text(row_xml: str, col: str, row_num: int) -> str | None:
    m = re.search(rf'<c r="{col}{row_num}"[^>]*>.*?<v>([^<]*)</v>', row_xml, re.S)
    return m.group(1) if m else None


def set_cell_value(row_xml: str, col: str, row_num: int, new_value: str) -> str:
    # Lazy quantifier on the <f> body is required: a greedy one can walk
    # past this cell's own (possibly self-closing) formula and latch onto
    # an unrelated </f> several cells later — see duplicate_option.py.
    pattern = re.compile(rf'(<c r="{col}{row_num}"[^>]*>(?:<f[^>]*?(?:/>|>.*?</f>))?)<v>[^<]*</v>', re.S)
    new_xml, count = pattern.subn(rf'\g<1><v>{new_value}</v>', row_xml)
    assert count == 1, f"{col}{row_num}: expected 1 substitution, got {count}"
    return new_xml


def set_formula_number(row_xml: str, col: str, row_num: int, old_number: str, new_number: str) -> str:
    """Replace the literal base-rate number inside a cell's formula text
    (e.g. `3572*$E$7` -> `3629*$E$7`), leaving the *$E$7 markup reference
    and everything else in the row untouched."""
    pattern = re.compile(rf'(<c r="{col}{row_num}"[^>]*><f>){re.escape(old_number)}(\*\$E\$7</f>)')
    new_xml, count = pattern.subn(rf'\g<1>{new_number}\g<2>', row_xml)
    assert count == 1, f"{col}{row_num}: expected 1 formula substitution, got {count}"
    return new_xml


def fetch_live_rates() -> dict[str, float]:
    """USD-based rates from a free, keyless API; derive EUR/CHF/CZK/USD -> COP."""
    with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=15) as resp:
        data = json.load(resp)
    if data.get("result") != "success":
        raise RuntimeError(f"rate API did not return success: {data}")
    r = data["rates"]
    usd_to_cop = r["COP"]
    return {
        "EUR": usd_to_cop / r["EUR"],
        "CHF": usd_to_cop / r["CHF"],
        "CZK": usd_to_cop / r["CZK"],
        "USD": usd_to_cop,
    }


def main():
    live = fetch_live_rates()
    # Round like the existing base rates (near-whole numbers; CZK is small
    # enough that a whole-number round would lose too much precision).
    base_rates = {code: (round(v, 1) if code == "CZK" else round(v)) for code, v in live.items()}
    print("Live base rates fetched (before markup):")
    for code, v in base_rates.items():
        print(f"  {code}: {v}")

    with zipfile.ZipFile(WORKBOOK) as z:
        files = {n: z.read(n) for n in z.namelist()}

    # --- 1. 'Tasas de Cambio' sheet: base rates, markup-derived cached values, date ---
    sheet3 = files["xl/worksheets/sheet3.xml"].decode("utf-8")

    row7 = re.search(r'<row r="7"[^>]*>.*?</row>', sheet3, re.S).group(0)
    markup_str = cell_value_text(row7, "E", 7)
    markup = float(markup_str)
    print(f"Markup factor read from {MARKUP_CELL} (unchanged by this script): {markup}")

    row5 = re.search(r'<row r="5"[^>]*>.*?</row>', sheet3, re.S).group(0)
    people_count = float(cell_value_text(row5, "C", 5))
    print(f"Shared traveler count read from 'Tasas de Cambio'!C5: {people_count}")

    new_rates: dict[str, float] = {}
    for code, rn in RATE_ROWS.items():
        row_xml = re.search(rf'<row r="{rn}"[^>]*>.*?</row>', sheet3, re.S).group(0)
        old_formula_match = re.search(rf'<c r="E{rn}"[^>]*><f>([\d.]+)\*\$E\$7</f>', row_xml)
        assert old_formula_match, f"row {rn}: E column formula not in the expected '<base>*$E$7' shape"
        old_base = old_formula_match.group(1)
        new_base = str(base_rates[code])
        new_value = round(base_rates[code] * markup, 2)
        new_rates[code] = new_value
        new_row = set_formula_number(row_xml, "E", rn, old_base, new_base)
        new_row = set_cell_value(new_row, "E", rn, str(new_value))
        sheet3 = sheet3.replace(row_xml, new_row, 1)
        print(f"  {code}: base {old_base} -> {new_base}, rate (with {markup}x markup) -> {new_value}")

    row7_current = re.search(r'<row r="7"[^>]*>.*?</row>', sheet3, re.S).group(0)
    today_str = date.today().strftime("%d/%m/%Y")
    ss_root = ET.fromstring(files["xl/sharedStrings.xml"])
    shared_strings = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in ss_root.findall("x:si", NS)]
    ss_raw = files["xl/sharedStrings.xml"].decode("utf-8")
    new_refs = 0
    if today_str in shared_strings:
        date_idx = shared_strings.index(today_str)
    else:
        date_idx = len(shared_strings)
        ss_raw = ss_raw.replace("</sst>", f"<si><t>{today_str}</t></si></sst>")
        new_refs = 1
    pattern = re.compile(rf'(<c r="{DATE_CELL}"[^>]*t="s"><v>)[^<]*(</v>)')
    new_row7, count = pattern.subn(rf'\g<1>{date_idx}\g<2>', row7_current)
    assert count == 1, "date cell substitution failed"
    sheet3 = sheet3.replace(row7_current, new_row7, 1)
    print(f"Rate-update date set to {today_str}")

    if new_refs:
        m = re.search(r'<sst[^>]*count="(\d+)" uniqueCount="(\d+)"', ss_raw)
        count_, unique_ = int(m.group(1)), int(m.group(2))
        ss_raw = ss_raw.replace(f'count="{count_}" uniqueCount="{unique_}"', f'count="{count_ + 1}" uniqueCount="{unique_ + 1}"', 1)
        files["xl/sharedStrings.xml"] = ss_raw.encode("utf-8")

    files["xl/worksheets/sheet3.xml"] = sheet3.encode("utf-8")

    # --- 2. Re-price every currency-typed row across every option sheet ---
    total_rows_updated = 0
    for sheet_no in SHEET_NUMBERS:
        sheet_xml = files[f"xl/worksheets/sheet{sheet_no}.xml"].decode("utf-8")
        divisor = SHEET_K_DIVISOR[sheet_no]
        rows_updated = 0
        for row_match in list(re.finditer(r'<row r="(\d+)"[^>]*>.*?</row>', sheet_xml, re.S)):
            rn = int(row_match.group(1))
            if rn < 5:
                continue
            row_xml = row_match.group(0)
            title = cell_value_text(row_xml, "D", rn)
            if not title:
                continue
            currency_raw = cell_value_text(row_xml, "E", rn)
            if currency_raw is None:
                continue
            currency = shared_strings[int(currency_raw)] if currency_raw.isdigit() else currency_raw
            if currency not in new_rates:
                continue  # COP rows are rate-independent
            h_val = cell_value_text(row_xml, "H", rn)
            if h_val is None:
                continue
            new_rate = new_rates[currency]
            new_total_cop = float(h_val) * new_rate
            new_per_person = new_total_cop / 2 if divisor == "2" else new_total_cop / people_count
            new_row = set_cell_value(row_xml, "I", rn, str(new_rate))
            new_row = set_cell_value(new_row, "J", rn, str(new_total_cop))
            new_row = set_cell_value(new_row, "K", rn, str(new_per_person))
            sheet_xml = sheet_xml.replace(row_xml, new_row, 1)
            rows_updated += 1
        files[f"xl/worksheets/sheet{sheet_no}.xml"] = sheet_xml.encode("utf-8")
        print(f"sheet{sheet_no}: re-priced {rows_updated} rows")
        total_rows_updated += rows_updated

    # --- 3. Repackage ---
    new_path = str(WORKBOOK) + ".new"
    with zipfile.ZipFile(WORKBOOK) as zin, zipfile.ZipFile(new_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            zout.writestr(item, files[item])
    shutil.move(new_path, WORKBOOK)

    print(f"\nTotal rows re-priced: {total_rows_updated}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
