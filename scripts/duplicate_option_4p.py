"""One-off: duplicate the 'Crucero' (Crucero para 3) sheet into a new sheet
for a 4-person version of that same itinerary, then apply the pricing
transformation used for the 2-person duplicate (see duplicate_option.py's
docstring for the full reasoning — this mirrors it exactly, just with 4
instead of 2):

- Rows priced per-person (quantity == 3, the current headcount) keep their
  unit price unchanged and just get quantity -> 4. Their K-column formula
  is rewritten to divide by a literal 4 instead of the shared
  'Tasas de Cambio'!$C$5 (which stays 3 for every other sheet).
- Rows priced as a shared/bundled total (quantity == 1: hotel, SIM card,
  group transfers) are cleared to a $0 placeholder, since that total isn't
  known for 4 people yet — same for the cruise cabin fare specifically
  (see CLEAR_ROWS), since cabin fares are priced per-occupancy, not
  linearly per head (a quad cabin's real rate isn't 4x a solo rate).
- Placeholder $0 rows (N/A, "Incluida en el crucero", "Día de navegación")
  are left untouched either way — nothing to clear or scale.

Editing style matches duplicate_option.py / manage_item.py / generate_data.py:
raw zip/XML string surgery on just the rows that change, not a full-document
XML parse.

Run once from the project root: python3 scripts/duplicate_option_4p.py
"""
from __future__ import annotations

import re
import shutil
import zipfile
from xml.etree import ElementTree as ET

ROOT_WORKBOOK = "Europa2027_Cotizacion_plan_completo (1).xlsx"

SOURCE_SHEET_NUM = 10
SOURCE_SHEET_ID = "10"
NEW_SHEET_NUM = 13
NEW_SHEET_ID = "13"
NEW_DRAWING_NUM = 13
NEW_RID = "rId17"
NEW_SHEET_NAME = "Crucero 4P"
NEW_HEADCOUNT = 4

# Row numbers in the source sheet whose price must be cleared regardless of
# quantity: the cruise cabin fare (priced per-occupancy, not flat per-head)
# plus every quantity=1 bundled/group-total row. Same rows as the 2-person
# duplicate — both are duplicating the same source sheet (sheet10).
CLEAR_ROWS = {5, 9, 10, 15, 16, 27, 31}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cell_value_text(row_xml: str, col: str, row_num: int) -> str | None:
    m = re.search(rf'<c r="{col}{row_num}"[^>]*>.*?<v>([^<]*)</v>', row_xml, re.S)
    return m.group(1) if m else None


def set_cell_value(row_xml: str, col: str, row_num: int, new_value: str) -> str:
    pattern = re.compile(rf'(<c r="{col}{row_num}"[^>]*>(?:<f[^>]*?(?:/>|>.*?</f>))?)<v>[^<]*</v>', re.S)
    replacement = rf'\g<1><v>{new_value}</v>'
    new_xml, count = pattern.subn(replacement, row_xml)
    assert count == 1, f"{col}{row_num}: expected 1 substitution, got {count}"
    return new_xml


def set_k_formula(row_xml: str, row_num: int, formula_text: str) -> str:
    pattern = re.compile(rf'(<c r="K{row_num}"[^>]*><f[^>]*>)[^<]*(</f>)')
    new_xml, count = pattern.subn(rf'\g<1>{formula_text}\g<2>', row_xml)
    assert count == 1, f"K{row_num}: expected 1 formula substitution, got {count}"
    return new_xml


def set_l_string_index(row_xml: str, row_num: int, idx: int) -> str:
    # L cell already has a shared-string value: just swap the index.
    pattern = re.compile(rf'(<c r="L{row_num}"[^>]*t="s"[^>]*><v>)[^<]*(</v>)')
    new_xml, count = pattern.subn(rf'\g<1>{idx}\g<2>', row_xml)
    if count == 1:
        return new_xml
    # L cell is empty/self-closing (no note previously): turn it into a
    # string-typed cell with one.
    pattern_empty = re.compile(rf'<c r="L{row_num}"([^>]*)/>')
    new_xml, count = pattern_empty.subn(rf'<c r="L{row_num}"\g<1> t="s"><v>{idx}</v></c>', row_xml)
    assert count == 1, f"L{row_num}: expected 1 substitution, got {count}"
    return new_xml


def main():
    with zipfile.ZipFile(ROOT_WORKBOOK) as z:
        files = {n: z.read(n) for n in z.namelist()}

    # --- 1-3. New worksheet + rels + drawing parts (verbatim copies) ---
    files[f"xl/worksheets/sheet{NEW_SHEET_NUM}.xml"] = files[f"xl/worksheets/sheet{SOURCE_SHEET_NUM}.xml"]
    src_rels = files[f"xl/worksheets/_rels/sheet{SOURCE_SHEET_NUM}.xml.rels"].decode("utf-8")
    files[f"xl/worksheets/_rels/sheet{NEW_SHEET_NUM}.xml.rels"] = src_rels.replace(
        f"drawing{SOURCE_SHEET_NUM}.xml", f"drawing{NEW_DRAWING_NUM}.xml"
    ).encode("utf-8")
    files[f"xl/drawings/drawing{NEW_DRAWING_NUM}.xml"] = files[f"xl/drawings/drawing{SOURCE_SHEET_NUM}.xml"]

    # --- 4. [Content_Types].xml ---
    ct = files["[Content_Types].xml"].decode("utf-8")
    ct = ct.replace(
        "</Types>",
        f'<Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" PartName="/xl/worksheets/sheet{NEW_SHEET_NUM}.xml"/>'
        f'<Override ContentType="application/vnd.openxmlformats-officedocument.drawing+xml" PartName="/xl/drawings/drawing{NEW_DRAWING_NUM}.xml"/>'
        "</Types>",
    )
    files["[Content_Types].xml"] = ct.encode("utf-8")

    # --- 5. xl/_rels/workbook.xml.rels ---
    wbrels = files["xl/_rels/workbook.xml.rels"].decode("utf-8")
    wbrels = wbrels.replace(
        "</Relationships>",
        f'<Relationship Id="{NEW_RID}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{NEW_SHEET_NUM}.xml"/></Relationships>',
    )
    files["xl/_rels/workbook.xml.rels"] = wbrels.encode("utf-8")

    # --- 6. xl/workbook.xml — insert right after the existing 2-person
    # cruise variant so the three cruise sheets stay grouped together. ---
    wb = files["xl/workbook.xml"].decode("utf-8")
    anchor = '<sheet state="visible" name="Crucero 2P" sheetId="12" r:id="rId16"/>'
    assert anchor in wb, "2-person cruise sheet entry not found in workbook.xml"
    new_entry = f'<sheet state="visible" name="{NEW_SHEET_NAME}" sheetId="{NEW_SHEET_ID}" r:id="{NEW_RID}"/>'
    wb = wb.replace(anchor, anchor + new_entry)
    files["xl/workbook.xml"] = wb.encode("utf-8")

    # --- 7. Shared strings: append the one new "pending" note text. Real
    # XML parsing (not a naive <si><t>...</t></si> regex — see
    # duplicate_option.py's docstring for why that undercounts). ---
    ss_raw = files["xl/sharedStrings.xml"].decode("utf-8")
    ss_ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    ss_root = ET.fromstring(ss_raw)
    existing_strings = [
        "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
        for item in ss_root.findall("x:si", ss_ns)
    ]
    pending_text = f"Pendiente cotizar para {NEW_HEADCOUNT} personas"
    if pending_text in existing_strings:
        pending_idx = existing_strings.index(pending_text)
        new_entries_count = 0
    else:
        pending_idx = len(existing_strings)
        ss_raw = ss_raw.replace("</sst>", f"<si><t>{esc(pending_text)}</t></si></sst>")
        new_entries_count = 1

    # --- 8. Apply the pricing transformation to the new sheet, row by row ---
    sheet_xml = files[f"xl/worksheets/sheet{NEW_SHEET_NUM}.xml"].decode("utf-8")
    changed_rows = []
    cleared_count = 0

    for row_match in list(re.finditer(r'<row r="(\d+)"[^>]*>.*?</row>', sheet_xml, re.S)):
        rn = int(row_match.group(1))
        if rn < 5:
            continue
        row_xml = row_match.group(0)
        d_val = cell_value_text(row_xml, "D", rn)
        if d_val is None:
            continue
        f_val = cell_value_text(row_xml, "F", rn)
        g_val = cell_value_text(row_xml, "G", rn)
        if f_val is None or g_val is None:
            continue
        unit = float(f_val)
        qty = float(g_val)

        new_row_xml = row_xml
        if rn in CLEAR_ROWS:
            new_row_xml = set_cell_value(new_row_xml, "F", rn, "0.0")
            new_row_xml = set_cell_value(new_row_xml, "H", rn, "0")
            new_row_xml = set_cell_value(new_row_xml, "J", rn, "0")
            new_row_xml = set_k_formula(new_row_xml, rn, f"IFERROR(J{rn}/{NEW_HEADCOUNT},0)")
            new_row_xml = set_cell_value(new_row_xml, "K", rn, "0")
            new_row_xml = set_l_string_index(new_row_xml, rn, pending_idx)
            changed_rows.append((rn, d_val, "cleared"))
            cleared_count += 1
        elif qty == 3.0 and unit != 0:
            rate_val = cell_value_text(row_xml, "I", rn)
            rate = float(rate_val) if rate_val else 1.0
            new_total_original = unit * NEW_HEADCOUNT
            new_total_cop = new_total_original * rate
            new_per_person = new_total_cop / NEW_HEADCOUNT
            new_row_xml = set_cell_value(new_row_xml, "G", rn, f"{NEW_HEADCOUNT}.0")
            new_row_xml = set_cell_value(new_row_xml, "H", rn, str(new_total_original))
            new_row_xml = set_cell_value(new_row_xml, "J", rn, str(new_total_cop))
            new_row_xml = set_k_formula(new_row_xml, rn, f"IFERROR(J{rn}/{NEW_HEADCOUNT},0)")
            new_row_xml = set_cell_value(new_row_xml, "K", rn, str(new_per_person))
            changed_rows.append((rn, d_val, f"unit={unit} qty 3->{NEW_HEADCOUNT}"))

        if new_row_xml != row_xml:
            sheet_xml = sheet_xml.replace(row_xml, new_row_xml, 1)

    files[f"xl/worksheets/sheet{NEW_SHEET_NUM}.xml"] = sheet_xml.encode("utf-8")

    # --- 9. Finalize shared strings count/uniqueCount ---
    m = re.search(r'<sst[^>]*count="(\d+)" uniqueCount="(\d+)"', ss_raw)
    count, unique = int(m.group(1)), int(m.group(2))
    ss_raw = ss_raw.replace(
        f'count="{count}" uniqueCount="{unique}"',
        f'count="{count + cleared_count}" uniqueCount="{unique + new_entries_count}"',
        1,
    )
    files["xl/sharedStrings.xml"] = ss_raw.encode("utf-8")

    # --- 10. Repackage ---
    new_path = ROOT_WORKBOOK + ".new"
    with zipfile.ZipFile(ROOT_WORKBOOK) as zin, zipfile.ZipFile(new_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            zout.writestr(item, files[item])
        for extra in (
            f"xl/worksheets/sheet{NEW_SHEET_NUM}.xml",
            f"xl/worksheets/_rels/sheet{NEW_SHEET_NUM}.xml.rels",
            f"xl/drawings/drawing{NEW_DRAWING_NUM}.xml",
        ):
            if extra not in zin.namelist():
                zout.writestr(extra, files[extra])
    shutil.move(new_path, ROOT_WORKBOOK)

    print(f"Created sheet{NEW_SHEET_NUM}.xml ({NEW_SHEET_NAME!r}, sheetId={NEW_SHEET_ID}, {NEW_RID}) as a copy of sheet{SOURCE_SHEET_NUM}.xml")
    print(f"Applied {len(changed_rows)} row changes:")
    for rn, title, kind in changed_rows:
        print(f"  row {rn}: {title!r} -> {kind}")


if __name__ == "__main__":
    main()
