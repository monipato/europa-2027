"""One-off: duplicate the 'Crucero' (Solo crucero) sheet into a new sheet
for a 2-person version of that same itinerary, then apply the pricing
transformation agreed with the user:

- Rows priced per-person (quantity == 3, the current headcount) keep their
  unit price unchanged and just get quantity -> 2 — a flight seat, a tour
  ticket, an insurance policy costs the same per person regardless of group
  size. Their K-column formula is rewritten to divide by a literal 2
  instead of the shared 'Tasas de Cambio'!$C$5 (which stays 3 for every
  other sheet).
- Rows priced as a shared/bundled total (quantity == 1: hotel, SIM card,
  group transfers) are cleared to a $0 placeholder, since that total isn't
  known for 2 people yet — same treatment for the cruise cabin fare
  specifically (see CLEAR_ROWS), even though it's nominally "per person"
  quantity=3, because cabin fares are priced per-occupancy, not linearly
  per head, so keeping the triple-share rate would understate a double
  cabin's real price.
- Placeholder $0 rows (N/A, "Incluida en el crucero", "Día de navegación")
  are left untouched either way — nothing to clear or scale.

Editing style matches manage_item.py / generate_data.py: raw zip/XML string
surgery on just the rows that change, not a full-document XML parse — this
551KB sheet declares several namespaces (x14ac, mc, mv, ...) used outside
the rows this script touches, and a parse/reserialize round-trip risks
silently mangling parts never inspected. Every edit here is a targeted
regex substitution inside one <row>...</row> block at a time.

Run once from the project root: python3 scripts/duplicate_option.py
"""
from __future__ import annotations

import re
import shutil
import zipfile
from xml.etree import ElementTree as ET

ROOT_WORKBOOK = "Europa2027_Cotizacion_plan_completo (1).xlsx"

SOURCE_SHEET_NUM = 10
SOURCE_SHEET_ID = "10"
NEW_SHEET_NUM = 12
NEW_SHEET_ID = "12"
NEW_DRAWING_NUM = 12
NEW_RID = "rId16"
NEW_SHEET_NAME = "Crucero 2P"

# Row numbers in the source sheet whose price must be cleared regardless of
# quantity: the cruise cabin fare (priced per-occupancy, not flat per-head)
# plus every quantity=1 bundled/group-total row.
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

    # --- 6. xl/workbook.xml ---
    wb = files["xl/workbook.xml"].decode("utf-8")
    anchor = f'<sheet state="visible" name="Crucero" sheetId="{SOURCE_SHEET_ID}" r:id="rId14"/>'
    assert anchor in wb, "source sheet entry not found in workbook.xml"
    new_entry = f'<sheet state="visible" name="{NEW_SHEET_NAME}" sheetId="{NEW_SHEET_ID}" r:id="{NEW_RID}"/>'
    wb = wb.replace(anchor, anchor + new_entry)
    files["xl/workbook.xml"] = wb.encode("utf-8")

    # --- 7. Shared strings: append the one new "pending" note text.
    # Use real XML parsing (like generate_data.py's shared_strings() and
    # manage_item.py's Workbook._parse_shared_strings) to count entries —
    # not a naive "<si><t>...</t></si>" regex: some entries use
    # <t xml:space="preserve">, which that pattern silently skips, which
    # would miscount the total and point the new index at an existing,
    # unrelated string instead of the new one. ---
    ss_raw = files["xl/sharedStrings.xml"].decode("utf-8")
    ss_ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    ss_root = ET.fromstring(ss_raw)
    existing_strings = [
        "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
        for item in ss_root.findall("x:si", ss_ns)
    ]
    pending_text = "Pendiente cotizar para 2 personas"
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
            new_row_xml = set_k_formula(new_row_xml, rn, f"IFERROR(J{rn}/2,0)")
            new_row_xml = set_cell_value(new_row_xml, "K", rn, "0")
            new_row_xml = set_l_string_index(new_row_xml, rn, pending_idx)
            changed_rows.append((rn, d_val, "cleared"))
            cleared_count += 1
        elif qty == 3.0 and unit != 0:
            rate_val = cell_value_text(row_xml, "I", rn)
            rate = float(rate_val) if rate_val else 1.0
            new_total_original = unit * 2
            new_total_cop = new_total_original * rate
            new_per_person = new_total_cop / 2
            new_row_xml = set_cell_value(new_row_xml, "G", rn, "2.0")
            new_row_xml = set_cell_value(new_row_xml, "H", rn, str(new_total_original))
            new_row_xml = set_cell_value(new_row_xml, "J", rn, str(new_total_cop))
            new_row_xml = set_k_formula(new_row_xml, rn, f"IFERROR(J{rn}/2,0)")
            new_row_xml = set_cell_value(new_row_xml, "K", rn, str(new_per_person))
            changed_rows.append((rn, d_val, f"unit={unit} qty 3->2"))

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
