"""One-off: duplicate the 'Cotización' sheet ("1 mes por Europa", sheet4)
into a new sheet as the starting point for a Milán-anchored variant of the
same 29-day itinerary — same shape (city stay, then París, Barcelona, the
Mediterranean cruise, Roma, Praga, Berlín, Múnich), just with the opening
Zürich segment swapped for Milán.

Same pattern as duplicate_option_venice.py: a straight verbatim copy, no
pricing transform (headcount stays 3) — the Zürich-specific rows (flight,
transfer, hotel, meals, tours, the Zürich→París leg) are re-pointed to
Milán content afterward via individual scripts/manage_item.py calls,
reusing real numbers already quoted for the "Italia" option where the
itinerary overlaps (same hotel, same Alpine Wonders tour, same Duomo
ticket).

Run once from the project root: python3 scripts/duplicate_option_milan_europa.py
"""
from __future__ import annotations

import shutil
import zipfile

ROOT_WORKBOOK = "Europa2027_Cotizacion_plan_completo (1).xlsx"

SOURCE_SHEET_NUM = 4
NEW_SHEET_NUM = 15
NEW_SHEET_ID = "15"
NEW_DRAWING_NUM = 15
NEW_RID = "rId19"
NEW_SHEET_NAME = "Cotizacion Milan"


def main():
    with zipfile.ZipFile(ROOT_WORKBOOK) as z:
        files = {n: z.read(n) for n in z.namelist()}

    files[f"xl/worksheets/sheet{NEW_SHEET_NUM}.xml"] = files[f"xl/worksheets/sheet{SOURCE_SHEET_NUM}.xml"]
    src_rels = files[f"xl/worksheets/_rels/sheet{SOURCE_SHEET_NUM}.xml.rels"].decode("utf-8")
    files[f"xl/worksheets/_rels/sheet{NEW_SHEET_NUM}.xml.rels"] = src_rels.replace(
        f"drawing{SOURCE_SHEET_NUM}.xml", f"drawing{NEW_DRAWING_NUM}.xml"
    ).encode("utf-8")
    files[f"xl/drawings/drawing{NEW_DRAWING_NUM}.xml"] = files[f"xl/drawings/drawing{SOURCE_SHEET_NUM}.xml"]

    ct = files["[Content_Types].xml"].decode("utf-8")
    ct = ct.replace(
        "</Types>",
        f'<Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" PartName="/xl/worksheets/sheet{NEW_SHEET_NUM}.xml"/>'
        f'<Override ContentType="application/vnd.openxmlformats-officedocument.drawing+xml" PartName="/xl/drawings/drawing{NEW_DRAWING_NUM}.xml"/>'
        "</Types>",
    )
    files["[Content_Types].xml"] = ct.encode("utf-8")

    wbrels = files["xl/_rels/workbook.xml.rels"].decode("utf-8")
    wbrels = wbrels.replace(
        "</Relationships>",
        f'<Relationship Id="{NEW_RID}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{NEW_SHEET_NUM}.xml"/></Relationships>',
    )
    files["xl/_rels/workbook.xml.rels"] = wbrels.encode("utf-8")

    wb = files["xl/workbook.xml"].decode("utf-8")
    anchor = '<sheet state="visible" name="Crucero Milan" sheetId="14" r:id="rId18"/>'
    assert anchor in wb, "anchor sheet entry not found in workbook.xml"
    new_entry = f'<sheet state="visible" name="{NEW_SHEET_NAME}" sheetId="{NEW_SHEET_ID}" r:id="{NEW_RID}"/>'
    wb = wb.replace(anchor, anchor + new_entry)
    files["xl/workbook.xml"] = wb.encode("utf-8")

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
