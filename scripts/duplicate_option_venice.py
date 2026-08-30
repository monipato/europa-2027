"""One-off: duplicate the 'Opción 4 (Múnich)' sheet (Múnich y Crucero) into
a new sheet as the starting point for "Venecia y Crucero" — same shape (a
pre-cruise city stay, then the same Barcelona-based Mediterranean cruise),
just with the anchor city swapped from Múnich to Venecia.

Unlike duplicate_option.py / duplicate_option_4p.py, this is a straight
verbatim copy with NO pricing transform (headcount stays 3, same as the
source) — the Múnich-specific rows (flight, transfer, hotel, tours, meals)
are re-pointed to Venecia content afterward via individual
scripts/manage_item.py calls, since that's genuinely new content (a
different flight route, a different hotel, different tours), not a
mechanical scale-by-headcount transform.

Editing style matches duplicate_option.py: raw zip/XML string surgery on
just the workbook-level parts that need a new sheet registered, not a
full-document XML parse.

Run once from the project root: python3 scripts/duplicate_option_venice.py
"""
from __future__ import annotations

import shutil
import zipfile

ROOT_WORKBOOK = "Europa2027_Cotizacion_plan_completo (1).xlsx"

SOURCE_SHEET_NUM = 8
NEW_SHEET_NUM = 14
NEW_SHEET_ID = "14"
NEW_DRAWING_NUM = 14
NEW_RID = "rId18"
NEW_SHEET_NAME = "Crucero Venecia"


def main():
    with zipfile.ZipFile(ROOT_WORKBOOK) as z:
        files = {n: z.read(n) for n in z.namelist()}

    # --- New worksheet + rels + drawing parts (verbatim copies) ---
    files[f"xl/worksheets/sheet{NEW_SHEET_NUM}.xml"] = files[f"xl/worksheets/sheet{SOURCE_SHEET_NUM}.xml"]
    src_rels = files[f"xl/worksheets/_rels/sheet{SOURCE_SHEET_NUM}.xml.rels"].decode("utf-8")
    files[f"xl/worksheets/_rels/sheet{NEW_SHEET_NUM}.xml.rels"] = src_rels.replace(
        f"drawing{SOURCE_SHEET_NUM}.xml", f"drawing{NEW_DRAWING_NUM}.xml"
    ).encode("utf-8")
    files[f"xl/drawings/drawing{NEW_DRAWING_NUM}.xml"] = files[f"xl/drawings/drawing{SOURCE_SHEET_NUM}.xml"]

    # --- [Content_Types].xml ---
    ct = files["[Content_Types].xml"].decode("utf-8")
    ct = ct.replace(
        "</Types>",
        f'<Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" PartName="/xl/worksheets/sheet{NEW_SHEET_NUM}.xml"/>'
        f'<Override ContentType="application/vnd.openxmlformats-officedocument.drawing+xml" PartName="/xl/drawings/drawing{NEW_DRAWING_NUM}.xml"/>'
        "</Types>",
    )
    files["[Content_Types].xml"] = ct.encode("utf-8")

    # --- xl/_rels/workbook.xml.rels ---
    wbrels = files["xl/_rels/workbook.xml.rels"].decode("utf-8")
    wbrels = wbrels.replace(
        "</Relationships>",
        f'<Relationship Id="{NEW_RID}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{NEW_SHEET_NUM}.xml"/></Relationships>',
    )
    files["xl/_rels/workbook.xml.rels"] = wbrels.encode("utf-8")

    # --- xl/workbook.xml — append at the very end of the sheet list. ---
    wb = files["xl/workbook.xml"].decode("utf-8")
    anchor = '<sheet state="hidden" name="Resumen Crucero" sheetId="11" r:id="rId15"/>'
    assert anchor in wb, "anchor sheet entry not found in workbook.xml"
    new_entry = f'<sheet state="visible" name="{NEW_SHEET_NAME}" sheetId="{NEW_SHEET_ID}" r:id="{NEW_RID}"/>'
    wb = wb.replace(anchor, anchor + new_entry)
    files["xl/workbook.xml"] = wb.encode("utf-8")

    # --- Repackage ---
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

    print(f"Created sheet{NEW_SHEET_NUM}.xml ({NEW_SHEET_NAME!r}, sheetId={NEW_SHEET_ID}, {NEW_RID}) as a verbatim copy of sheet{SOURCE_SHEET_NUM}.xml")


if __name__ == "__main__":
    main()
