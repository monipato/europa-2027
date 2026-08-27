"""Build the app's itinerary data from the quote workbook.

Run from the project root:
    python3 scripts/generate_data.py

This is the *only* place that reads the Excel file. It parses the .xlsx
directly as a zip of XML (no external dependency), turns each quote line
into a per-option, per-day itinerary, and writes the result to
src/data/generated/itinerary.generated.ts — a plain data file the React app
imports and renders directly. Nothing in src/ talks to the spreadsheet.

Re-run this script after editing the workbook. The generated file is
checked in (so the app builds without Python installed) but should never be
hand-edited — fix the workbook or this script instead, then regenerate.
"""
from __future__ import annotations

import html
import json
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "Europa2027_Cotizacion_plan_completo (1).xlsx"
ITINERARY_OUTPUT = ROOT / "src" / "data" / "generated" / "itinerary.generated.ts"
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MONTH_ORDER = {m.upper(): i for i, m in enumerate(MONTHS_ES)}
EXCEL_EPOCH = date(1899, 12, 30)

# App-level category used across the UI, mapped from the Excel category text.
CATEGORY_BY_EXCEL = {
    "Vuelos y Trenes": "Transporte", "Traslados": "Transporte", "Alojamiento": "Alojamiento",
    "Comidas": "Comida", "Tours y Excursiones": "Tours", "Crucero": "Crucero",
    "Seguro de Viaje": "Seguro", "Otros y Extras": "Otros",
}

def unsplash(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=900&q=80"


# (country, emoji, hero image URL) per canonical city name shown in the itinerary.
# Photo URLs are checked into the generated output, so they need to keep resolving
# indefinitely — if one ever 404s, replace it (any stable image host is fine, not
# just Unsplash) rather than leaving a broken image.
CITY_INFO = {
    "Zúrich": ("Suiza", "🇨🇭", unsplash("photo-1527668752968-14dc70a27c95")),
    "París": ("Francia", "🇫🇷", unsplash("photo-1502602898657-3e91760cbb34")),
    "Barcelona": ("España", "🇪🇸", unsplash("photo-1539037116277-4db20889f2d4")),
    "La Spezia": ("Italia", "🇮🇹", unsplash("photo-1533104816931-20fa691ff6ca")),
    "Salerno": ("Italia", "🇮🇹", unsplash("photo-1530789253388-582c481c54b0")),
    # Wikimedia Commons, not Unsplash: the "Greeting to the Sun" / Sea Organ waterfront at
    # sunset — the original Unsplash ID here 404'd, and Zadar's own city photos are thin on
    # Unsplash. https://commons.wikimedia.org/wiki/File:Sunset_over_the_Adriatic_Sea_as_seen_from_the_Sea_Organ_in_Zadar_(48670423612).jpg
    "Zadar": ("Croacia", "🇭🇷", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Sunset_over_the_Adriatic_Sea_as_seen_from_the_Sea_Organ_in_Zadar_%2848670423612%29.jpg/960px-Sunset_over_the_Adriatic_Sea_as_seen_from_the_Sea_Organ_in_Zadar_%2848670423612%29.jpg"),
    "Venecia": ("Italia", "🇮🇹", unsplash("photo-1520175480921-4edfa2983e0f")),
    "Roma": ("Italia", "🇮🇹", unsplash("photo-1552832230-c0197dd311b5")),
    "Praga": ("República Checa", "🇨🇿", unsplash("photo-1541849546-216549ae216d")),
    "Berlín": ("Alemania", "🇩🇪", unsplash("photo-1560969184-10fe8719e047")),
    "Múnich": ("Alemania", "🇩🇪", unsplash("photo-1595867818082-083862f3d630")),
    "En el mar": ("Mediterráneo", "🛳️", unsplash("photo-1544551763-46a013bb70d5")),
}

# A city can appear on several itinerary days. Use a small curated pool so the
# hero does not repeat the same background on every occurrence. The duck sticker
# is independent and remains assigned by the UI.
CITY_IMAGE_POOLS = {
    "Zúrich": [
        unsplash("photo-1527668752968-14dc70a27c95"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Zurich_after_sunset.jpg/960px-Zurich_after_sunset.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/48/Lake_Z%C3%BCrich_from_Uetliberg.jpg/960px-Lake_Z%C3%BCrich_from_Uetliberg.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Z%C3%BCrich_view_Quaibr%C3%BCcke_20200702.jpg/960px-Z%C3%BCrich_view_Quaibr%C3%BCcke_20200702.jpg",
    ],
    "París": [unsplash("photo-1502602898657-3e91760cbb34"), unsplash("photo-1499856871958-5b9627545d1a"), unsplash("photo-1503917988258-f87a78e3c995")],
    "Barcelona": [unsplash("photo-1539037116277-4db20889f2d4"), unsplash("photo-1583422409516-2895a77efded"), unsplash("photo-1523531294919-4bcd7c65e216")],
    "La Spezia": [
        unsplash("photo-1533104816931-20fa691ff6ca"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Vernazza%2C_Cinque_Terre_%28panorama%29.jpg/960px-Vernazza%2C_Cinque_Terre_%28panorama%29.jpg",
    ],
    "Salerno": [
        unsplash("photo-1530789253388-582c481c54b0"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Positano_at_dusk%2C_Amalfi_Coast%2C_Italy.jpg/960px-Positano_at_dusk%2C_Amalfi_Coast%2C_Italy.jpg",
    ],
    "Zadar": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Sunset_over_the_Adriatic_Sea_as_seen_from_the_Sea_Organ_in_Zadar_%2848670423612%29.jpg/960px-Sunset_over_the_Adriatic_Sea_as_seen_from_the_Sea_Organ_in_Zadar_%2848670423612%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/The_Sea_Organ_on_the_waterfront_of_Zadar%2C_Croatia_%2848607630256%29.jpg/960px-The_Sea_Organ_on_the_waterfront_of_Zadar%2C_Croatia_%2848607630256%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Zadar_%2848947016376%29.jpg/960px-Zadar_%2848947016376%29.jpg",
    ],
    "Venecia": [unsplash("photo-1520175480921-4edfa2983e0f"), unsplash("photo-1514890547357-a9ee288728e0"), unsplash("photo-1523906834658-6e24ef2386f9")],
    "Roma": [unsplash("photo-1552832230-c0197dd311b5"), unsplash("photo-1529260830199-42c24126f198"), unsplash("photo-1531572753322-ad063cecc140")],
    "Praga": [
        unsplash("photo-1541849546-216549ae216d"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Charles_Bridge_at_Sunset%2C_Prague_%2850489016846%29.jpg/960px-Charles_Bridge_at_Sunset%2C_Prague_%2850489016846%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Prague_Old_Town_2021_13.jpg/960px-Prague_Old_Town_2021_13.jpg",
    ],
    "Berlín": [
        unsplash("photo-1560969184-10fe8719e047"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Skyline_Berlin.jpg/960px-Skyline_Berlin.jpg",
        unsplash("photo-1528728329032-2972f65dfb3f"),
    ],
    "Múnich": [
        unsplash("photo-1595867818082-083862f3d630"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Vista_panor%C3%A1mica_desde_Olympiapark%2C_M%C3%BAnich%2C_Alemania_2012-04-28%2C_DD_03.JPG/960px-Vista_panor%C3%A1mica_desde_Olympiapark%2C_M%C3%BAnich%2C_Alemania_2012-04-28%2C_DD_03.JPG",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/Munich%2C_Nuevo_Ayuntamiento_01.jpg/960px-Munich%2C_Nuevo_Ayuntamiento_01.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Historische_Altstadt_Muenchen_01.JPG/960px-Historische_Altstadt_Muenchen_01.JPG",
    ],
    "En el mar": [
        unsplash("photo-1544551763-46a013bb70d5"),
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/db/Cruising_into_the_sunset_%28Explored%29_-_Flickr_-_M_McBey.jpg/960px-Cruising_into_the_sunset_%28Explored%29_-_Flickr_-_M_McBey.jpg",
        unsplash("photo-1500375592092-40eb2168fd21"),
    ],
}


def image_for_day(city: str, occurrence: int) -> str:
    pool = CITY_IMAGE_POOLS.get(city)
    if pool:
        return pool[occurrence % len(pool)]
    return CITY_INFO.get(city, ("Europa", "🌍", unsplash("photo-1436491865332-7a61a109cc05")))[2]

# Ordered most-specific-first: substring match against a line's "place" text.
CITY_ALIASES = [
    ("La Spezia", "La Spezia"), ("Civitavecchia", "Roma"), ("Salerno", "Salerno"), ("Zadar", "Zadar"),
    ("Rávena", "Venecia"), ("Ravena", "Venecia"), ("Venecia", "Venecia"),
    ("Zúrich", "Zúrich"), ("Zurich", "Zúrich"),
    ("París", "París"), ("Paris", "París"),
    ("Barcelona", "Barcelona"), ("Roma", "Roma"), ("Praga", "Praga"),
    ("Berlín", "Berlín"), ("Berlin", "Berlín"), ("Múnich", "Múnich"), ("Munich", "Múnich"),
    ("Navegaci", "En el mar"),
]


def shared_strings(book: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root.findall("x:si", NS)]


def value(cell: ET.Element, strings: list[str]) -> str:
    node = cell.find("x:v", NS)
    raw = "" if node is None else node.text or ""
    if cell.attrib.get("t") == "s" and raw:
        return strings[int(raw)]
    return raw


def number(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def capitalize_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def is_placeholder(title: str) -> bool:
    """'N/A' rows (e.g. 'N/A (día de navegación)') are blank markers with no
    real content — unlike a genuine zero-cost item ('Tour a pie gratis'), they
    carry no information and shouldn't be listed as an expense."""
    return title.strip().upper().startswith("N/A")


def excel_serial_to_text(serial: float) -> str:
    d = EXCEL_EPOCH + timedelta(days=int(serial))
    return f"{d.day} {MONTHS_ES[d.month - 1]} {d.year}"


def normalize_date(raw: str) -> str:
    """Some sheets store the date column as a raw Excel serial number
    instead of formatted text (e.g. '46508.0'). Convert those to the same
    'D Mon YYYY' text the other sheets already use; leave text (including
    date ranges like '3 – 6 May (3 noches)') untouched."""
    stripped = raw.strip()
    if re.fullmatch(r"\d+(\.0)?", stripped):
        return excel_serial_to_text(float(stripped))
    return raw


def day_key(raw_date: str) -> str | None:
    """Extract a 'DD MON' sort/group key from the start of a date field.
    Returns None for dateless rows (e.g. 'Contingencia')."""
    match = re.search(r"(\d{1,2})\s*[–\-]?\s*(?:\d{1,2}\s*)?(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)", raw_date, re.IGNORECASE)
    if not match:
        return None
    day_num, month = match.group(1), match.group(2)
    return f"{int(day_num):02d} {month.upper()}"


def read_rows(sheet_number: int, option_name: str) -> list[dict[str, object]]:
    with zipfile.ZipFile(WORKBOOK) as book:
        strings = shared_strings(book)
        sheet = ET.fromstring(book.read(f"xl/worksheets/sheet{sheet_number}.xml"))
        rows: list[dict[str, object]] = []
        headers: list[str] = []
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            cells = {cell.attrib["r"]: value(cell, strings) for cell in row.findall("x:c", NS)}
            values = [cells.get(f"{column}{row.attrib['r']}", "") for column in "ABCDEFGHIJKLM"]
            if values[0] == "Categoría" and values[4] == "Moneda":
                headers = values
                continue
            if not headers or values[0] not in {"Vuelos y Trenes", "Traslados", "Alojamiento", "Crucero", "Tours y Excursiones", "Comidas", "Seguro de Viaje", "Otros y Extras"}:
                continue
            if not values[3].strip():
                # Blank continuation row left over from merged-cell formatting — no real line item.
                continue
            raw_date = normalize_date(values[2])
            # Seguro de Viaje's date is a coverage period (e.g. "29 Abr – 30 May ... cobertura"),
            # not an itinerary stop — treat it as dateless like the other trip-wide costs so it
            # doesn't create a phantom day before the trip actually starts.
            is_trip_wide = values[0] == "Seguro de Viaje"
            rows.append({
                "option": option_name, "category": values[0], "place": values[1], "date": raw_date,
                "dayKey": None if is_trip_wide else day_key(raw_date), "title": capitalize_first(values[3]), "currency": values[4] or "COP",
                "unitOriginal": number(values[5]), "quantity": number(values[6]),
                "totalOriginal": number(values[7]), "rateToCop": number(values[8]),
                "totalCop": number(values[9]), "perPersonCop": number(values[10]),
                "note": html.unescape(values[11]),
            })
        return rows


def ts(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_rates() -> list[dict[str, object]]:
    """Read the 'Tasas de Cambio' sheet (sheet3): code, label, symbol, rate to COP."""
    with zipfile.ZipFile(WORKBOOK) as book:
        strings = shared_strings(book)
        sheet = ET.fromstring(book.read("xl/worksheets/sheet3.xml"))
        rates: list[dict[str, object]] = []
        update_date = ""
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            cells = {cell.attrib["r"]: value(cell, strings) for cell in row.findall("x:c", NS)}
            values = [cells.get(f"{column}{row.attrib['r']}", "") for column in "ABCDE"]
            if values[1] == "Fecha de actualización de tasas":
                update_date = values[2]
            if values[1] in {"EUR", "CHF", "CZK", "USD"}:
                rates.append({"code": values[1], "label": values[2], "symbol": values[3], "rate": number(values[4])})
        return rates, update_date


def day_sort_key(key: str) -> tuple[int, int]:
    day_str, month_str = key.split()
    return (MONTH_ORDER[month_str], int(day_str))


def extract_city(place: str, category: str) -> str | None:
    if category == "Crucero":
        return None
    for alias, city in CITY_ALIASES:
        if alias.lower() in place.lower():
            return city
    return None


def day_city(lines: list[dict[str, object]], fallback: str | None) -> str:
    lodging = [line for line in lines if line["category"] == "Alojamiento"]
    if lodging:
        city = extract_city(str(lodging[0]["place"]), "Alojamiento")
        if city:
            return city
    for line in lines:
        city = extract_city(str(line["place"]), str(line["category"]))
        if city:
            return city
    return fallback or "Europa"


def day_title(lines: list[dict[str, object]], city: str, is_first: bool, is_last: bool, is_embark: bool) -> str:
    if is_embark:
        return f"Embarque en {city}"
    if is_last:
        return "Vuelo de regreso"
    # A hotel check-in this day means the traveler has actually arrived — prioritize that framing
    # even over a same-day tour, and even on a day other than the trip's first (a long-haul outbound
    # flight can depart one calendar day and land/check in the next; see is_first below for that case).
    if any(line["category"] == "Alojamiento" for line in lines):
        return f"Llegada a {city}"
    if is_first:
        # The trip's first day with no hotel line yet: this is a pure travel day (e.g. an overnight
        # flight departing today and landing — and checking into a hotel — the next calendar day).
        return f"Vuelo a {city}"
    if city == "En el mar":
        return "Día de navegación"
    tours = [line for line in lines if line["category"] == "Tours y Excursiones" and str(line["title"]).strip() and not is_placeholder(str(line["title"]))]
    if tours:
        return str(tours[0]["title"])
    return f"Día en {city}"


LINK_RE = re.compile(r"https?://\S+")


def to_expense(line: dict[str, object]) -> dict[str, object]:
    amount = line["perPersonCop"] or 0
    rate = line["rateToCop"]
    currency = str(line["currency"])
    original_amount = amount / rate if currency != "COP" and rate else amount
    note = str(line["note"])
    link_match = LINK_RE.search(note)
    link = link_match.group(0).rstrip(".,)") if link_match else None
    clean_note = LINK_RE.sub("", note).strip(" .|")
    return {
        "category": CATEGORY_BY_EXCEL[str(line["category"])],
        "title": line["title"], "amount": amount, "originalAmount": original_amount,
        "currency": currency, "note": clean_note, "place": line["place"], "date": line["date"], "link": link,
    }


def build_itinerary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    dateless = [row for row in rows if row["dayKey"] is None]
    dated = [row for row in rows if row["dayKey"] is not None]
    keys = sorted({str(row["dayKey"]) for row in dated}, key=day_sort_key)
    current_city: str | None = None
    city_occurrences: dict[str, int] = {}
    days = []
    for index, key in enumerate(keys):
        # `lines` (unfiltered) drives city/title detection and day continuity — a day still
        # gets a card even if every line on it is zero-cost. Zero-value and "N/A" placeholder
        # lines are only dropped from what's actually displayed as an expense.
        lines = [row for row in dated if row["dayKey"] == key]
        if index == 0:
            lines = lines + dateless
        city = day_city(lines, current_city)
        current_city = city
        country, emoji, _ = CITY_INFO.get(city, ("Europa", "🌍", unsplash("photo-1436491865332-7a61a109cc05")))
        image_url = image_for_day(city, city_occurrences.get(city, 0))
        city_occurrences[city] = city_occurrences.get(city, 0) + 1
        is_embark = any(line["category"] == "Crucero" for line in lines)
        is_first = index == 0
        display_lines = [line for line in lines if (line["perPersonCop"] or 0) != 0 and not is_placeholder(str(line["title"]))]
        days.append({
            "dayKey": key, "city": city, "country": country, "emoji": emoji,
            "image": image_url,
            "title": day_title(lines, city, is_first, index == len(keys) - 1, is_embark),
            "dayKind": "flight" if is_first else ("embark" if is_embark else None),
            "expenses": [to_expense(line) for line in display_lines],
        })
    return days


def build_option(name: str, dates_label: str, color: str, description: str, rows: list[dict[str, object]]) -> dict[str, object]:
    itinerary = build_itinerary(rows)
    total = sum(line["perPersonCop"] or 0 for line in rows)
    # "En el mar" is a placeholder for days at sea, not a real destination —
    # leave it out of the displayed route (the option card's city list).
    route: list[str] = []
    for day in itinerary:
        if day["city"] == "En el mar":
            continue
        if not route or route[-1] != day["city"]:
            route.append(day["city"])
    return {
        # "total" mirrors "perPerson": the UI only ever shows a per-person price (matching the
        # Excel's "Costo por persona" headline), there is no separate group-total display.
        "name": name, "dates": dates_label, "route": " · ".join(route), "days": len(itinerary),
        "total": round(total), "perPerson": round(total), "color": color, "description": description,
        "itinerary": itinerary,
    }


def main() -> None:
    sheets = [(4, "Completo"), (6, "Zúrich y Crucero"), (8, "Múnich y Crucero"), (10, "Solo crucero")]
    rows = [line for sheet, name in sheets for line in read_rows(sheet, name)]

    options_meta = [
        ("Completo", "30 abr – 30 may 2027", "#e9a34c", "El recorrido más completo por Europa", "Completo"),
        ("Solo crucero", "5 – 16 may 2027", "#7f9fc4", "Una escapada mediterránea", "Solo crucero"),
        ("Zúrich y Crucero", "30 abr – 16 may 2027", "#91b9a2", "Ciudad y mar en un solo viaje", "Zúrich y Crucero"),
        ("Múnich y Crucero", "30 abr – 16 may 2027", "#bf8e9a", "Alemania, España y Mediterráneo", "Múnich y Crucero"),
    ]
    options = [
        build_option(display_name, dates_label, color, description, [r for r in rows if r["option"] == sheet_option])
        for display_name, dates_label, color, description, sheet_option in options_meta
    ]
    rates, rates_updated = read_rates()

    ITINERARY_OUTPUT.write_text(
        "// Generated by scripts/generate_data.py — do not edit manually.\n"
        "export type GeneratedExpense = { category: string; title: string; amount: number; originalAmount: number; currency: string; note: string; place: string; date: string; link: string | null };\n"
        "export type GeneratedDay = { dayKey: string; city: string; country: string; emoji: string; image: string; title: string; dayKind: 'flight' | 'embark' | null; expenses: GeneratedExpense[] };\n"
        "export type GeneratedOption = { name: string; dates: string; route: string; days: number; total: number; perPerson: number; color: string; description: string; itinerary: GeneratedDay[] };\n"
        "export type ExchangeRate = { code: string; label: string; symbol: string; rate: number };\n"
        f"export const generatedOptions: GeneratedOption[] = {ts(options)};\n"
        f"export const exchangeRates: ExchangeRate[] = {ts(rates)};\n"
        f"export const ratesUpdatedAt: string = {ts(rates_updated)};\n",
        encoding="utf-8",
    )
    print(f"Generated {len(options)} itinerary options at {ITINERARY_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
