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
    # Wikimedia Commons, not Unsplash — Milan's Duomo. https://commons.wikimedia.org/wiki/File:Milan_Cathedral_(Duomo_di_Milano).jpg
    "Milán": ("Italia", "🇮🇹", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Milan_Cathedral_%28Duomo_di_Milano%29.jpg/960px-Milan_Cathedral_%28Duomo_di_Milano%29.jpg"),
    # Wikimedia Commons, not Unsplash — Ponte Vecchio. https://commons.wikimedia.org/wiki/File:Panorama_of_the_Ponte_Vecchio_in_Florence,_Italy.jpg
    "Florencia": ("Italia", "🇮🇹", "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Panorama_of_the_Ponte_Vecchio_in_Florence%2C_Italy.jpg/960px-Panorama_of_the_Ponte_Vecchio_in_Florence%2C_Italy.jpg"),
    "En el mar": ("Mediterráneo", "🛳️", unsplash("photo-1544551763-46a013bb70d5")),
    "Orlando": ("Estados Unidos", "🇺🇸", unsplash("photo-1578089815509-ed664d5b66d3")),
}

# Approximate late April/May climate per city — sunrise/sunset, typical
# temperature range, a one-line weather label + emoji, and a short packing
# tip. These are seasonal averages (single value per city, not per exact
# date), same "aprox" framing as any travel-planning weather estimate this
# far ahead — not a real forecast. If a city is ever added to CITY_INFO
# without an entry here, DEFAULT_CLIMATE below is used instead of crashing.
CITY_CLIMATE = {
    "Zúrich": {"sunrise": "6:11 AM", "sunset": "8:35 PM", "temp": "6–16°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Chaqueta ligera y zapatos cómodos"},
    "París": {"sunrise": "6:25 AM", "sunset": "9:09 PM", "temp": "8–18°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Chaqueta ligera y paraguas compacto"},
    "Barcelona": {"sunrise": "6:40 AM", "sunset": "8:55 PM", "temp": "13–21°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Ropa ligera y gafas de sol"},
    "La Spezia": {"sunrise": "5:58 AM", "sunset": "8:35 PM", "temp": "12–20°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Zapatos cómodos para caminar"},
    "Salerno": {"sunrise": "5:45 AM", "sunset": "8:09 PM", "temp": "14–21°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Traje de baño y bloqueador solar"},
    "Zadar": {"sunrise": "5:32 AM", "sunset": "8:18 PM", "temp": "14–22°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Ropa cómoda y calzado para caminar"},
    "Venecia": {"sunrise": "5:38 AM", "sunset": "8:35 PM", "temp": "14–21°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Zapatos cómodos, el suelo puede estar húmedo"},
    "Roma": {"sunrise": "5:52 AM", "sunset": "8:20 PM", "temp": "13–23°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Ropa ligera y zapatos para caminar"},
    "Praga": {"sunrise": "5:08 AM", "sunset": "8:48 PM", "temp": "11–21°C", "weatherIcon": "🌦️", "weather": "Llovizna", "packing": "Chaqueta y capas ligeras"},
    "Berlín": {"sunrise": "4:58 AM", "sunset": "9:07 PM", "temp": "11–21°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Chaqueta impermeable"},
    "Múnich": {"sunrise": "5:21 AM", "sunset": "8:59 PM", "temp": "10–20°C", "weatherIcon": "☁️", "weather": "Nublado", "packing": "Chaqueta ligera y zapatos cómodos"},
    "En el mar": {"sunrise": "5:46 AM", "sunset": "8:02 PM", "temp": "9–20°C", "weatherIcon": "🌦️", "weather": "Llovizna", "packing": "Traje de baño y ropa casual"},
    "Jungfraujoch": {"sunrise": "6:10 AM", "sunset": "8:39 PM", "temp": "-11–-5°C", "weatherIcon": "⛅", "weather": "Parcialmente nublado", "packing": "Ropa de abrigo tipo montaña y gafas de sol para la nieve"},
    # Late March (Semana Santa), Orlando/Central Florida — sunny and warm,
    # around the spring equinox.
    "Orlando": {"sunrise": "7:20 AM", "sunset": "7:26 PM", "temp": "16–27°C", "weatherIcon": "☀️", "weather": "Soleado", "packing": "Ropa ligera, bloqueador solar y gorra"},
}
DEFAULT_CLIMATE = {"sunrise": "6:00 AM", "sunset": "8:15 PM", "temp": "12–20°C", "weatherIcon": "⛅", "weather": "Variable", "packing": "Ropa por capas y zapatos cómodos"}

# Per (city, dayKey) override of sunrise/sunset/temp/weatherIcon/weather —
# these vary by the exact calendar date, not just the city, so a city
# visited twice on different dates can show different values. Populated by
# scripts/update_climate.py; falls back to CITY_CLIMATE/DEFAULT_CLIMATE
# above (city-only) for any day not covered here, e.g. right after a new
# day is added to the workbook and before the next update_climate.py run.
CITY_CLIMATE_BY_DAY: dict[str, dict[str, str]] = {
    "Zúrich|29 ABR": {"sunrise": "6:11 AM", "sunset": "8:35 PM", "temp": "6–16°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Zúrich|30 ABR": {"sunrise": "6:09 AM", "sunset": "8:36 PM", "temp": "6–16°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Zúrich|01 MAY": {"sunrise": "6:07 AM", "sunset": "8:38 PM", "temp": "7–16°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "París|05 MAY": {"sunrise": "6:21 AM", "sunset": "9:12 PM", "temp": "9–19°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "París|03 MAY": {"sunrise": "6:25 AM", "sunset": "9:09 PM", "temp": "8–18°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "París|04 MAY": {"sunrise": "6:23 AM", "sunset": "9:11 PM", "temp": "9–19°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Jungfraujoch|02 MAY": {"sunrise": "6:10 AM", "sunset": "8:39 PM", "temp": "-11–-5°C", "weatherIcon": "⛅", "weather": "Parcialmente nublado"},
    "Barcelona|06 MAY": {"sunrise": "6:40 AM", "sunset": "8:55 PM", "temp": "13–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Barcelona|07 MAY": {"sunrise": "6:39 AM", "sunset": "8:56 PM", "temp": "13–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Barcelona|08 MAY": {"sunrise": "6:38 AM", "sunset": "8:57 PM", "temp": "12–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "En el mar|13 MAY": {"sunrise": "5:42 AM", "sunset": "8:06 PM", "temp": "11–22°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "En el mar|09 MAY": {"sunrise": "5:46 AM", "sunset": "8:02 PM", "temp": "9–20°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Zadar|14 MAY": {"sunrise": "5:32 AM", "sunset": "8:18 PM", "temp": "14–22°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "La Spezia|10 MAY": {"sunrise": "5:58 AM", "sunset": "8:35 PM", "temp": "12–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Roma|11 MAY": {"sunrise": "5:52 AM", "sunset": "8:20 PM", "temp": "13–23°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Salerno|12 MAY": {"sunrise": "5:45 AM", "sunset": "8:09 PM", "temp": "14–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Venecia|15 MAY": {"sunrise": "5:38 AM", "sunset": "8:35 PM", "temp": "14–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Praga|19 MAY": {"sunrise": "5:08 AM", "sunset": "8:48 PM", "temp": "11–21°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Praga|21 MAY": {"sunrise": "5:06 AM", "sunset": "8:51 PM", "temp": "11–21°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Roma|16 MAY": {"sunrise": "5:47 AM", "sunset": "8:25 PM", "temp": "14–24°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Roma|17 MAY": {"sunrise": "5:46 AM", "sunset": "8:26 PM", "temp": "14–25°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Praga|20 MAY": {"sunrise": "5:07 AM", "sunset": "8:49 PM", "temp": "11–21°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Roma|18 MAY": {"sunrise": "5:45 AM", "sunset": "8:27 PM", "temp": "14–25°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Berlín|22 MAY": {"sunrise": "4:58 AM", "sunset": "9:07 PM", "temp": "11–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Zúrich|04 MAY": {"sunrise": "6:03 AM", "sunset": "8:42 PM", "temp": "8–18°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Zúrich|05 MAY": {"sunrise": "6:01 AM", "sunset": "8:43 PM", "temp": "8–18°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Múnich|26 MAY": {"sunrise": "5:20 AM", "sunset": "9:00 PM", "temp": "10–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Múnich|25 MAY": {"sunrise": "5:21 AM", "sunset": "8:59 PM", "temp": "10–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Múnich|27 MAY": {"sunrise": "5:19 AM", "sunset": "9:01 PM", "temp": "10–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Berlín|23 MAY": {"sunrise": "4:56 AM", "sunset": "9:09 PM", "temp": "11–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Zúrich|03 MAY": {"sunrise": "6:04 AM", "sunset": "8:40 PM", "temp": "7–17°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Berlín|24 MAY": {"sunrise": "4:55 AM", "sunset": "9:10 PM", "temp": "11–21°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Venecia|16 MAY": {"sunrise": "5:37 AM", "sunset": "8:36 PM", "temp": "14–22°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Múnich|01 MAY": {"sunrise": "5:53 AM", "sunset": "8:28 PM", "temp": "6–16°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Múnich|04 MAY": {"sunrise": "5:48 AM", "sunset": "8:32 PM", "temp": "7–17°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Múnich|30 ABR": {"sunrise": "5:55 AM", "sunset": "8:26 PM", "temp": "6–16°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Múnich|02 MAY": {"sunrise": "5:51 AM", "sunset": "8:29 PM", "temp": "6–16°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Múnich|03 MAY": {"sunrise": "5:50 AM", "sunset": "8:30 PM", "temp": "7–17°C", "weatherIcon": "🌦️", "weather": "Llovizna"},
    "Múnich|05 MAY": {"sunrise": "5:47 AM", "sunset": "8:33 PM", "temp": "7–18°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Barcelona|05 MAY": {"sunrise": "6:42 AM", "sunset": "8:53 PM", "temp": "13–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Milán|03 MAY": {"sunrise": "6:07 AM", "sunset": "8:33 PM", "temp": "11–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Milán|01 MAY": {"sunrise": "6:09 AM", "sunset": "8:30 PM", "temp": "11–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Florencia|05 MAY": {"sunrise": "6:00 AM", "sunset": "8:23 PM", "temp": "10–22°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Florencia|04 MAY": {"sunrise": "6:01 AM", "sunset": "8:22 PM", "temp": "10–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Milán|29 ABR": {"sunrise": "6:13 AM", "sunset": "8:28 PM", "temp": "10–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Milán|02 MAY": {"sunrise": "6:08 AM", "sunset": "8:32 PM", "temp": "11–21°C", "weatherIcon": "☁️", "weather": "Nublado"},
    "Milán|30 ABR": {"sunrise": "6:11 AM", "sunset": "8:29 PM", "temp": "10–20°C", "weatherIcon": "☁️", "weather": "Nublado"},
}

# Where a reader can independently check a city's climate normals — shown as the
# "Ver clima" link on that day's weather chip in the app. weather-and-climate.com
# uses a plain city+country slug (no per-city ID lookup needed), which is what
# scripts/update_climate.py relies on when refreshing CITY_CLIMATE above.
# "En el mar" has no fixed location, so it gets no link.
CLIMATE_SOURCE_URL = {
    "Zúrich": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,zurich,Switzerland",
    "París": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,paris,France",
    "Barcelona": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,barcelona,Spain",
    "La Spezia": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,la-spezia,Italy",
    "Salerno": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,salerno,Italy",
    "Zadar": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,zadar,Croatia",
    "Venecia": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,venice,Italy",
    "Roma": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,rome,Italy",
    "Praga": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,prague,Czech-Republic",
    "Berlín": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,berlin,Germany",
    "Múnich": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,munich,Germany",
    "Milán": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,milan,Italy",
    "Florencia": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,florence,Italy",
    # weather-and-climate.com has no page for the Jungfraujoch summit itself
    # (not a "city") — Interlaken is the nearest town with one, a reasonable
    # stand-in reference the same way "En el mar" uses a representative point.
    "Jungfraujoch": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,interlaken,Switzerland",
}

# Some Tours lines are a day trip to a specific destination distinct from
# where the traveler is actually staying that day — e.g. a Zürich-based day
# (02 May) with an optional excursion up to the Jungfraujoch. Detected by a
# keyword match (lowercase substring) against that day's Tours y Excursiones
# line titles. When matched, that day's weather/sunrise/sunset/packing
# reflect the excursion destination instead of the base city, since that's
# where the day is actually spent — the day's own city/title/hero image are
# unaffected. The destination still needs its own CITY_CLIMATE (fallback),
# CLIMATE_SOURCE_URL/SUN_SOURCE_URL entries below, and CITY_COORDS in
# scripts/update_climate.py, the same as any other climate-tracked place.
DAY_TRIP_DESTINATIONS = {
    "jungfraujoch": "Jungfraujoch",
}


def day_trip_destination(lines: list[dict[str, object]]) -> str | None:
    for line in lines:
        if line["category"] != "Tours y Excursiones":
            continue
        title_lower = str(line["title"]).lower()
        for keyword, destination in DAY_TRIP_DESTINATIONS.items():
            if keyword in title_lower:
                return destination
    return None


# Where a reader can independently check a city's sunrise/sunset — shown as
# the "Ver amanecer/atardecer" link on those two day-condition chips. Same
# page serves both (sunrise-sunset.org's per-location page shows the day's
# full sun schedule), so amanecer and atardecer share this one URL per city.
SUN_SOURCE_URL = {
    "Zúrich": "https://sunrise-sunset.org/search?location=Zurich",
    "París": "https://sunrise-sunset.org/search?location=Paris",
    "Barcelona": "https://sunrise-sunset.org/search?location=Barcelona",
    "La Spezia": "https://sunrise-sunset.org/search?location=La+Spezia",
    "Salerno": "https://sunrise-sunset.org/search?location=Salerno",
    "Zadar": "https://sunrise-sunset.org/search?location=Zadar",
    "Venecia": "https://sunrise-sunset.org/search?location=Venice",
    "Roma": "https://sunrise-sunset.org/search?location=Rome",
    "Praga": "https://sunrise-sunset.org/search?location=Prague",
    "Berlín": "https://sunrise-sunset.org/search?location=Berlin",
    "Múnich": "https://sunrise-sunset.org/search?location=Munich",
    "Milán": "https://sunrise-sunset.org/search?location=Milan",
    "Florencia": "https://sunrise-sunset.org/search?location=Florence",
    "Jungfraujoch": "https://sunrise-sunset.org/search?location=Jungfraujoch",
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
    "Orlando": [
        unsplash("photo-1578089815509-ed664d5b66d3"),
        unsplash("photo-1597466599360-3b9775841aec"),
        unsplash("photo-1524008279394-3aed4643b30b"),
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
    # Florencia before Milán: on the "Milán / Florencia" train-day place text,
    # the first alias that matches wins (see extract_city), and that day's
    # actual city is the destination, Florencia.
    ("Florencia", "Florencia"), ("Firenze", "Florencia"), ("Florence", "Florencia"),
    ("Milán", "Milán"), ("Milan", "Milán"),
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


# Where a reader can independently verify each currency's rate to COP —
# shown as a "Ver fuente" link next to that currency in the app. Same
# provider for all four, for consistency; update here if it ever changes.
CURRENCY_SOURCE_URL = {
    "EUR": "https://www.xe.com/currencyconverter/convert/?Amount=1&From=EUR&To=COP",
    "CHF": "https://www.xe.com/currencyconverter/convert/?Amount=1&From=CHF&To=COP",
    "CZK": "https://www.xe.com/currencyconverter/convert/?Amount=1&From=CZK&To=COP",
    "USD": "https://www.xe.com/currencyconverter/convert/?Amount=1&From=USD&To=COP",
}


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
                rates.append({
                    "code": values[1], "label": values[2], "symbol": values[3], "rate": number(values[4]),
                    "sourceUrl": CURRENCY_SOURCE_URL.get(values[1]),
                })
        return rates, update_date


def read_people_count() -> int:
    """Read 'Número de personas' from the 'Tasas de Cambio' sheet (sheet3).
    Currently one shared value divides every sheet's per-person formulas —
    if a future option ever needs its own traveler count, give that sheet
    its own cell and make this per-option instead of workbook-wide."""
    with zipfile.ZipFile(WORKBOOK) as book:
        strings = shared_strings(book)
        sheet = ET.fromstring(book.read("xl/worksheets/sheet3.xml"))
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            cells = {cell.attrib["r"]: value(cell, strings) for cell in row.findall("x:c", NS)}
            if cells.get(f"B{row.attrib['r']}", "") == "Número de personas":
                return int(float(cells.get(f"C{row.attrib['r']}", "3") or 3))
        return 3


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
TEMP_RANGE_RE = re.compile(r"(-?\d+)\D+(-?\d+)")


def _parse_temp_range(temp: str) -> tuple[int, int] | None:
    match = TEMP_RANGE_RE.match(temp)
    return (int(match.group(1)), int(match.group(2))) if match else None


def compute_packing(
    city: str, day_kind: str | None, is_last: bool, weather: str, temp: str,
    has_lodging: bool, has_tours: bool, fallback: str,
) -> list[str]:
    """Rule-based "qué llevar" checklist for one day, combining what that
    day's own plans require (documents, logistics) with what its weather
    calls for. The rules themselves are informed by common travel-prep
    checklists — passport validity, a printed/offline boarding pass, a
    cruise embarkation day-bag — researched once (see the update-packing
    skill for sources) rather than fetched live: unlike climate, packing
    guidance doesn't go stale day to day, so there's no separate "run this
    script" step — it's recomputed automatically here every time the
    itinerary regenerates, from whatever that day's dayKind/weather/lines
    already are. Falls back to a single-item list with the city's static
    CITY_CLIMATE packing tip on an otherwise uneventful day (no
    flight/embark, mild weather) rather than forcing a generic item onto
    every single day."""
    items: list[str] = []

    if day_kind == "flight":
        items.append("pasaporte (vigencia mínima de 6 meses)")
        items.append("tiquete o pase de abordar impreso y en el celular")
    elif day_kind == "embark":
        items.append("pasaporte y documentos de embarque del crucero")
        items.append("bolso de mano con lo esencial — el equipaje tarda en llegar al camarote")
    elif is_last:
        items.append("pasaporte y documentos del vuelo de regreso")
    elif has_lodging:
        items.append("confirmación de la reserva del hotel")

    if has_tours:
        items.append("efectivo para gastos pequeños y cámara")

    if city == "En el mar":
        items.append("traje de baño, protector solar y algo para el mareo si lo necesitas")

    weather_lower = weather.lower()
    if any(word in weather_lower for word in ("lluv", "chubasco", "tormenta")):
        items.append("paraguas compacto o chaqueta impermeable")

    temp_range = _parse_temp_range(temp)
    if temp_range:
        low, high = temp_range
        if low < 10:
            items.append("chaqueta abrigada")
        elif low < 16:
            items.append("chaqueta ligera")
        if high >= 22:
            items.append("ropa ligera, gafas de sol y bloqueador solar")

    if not items:
        return [fallback]

    items.append("botella de agua reutilizable")
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item.capitalize())
    return unique_items[:5]  # keep it a short checklist, not an exhaustive dump


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
        is_last = index == len(keys) - 1
        has_lodging = any(line["category"] == "Alojamiento" for line in lines)
        has_tours = any(
            line["category"] == "Tours y Excursiones" and str(line["title"]).strip() and not is_placeholder(str(line["title"]))
            for line in lines
        )
        display_lines = [line for line in lines if not is_placeholder(str(line["title"]))]
        # The day's weather/sunrise/sunset/packing follow wherever the day is actually spent —
        # the base city, unless a Tours line is a day trip elsewhere (see DAY_TRIP_DESTINATIONS).
        # The day's own city/title/hero image always stay the base city regardless.
        climate_city = day_trip_destination(lines) or city
        climate = {**CITY_CLIMATE.get(climate_city, DEFAULT_CLIMATE), **CITY_CLIMATE_BY_DAY.get(f"{climate_city}|{key}", {})}
        day_kind = "flight" if is_first else ("embark" if is_embark else None)
        days.append({
            "dayKey": key, "city": city, "country": country, "emoji": emoji,
            "image": image_url,
            "title": day_title(lines, city, is_first, is_last, is_embark),
            "dayKind": day_kind,
            "climateCity": climate_city,
            "sunrise": climate["sunrise"], "sunset": climate["sunset"], "temp": climate["temp"],
            "weatherIcon": climate["weatherIcon"], "weather": climate["weather"],
            "packing": compute_packing(climate_city, day_kind, is_last, climate["weather"], climate["temp"], has_lodging, has_tours, climate["packing"]),
            "weatherUrl": CLIMATE_SOURCE_URL.get(climate_city),
            "sunUrl": SUN_SOURCE_URL.get(climate_city),
            "planNote": None, "planNoteCaption": None,
            "expenses": [to_expense(line) for line in display_lines],
        })
    return days


def build_option(name: str, dates_label: str, color: str, description: str, rows: list[dict[str, object]], people_count: int) -> dict[str, object]:
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
        "peopleCount": people_count, "itinerary": itinerary,
    }


# ============================================================
# Disney World + Universal Orlando trip — a second, independent workbook
# (Plan_Disney_Universal_2027.xlsx) with a completely different sheet shape
# than the Europa one above: costs are bucketed per category and per
# traveler-type (adults vs. children, since Disney/Universal/food price them
# differently), not one row per line item with an explicit date — and the
# day-by-day plan lives in separate "Itinerario Grupo A/B" sheets, keyed by
# day number rather than date. Read directly here rather than forced through
# read_rows()/to_expense(), since the shape genuinely doesn't fit that model.
# Two options come out of this workbook — "Orlando con Jero" (Grupo A) and
# "Orlando con Pachito y Vale" (Grupo B) — one per hotel room/travel
# subgroup, each with its own real per-traveler-type composition.
# ============================================================
DISNEY_WORKBOOK = ROOT / "Plan_Disney_Universal_2027.xlsx"

# (dayKey, title, dayKind) for the 9 fixed days (20-28 Mar 2027) — same for
# both groups, since both subgroups follow the same park each day, just with
# a different ride plan (see the itinerary sheets' "Plan recomendado" column).
DISNEY_DAYS = [
    ("20 MAR", "Llegada a Orlando", "flight"),
    ("21 MAR", "Magic Kingdom", None),
    ("22 MAR", "EPCOT", None),
    ("23 MAR", "Universal Studios + Islands of Adventure", None),
    ("24 MAR", "Hollywood Studios", None),
    ("25 MAR", "Universal Epic Universe", None),
    ("26 MAR", "Animal Kingdom", None),
    ("27 MAR", "Día libre / compras / pileta", None),
    ("28 MAR", "Check-out y vuelo de regreso", None),
]


def _disney_sheet_cells(book: zipfile.ZipFile, strings: list[str], sheet_no: int) -> dict[str, str]:
    sheet = ET.fromstring(book.read(f"xl/worksheets/sheet{sheet_no}.xml"))
    cells: dict[str, str] = {}
    for row in sheet.findall(".//x:sheetData/x:row", NS):
        for cell in row.findall("x:c", NS):
            v = value(cell, strings)
            if v:
                cells[cell.attrib["r"]] = v
    return cells


def _disney_num(cells: dict[str, str], ref: str) -> float:
    raw = cells.get(ref, "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def build_disney_option(
    name: str, description: str, color: str, budget_sheet: int, itinerary_sheet: int,
    child_age_label: str, adults_count: int, children_count: int, rate_usd_to_cop: float,
    has_adolescent: bool = False,
) -> dict[str, object]:
    with zipfile.ZipFile(DISNEY_WORKBOOK) as book:
        strings = shared_strings(book)
        budget = _disney_sheet_cells(book, strings, budget_sheet)
        itin = _disney_sheet_cells(book, strings, itinerary_sheet)

    people_count = adults_count + children_count

    def blended_expense(category: str, title: str, unit_usd: float, qty: int, note: str, link: str | None = None) -> dict[str, object]:
        """A cost bucket for one traveler type (e.g. "3 adultos"), shown at
        its blended per-person share of the option's total headcount — the
        same total/peopleCount split every Europa expense already uses, so
        the day and category views keep reconciling with the option's
        headline total. The real per-traveler-type price always stays
        visible in `note` (never hidden), since blending only ever produces
        an average, not what any one traveler actually pays."""
        total_usd = unit_usd * qty
        total_cop = total_usd * rate_usd_to_cop
        per_person_cop = total_cop / people_count
        return {
            "category": category, "title": title, "amount": round(per_person_cop),
            "originalAmount": round(total_usd / people_count, 2), "currency": "USD",
            "note": note, "place": "Orlando", "date": "", "link": link,
        }

    def shared_expense(category: str, title: str, total_usd: float, note: str, link: str | None = None) -> dict[str, object]:
        """A bundled cost for the whole subgroup (hotel room, PhotoPass,
        souvenirs...) — same convention as Europa's "costo total" rows."""
        return blended_expense(category, title, total_usd, 1, note, link)

    AVIANCA = "https://www.avianca.com/co/es/vuelos-desde-bogota-a-orlando"
    HILTON = "https://www.hilton.com/en/hotels/mcofhdt-doubletree-suites-orlando-disney-springs/"
    DISNEY_TICKETS = "https://disneyworld.disney.go.com/admission/tickets/"
    UNIVERSAL_TICKETS = "https://www.universalorlando.com/web/en/us/tickets-packages/park-tickets"
    EPIC_TICKETS = "https://www.universalorlando.com/web/en/us/tickets-packages/park-tickets/epic-products"

    flight_adult_unit, flight_child_unit = _disney_num(budget, "C6"), _disney_num(budget, "C7")
    flight_roundtrip_total = flight_adult_unit * adults_count + flight_child_unit * children_count
    hotel_total = _disney_num(budget, "F13")
    disney_adult_unit, disney_child_unit = _disney_num(budget, "C19"), _disney_num(budget, "C20")
    universal_adult_unit, universal_child_unit = _disney_num(budget, "C26"), _disney_num(budget, "C27")
    epic_adult_unit, epic_child_unit = _disney_num(budget, "C33"), _disney_num(budget, "C34")
    food_adult_per_day, food_child_per_day = _disney_num(budget, "B40"), _disney_num(budget, "B41")
    uber_total = _disney_num(budget, "B46")  # covers 2 days (Universal + Epic Universe), split below
    photopass, souvenirs, tips = _disney_num(budget, "B47"), _disney_num(budget, "B48"), _disney_num(budget, "B49")

    days: list[dict[str, object]] = []
    for index, (day_key, title, day_kind) in enumerate(DISNEY_DAYS):
        is_first, is_last = index == 0, index == len(DISNEY_DAYS) - 1
        expenses: list[dict[str, object]] = []

        if is_first:
            expenses.append(shared_expense(
                "Transporte", "Vuelo internacional Bogotá ⇄ Orlando (ida y vuelta)", flight_roundtrip_total,
                f"Avianca, estimado temporada Semana Santa. ${flight_adult_unit:.0f}/persona (adultos y niño de {child_age_label} años por igual).",
                AVIANCA,
            ))
            expenses.append(shared_expense(
                "Alojamiento", "Hotel DoubleTree Suites — costo total (8 noches)", hotel_total,
                "Recomendado: DoubleTree Suites, Disney Springs Resort Area — shuttle gratis a los 4 parques Disney, 4★.",
                HILTON,
            ))
            expenses.append({
                "category": "Otros", "title": "PhotoPass / fotos", "amount": round(photopass * rate_usd_to_cop / people_count),
                "originalAmount": round(photopass / people_count, 2), "currency": "USD",
                "note": "Estimado para todo el viaje, compartido entre el subgrupo.", "place": "Orlando", "date": "", "link": None,
            })
            expenses.append({
                "category": "Otros", "title": "Souvenirs (estimado)", "amount": round(souvenirs * rate_usd_to_cop / people_count),
                "originalAmount": round(souvenirs / people_count, 2), "currency": "USD",
                "note": "Estimado para todo el viaje, compartido entre el subgrupo.", "place": "Orlando", "date": "", "link": None,
            })
            expenses.append({
                "category": "Otros", "title": "Propinas y varios", "amount": round(tips * rate_usd_to_cop / people_count),
                "originalAmount": round(tips / people_count, 2), "currency": "USD",
                "note": "Estimado para todo el viaje, compartido entre el subgrupo.", "place": "Orlando", "date": "", "link": None,
            })

        if title == "Magic Kingdom":
            expenses.append(blended_expense(
                "Tours", f"Tickets Disney World — adultos ({adults_count} personas)", disney_adult_unit, adults_count,
                "Pase de 4 días, 1 parque/día, sin Park Hopper. Tarifa oficial temporada pico (MouseSavers).", DISNEY_TICKETS,
            ))
            expenses.append(blended_expense(
                "Tours", f"Tickets Disney World — niño ({child_age_label} años)", disney_child_unit, children_count,
                "Pase de 4 días, 1 parque/día, sin Park Hopper. El de 13 años (si aplica) paga tarifa adulto.", DISNEY_TICKETS,
            ))
        if title == "Universal Studios + Islands of Adventure":
            expenses.append(blended_expense(
                "Tours", f"Tickets Universal — adultos ({adults_count} personas)", universal_adult_unit, adults_count,
                "1 día Park-to-Park (Studios + Islands of Adventure). No incluye Epic Universe.", UNIVERSAL_TICKETS,
            ))
            expenses.append(blended_expense(
                "Tours", f"Tickets Universal — niño ({child_age_label} años)", universal_child_unit, children_count,
                "1 día Park-to-Park (Studios + Islands of Adventure). No incluye Epic Universe.", UNIVERSAL_TICKETS,
            ))
            expenses.append(shared_expense(
                "Transporte", "Uber ida y vuelta — Universal Studios + Islands of Adventure", uber_total / 2,
                "Disney va en shuttle gratis del hotel; solo Universal/Epic Universe necesitan Uber.",
            ))
        if title == "Universal Epic Universe":
            expenses.append(blended_expense(
                "Tours", f"Ticket Epic Universe — adultos ({adults_count} personas)", epic_adult_unit, adults_count,
                "1 día, 1 parque (4to parque de Universal, abierto desde may-2025).", EPIC_TICKETS,
            ))
            expenses.append(blended_expense(
                "Tours", f"Ticket Epic Universe — niño ({child_age_label} años)", epic_child_unit, children_count,
                "1 día, 1 parque. Niño estimado a ~97% de la tarifa adulto (ratio Universal).", EPIC_TICKETS,
            ))
            expenses.append(shared_expense(
                "Transporte", "Uber ida y vuelta — Universal Epic Universe", uber_total / 2,
                "Disney va en shuttle gratis del hotel; solo Universal/Epic Universe necesitan Uber.",
            ))

        # Comida — 8 de los 9 días (todos menos el de llegada, cubierto por
        # las comidas del vuelo), igual que el "COMIDA — 8 días" del workbook.
        if not is_first:
            food_total_day = food_adult_per_day * adults_count + food_child_per_day * children_count
            expenses.append(shared_expense(
                "Comida", "Comida del día (desayuno, almuerzo y cena)", food_total_day,
                f"Estimado: ${food_adult_per_day:.0f}/adulto + ${food_child_per_day:.0f}/niño ({child_age_label}) por día.",
            ))

        if is_last:
            expenses.append({
                "category": "Transporte", "title": "Vuelo internacional Orlando → Bogotá (regreso)", "amount": 0,
                "originalAmount": 0, "currency": "USD",
                "note": "Incluido en la tarifa ida y vuelta del vuelo de ida.", "place": "Orlando", "date": "", "link": None,
            })

        climate = CITY_CLIMATE["Orlando"]
        plan_note = itin.get(f"D{5 + index}")
        plan_caption = itin.get(f"E{5 + index}")
        has_tours = any(e["category"] == "Tours" for e in expenses)
        has_lodging = any(e["category"] == "Alojamiento" for e in expenses)
        day_kind_final = "flight" if is_first else None
        days.append({
            "dayKey": day_key, "city": "Orlando", "country": "Estados Unidos", "emoji": "🇺🇸",
            "image": image_for_day("Orlando", index),
            "title": title, "dayKind": day_kind_final,
            "climateCity": "Orlando",
            "sunrise": climate["sunrise"], "sunset": climate["sunset"], "temp": climate["temp"],
            "weatherIcon": climate["weatherIcon"], "weather": climate["weather"],
            "packing": compute_packing("Orlando", day_kind_final, is_last, climate["weather"], climate["temp"], has_lodging, has_tours, climate["packing"]),
            "weatherUrl": CLIMATE_SOURCE_URL.get("Orlando"), "sunUrl": SUN_SOURCE_URL.get("Orlando"),
            "planNote": plan_note, "planNoteCaption": plan_caption,
            "expenses": expenses,
        })

    total = sum(e["amount"] for day in days for e in day["expenses"])

    # The headline "perPerson" above is a blended average (total ÷
    # peopleCount) — accurate as a summary, but not what any individual
    # traveler actually pays when adults and children are priced
    # differently. perPersonByType gives the real figure for each fare tier,
    # computed the same way the blended total is (shared costs like the
    # hotel room split equally per head, fare-specific costs like tickets
    # kept at their real per-type price) — adults_count·adult + children_count·child
    # reproduces the exact group total above, just not blended together.
    shared_per_person = (hotel_total + uber_total + photopass + souvenirs + tips) / people_count
    food_days = len(DISNEY_DAYS) - 1
    adult_total_usd = flight_adult_unit + shared_per_person + disney_adult_unit + universal_adult_unit + epic_adult_unit + food_adult_per_day * food_days
    child_total_usd = flight_child_unit + shared_per_person + disney_child_unit + universal_child_unit + epic_child_unit + food_child_per_day * food_days
    per_person_by_type = [{"label": "Adulto", "amount": round(adult_total_usd * rate_usd_to_cop)}]
    if has_adolescent:
        per_person_by_type.append({"label": "Adolescente (13)", "amount": round(adult_total_usd * rate_usd_to_cop)})
    per_person_by_type.append({"label": f"Niño ({child_age_label})", "amount": round(child_total_usd * rate_usd_to_cop)})

    return {
        "name": name, "dates": "20 – 28 mar 2027", "route": "Orlando", "days": len(days),
        "total": round(total), "perPerson": round(total), "color": color, "description": description,
        "peopleCount": people_count, "perPersonByType": per_person_by_type, "itinerary": days,
    }


def read_disney_rate() -> float:
    """TRM (USD→COP) from the Disney workbook's own 'Resumen' sheet — kept
    separate from the Europa workbook's exchange-rate sheet since this is an
    independent quote with its own rate, entered by hand, no markup applied."""
    with zipfile.ZipFile(DISNEY_WORKBOOK) as book:
        strings = shared_strings(book)
        cells = _disney_sheet_cells(book, strings, 1)
    return _disney_num(cells, "B6")


def main() -> None:
    # Only 3 of the workbook's 8 option sheets are active — the rest (2P/4P
    # cruise headcount variants, the Zürich/Múnich+cruise combos, the Milán
    # variant of this same sheet) are hidden in the workbook and skipped
    # here, the same way the 6 in-Excel summary sheets always have been. See
    # scripts/restructure_2027_plan.py for the migration that dropped them.
    sheets = [
        (4, "Completo"), (12, "Solo crucero 2P"), (14, "Crucero Milán"),
    ]
    rows = [line for sheet, name in sheets for line in read_rows(sheet, name)]

    # people_count is per-option: every sheet but "Crucero 2P" shares the
    # workbook-wide 'Tasas de Cambio'!C5 headcount; sheet12 is hardcoded to
    # 2 since it's a dedicated 2-person duplicate with its own /2 formulas
    # (see scripts/duplicate_option.py) rather than reading the shared cell.
    shared_people_count = read_people_count()
    options_meta = [
        ("1 mes por Europa", "7 – 31 may 2027", "#e9a34c", "Crucero por el Mediterráneo primero, luego Roma, París, Praga, Múnich y Berlín", "Completo", shared_people_count),
        ("Italia", "30 abr – 16 may 2027", "#7a9b8e", "Milán, Florencia y Mediterráneo", "Crucero Milán", shared_people_count),
        ("Crucero en pareja", "5 – 16 may 2027", "#a998c9", "Una escapada mediterránea para dos", "Solo crucero 2P", 2),
    ]
    options = [
        build_option(display_name, dates_label, color, description, [r for r in rows if r["option"] == sheet_option], people_count)
        for display_name, dates_label, color, description, sheet_option, people_count in options_meta
    ]

    disney_rate = read_disney_rate()
    options.append(build_disney_option(
        "Orlando con Jero", "Disney World, Universal y Epic Universe — 3 adultos + niño de 7 años",
        "#5b9bd5", budget_sheet=2, itinerary_sheet=4, child_age_label="7",
        adults_count=3, children_count=1, rate_usd_to_cop=disney_rate,
    ))
    options.append(build_disney_option(
        "Orlando con Pachito y Vale", "Disney World, Universal y Epic Universe — 2 adultos + adolescente (13) y niño (9)",
        "#ed7d31", budget_sheet=3, itinerary_sheet=5, child_age_label="9",
        adults_count=3, children_count=1, rate_usd_to_cop=disney_rate, has_adolescent=True,
    ))

    rates, rates_updated = read_rates()

    ITINERARY_OUTPUT.write_text(
        "// Generated by scripts/generate_data.py — do not edit manually.\n"
        "export type GeneratedExpense = { category: string; title: string; amount: number; originalAmount: number; currency: string; note: string; place: string; date: string; link: string | null };\n"
        "export type GeneratedDay = { dayKey: string; city: string; country: string; emoji: string; image: string; title: string; dayKind: 'flight' | 'embark' | null; climateCity: string; sunrise: string; sunset: string; temp: string; weatherIcon: string; weather: string; packing: string[]; weatherUrl: string | null; sunUrl: string | null; planNote: string | null; planNoteCaption: string | null; expenses: GeneratedExpense[] };\n"
        "export type GeneratedOption = { name: string; dates: string; route: string; days: number; total: number; perPerson: number; color: string; description: string; peopleCount: number; perPersonByType?: { label: string; amount: number }[]; itinerary: GeneratedDay[] };\n"
        "export type ExchangeRate = { code: string; label: string; symbol: string; rate: number; sourceUrl: string };\n"
        f"export const generatedOptions: GeneratedOption[] = {ts(options)};\n"
        f"export const exchangeRates: ExchangeRate[] = {ts(rates)};\n"
        f"export const ratesUpdatedAt: string = {ts(rates_updated)};\n",
        encoding="utf-8",
    )
    print(f"Generated {len(options)} itinerary options at {ITINERARY_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
