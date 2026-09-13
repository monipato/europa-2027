"""Generate src/data/generated/itinerary.generated.ts from data/*.json.

Run from the project root:
    python3 scripts/generate_data.py

Reads every trip option's plain JSON file under data/options/ (plus the two
shared files, data/rates.json and data/cities.json), applies the currency
math every option always used (live rate × the standing markup, divided by
however many people share that cost), and writes one generated TypeScript
file that's the app's single source of truth. See CLAUDE.md for the full
data flow and the "Data" section for each JSON file's shape.

Unlike the old Excel-based version of this script, a day's city/title/
weather are never guessed from its line items — every option's JSON states
them directly, day by day (see data/options/europa.json for the shape).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ITINERARY_OUTPUT = ROOT / "src" / "data" / "generated" / "itinerary.generated.ts"

# Category labels as they appear in data/options/*.json, collapsed into the
# smaller set of categories the app actually shows.
CATEGORY_BY_EXCEL = {
    "Vuelos y Trenes": "Transporte", "Traslados": "Transporte", "Alojamiento": "Alojamiento",
    "Comidas": "Comida", "Tours y Excursiones": "Tours", "Crucero": "Crucero",
    "Seguro de Viaje": "Seguro", "Otros y Extras": "Otros",
}

DEFAULT_CLIMATE = {"sunrise": "6:00 AM", "sunset": "8:15 PM", "temp": "12–20°C", "weatherIcon": "⛅", "weather": "Variable", "packing": "Ropa por capas y zapatos cómodos"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


CITIES = load_json(DATA / "cities.json")
RATES_DOC = load_json(DATA / "rates.json")


def unsplash(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=900&q=80"


def rate_for(currency: str) -> float:
    """COP per 1 unit of `currency`, live from data/rates.json (base rate
    times the standing markup — the same "always add 5% more" policy that
    used to live in the workbook's own E7 cell). 1.0 for COP itself."""
    if currency == "COP":
        return 1.0
    entry = RATES_DOC["rates"][currency]
    return entry["baseRate"] * RATES_DOC["markup"]


def image_for_day(city: str, occurrence: int) -> str:
    """A city can appear on several itinerary days — cycle through its photo
    pool (data/cities.json) so the hero does not repeat the same background
    on every occurrence."""
    entry = CITIES["cities"].get(city)
    images = entry["images"] if entry else None
    if images:
        return images[occurrence % len(images)]
    return unsplash("photo-1436491865332-7a61a109cc05")


def city_country_emoji(city: str) -> tuple[str, str]:
    entry = CITIES["cities"].get(city)
    return (entry["country"], entry["emoji"]) if entry else ("Europa", "🌍")


def city_climate(city: str) -> dict[str, str]:
    """Only used for: (1) Orlando/Japón, whose days don't carry their own
    per-day weather (a single seasonal estimate is accurate enough for
    those), and (2) the packing-tip fallback text for every option, which
    isn't part of a day's own embedded `weather` object."""
    entry = CITIES["cities"].get(city)
    return entry["climate"] if entry else DEFAULT_CLIMATE


def climate_source_url(city: str) -> str | None:
    entry = CITIES["cities"].get(city)
    return entry.get("weatherSourceUrl") if entry else None


def sun_source_url(city: str) -> str | None:
    entry = CITIES["cities"].get(city)
    return entry.get("sunSourceUrl") if entry else None


import re  # noqa: E402

TEMP_RANGE_RE = re.compile(r"(-?\d+)\D+(-?\d+)")


def _parse_temp_range(temp: str) -> tuple[int, int] | None:
    match = TEMP_RANGE_RE.match(temp)
    return (int(match.group(1)), int(match.group(2))) if match else None


def compute_packing(
    city: str, day_kind: str | None, is_last: bool, weather: str, temp: str,
    has_lodging: bool, has_tours: bool, fallback: str,
) -> list[str]:
    """Rule-based "qué llevar" checklist for one day — see the update-packing
    skill for the reasoning and sources behind these rules. Recomputed fresh
    every regenerate from that day's dayKind/weather/line items; there's no
    separate "run this script" step for it, unlike rates or climate."""
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


def ts(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


# ============================================================
# Europa-shaped options ("1 mes por Europa", "Alpes Suizos...", "Crucero en
# pareja") — each data/options/*.json file is an explicit list of days, each
# stating its own city/title/weather directly plus a flat list of that
# day's line items. See CLAUDE.md's "Data" section for the exact shape.
# ============================================================

def to_expense(item: dict[str, object], people_count: int) -> dict[str, object]:
    total_original = item["unitAmount"] * item["quantity"]
    rate = rate_for(item["currency"])
    total_cop = total_original * rate
    per_person_cop = total_cop / people_count
    original_amount = per_person_cop / rate if item["currency"] != "COP" and rate else per_person_cop
    return {
        "category": CATEGORY_BY_EXCEL[item["category"]],
        "title": item["title"], "amount": per_person_cop, "originalAmount": original_amount,
        "currency": item["currency"], "note": item.get("note") or "", "place": item.get("place", ""),
        "date": item.get("date", ""), "link": item.get("link"),
    }


def build_option(doc: dict[str, object]) -> dict[str, object]:
    people_count = doc["peopleCount"]
    days_src = doc["days"]
    city_occurrences: dict[str, int] = {}
    itinerary = []
    for index, day in enumerate(days_src):
        city = day["city"]
        climate_city = day.get("climateCity", city)
        country, emoji = city_country_emoji(city)
        image_url = image_for_day(city, city_occurrences.get(city, 0))
        city_occurrences[city] = city_occurrences.get(city, 0) + 1
        weather = day["weather"]
        packing_fallback = city_climate(climate_city)["packing"]
        has_lodging = any(it["category"] == "Alojamiento" for it in day["items"])
        has_tours = any(it["category"] == "Tours y Excursiones" for it in day["items"])
        is_last = index == len(days_src) - 1
        itinerary.append({
            "dayKey": day["dayKey"], "city": city, "country": country, "emoji": emoji,
            "image": image_url, "title": day["title"], "dayKind": day["dayKind"],
            "climateCity": climate_city,
            "sunrise": weather["sunrise"], "sunset": weather["sunset"], "temp": weather["temp"],
            "weatherIcon": weather["weatherIcon"], "weather": weather["weather"],
            "packing": compute_packing(climate_city, day["dayKind"], is_last, weather["weather"], weather["temp"], has_lodging, has_tours, packing_fallback),
            "weatherUrl": climate_source_url(climate_city), "sunUrl": sun_source_url(climate_city),
            "planNote": None, "planNoteCaption": None,
            "expenses": [to_expense(item, people_count) for item in day["items"]],
        })

    total = sum(e["amount"] for day in itinerary for e in day["expenses"])
    route_override = doc.get("routeOverride")
    if route_override:
        route = route_override
    else:
        # "En el mar" is a placeholder for days at sea, not a real destination —
        # leave it out of the displayed route (the option card's city list).
        route = []
        for day in itinerary:
            if day["city"] == "En el mar":
                continue
            if not route or route[-1] != day["city"]:
                route.append(day["city"])
    return {
        "name": doc["name"], "dates": doc["dates"], "route": " · ".join(route), "days": len(itinerary),
        "total": round(total), "perPerson": round(total), "color": doc["color"], "description": doc["description"],
        "peopleCount": people_count, "itinerary": itinerary,
    }


# ============================================================
# Disney World + Universal Orlando trip — a completely different shape:
# costs are bucketed per category *and* per traveler-type (adults vs.
# children, since Disney/Universal/food price them differently), not one
# row per line item with an explicit date, and the day-by-day plan is a
# fixed 9-day calendar with a per-day "ride plan" note rather than its own
# priced line items. See data/options/orlando-*.json.
# ============================================================
DISNEY_DAYS = [
    ("20 MAR", "Llegada a Orlando", "flight"),
    ("21 MAR", "Magic Kingdom", None),
    ("22 MAR", "EPCOT", None),
    ("23 MAR", "Universal Studios + Islands of Adventure", None),
    ("24 MAR", "Hollywood Studios", None),
    ("25 MAR", "Universal Epic Universe", None),
    ("26 MAR", "Animal Kingdom", None),
    ("27 MAR", "Día libre / compras / piscina", None),
    ("28 MAR", "Check-out y vuelo de regreso", None),
]


def build_disney_option(doc: dict[str, object]) -> dict[str, object]:
    comp = doc["composition"]
    adults_count, children_count = comp["adultsCount"], comp["childrenCount"]
    has_adolescent, child_age_label = comp["hasAdolescent"], comp["childAgeLabel"]
    people_count = adults_count + children_count
    rate_usd_to_cop = doc["rateUsdToCop"]
    b = doc["budget"]

    def blended_expense(category: str, title: str, unit_usd: float, qty: int, note: str, link: str | None = None) -> dict[str, object]:
        """A cost bucket for one traveler type, shown at its blended
        per-person share of the option's total headcount — the same
        total/peopleCount split every other option uses, so the day and
        category views keep reconciling with the option's headline total."""
        total_usd = unit_usd * qty
        total_cop = total_usd * rate_usd_to_cop
        per_person_cop = total_cop / people_count
        clarified_note = f"{note} El monto de acá es el promedio repartido entre las {people_count} personas del grupo, no un precio individual."
        return {
            "category": category, "title": title, "amount": round(per_person_cop),
            "originalAmount": round(total_usd / people_count, 2), "currency": "USD",
            "note": clarified_note, "place": "Orlando", "date": "", "link": link,
        }

    def shared_expense(category: str, title: str, total_usd: float, note: str, link: str | None = None) -> dict[str, object]:
        return blended_expense(category, title, total_usd, 1, note, link)

    adult_label = "adulto (incluye al adolescente de 13 años)" if has_adolescent else "adulto"

    def ticket_expense(category: str, title: str, adult_unit: float, child_unit: float, detail: str, link: str | None = None) -> dict[str, object]:
        total_usd = adult_unit * adults_count + child_unit * children_count
        per_person_usd = total_usd / people_count
        note = (
            f"{detail} Precio real: US${adult_unit:.2f} por {adult_label}, US${child_unit:.2f} para el niño de "
            f"{child_age_label} años. El monto de acá es un promedio entre los {people_count} del grupo, no lo que paga cada quien."
        )
        return {
            "category": category, "title": title, "amount": round(per_person_usd * rate_usd_to_cop),
            "originalAmount": round(per_person_usd, 2), "currency": "USD",
            "note": note, "place": "Orlando", "date": "", "link": link,
        }

    AVIANCA = "https://www.avianca.com/co/es/vuelos-desde-bogota-a-orlando"
    HILTON = "https://www.hilton.com/en/hotels/mcofhdt-doubletree-suites-orlando-disney-springs/"
    DISNEY_TICKETS = "https://disneyworld.disney.go.com/admission/tickets/"
    UNIVERSAL_TICKETS = "https://www.universalorlando.com/web/en/us/tickets-packages/park-tickets"
    EPIC_TICKETS = "https://www.universalorlando.com/web/en/us/tickets-packages/park-tickets/epic-products"

    flight_roundtrip_total = b["flightAdultUnit"] * adults_count + b["flightChildUnit"] * children_count

    days: list[dict[str, object]] = []
    for index, (day_key_, title, day_kind) in enumerate(DISNEY_DAYS):
        is_first, is_last = index == 0, index == len(DISNEY_DAYS) - 1
        expenses: list[dict[str, object]] = []

        if is_first:
            expenses.append(shared_expense(
                "Transporte", "Vuelo internacional Bogotá ⇄ Orlando (ida y vuelta)", flight_roundtrip_total,
                f"Avianca, estimado temporada Semana Santa. ${b['flightAdultUnit']:.0f}/persona (adultos y niño de {child_age_label} años por igual).",
                AVIANCA,
            ))
            expenses.append(shared_expense(
                "Alojamiento", "Hotel DoubleTree Suites — costo total (8 noches)", b["hotelTotal"],
                "Recomendado: DoubleTree Suites, Disney Springs Resort Area — shuttle gratis a los 4 parques Disney, 4★.",
                HILTON,
            ))
            # PhotoPass folded into souvenirs (one combined "extras" line)
            # instead of its own row — the family isn't buying it separately.
            expenses.append(shared_expense(
                "Otros", "Souvenirs (estimado)", b["souvenirs"] + b["photopass"],
                "Estimado para todo el viaje del subgrupo. Incluye PhotoPass.",
            ))
            expenses.append(shared_expense(
                "Otros", "Propinas y varios", b["tips"],
                "Estimado para todo el viaje del subgrupo.",
            ))

        if title == "Magic Kingdom":
            expenses.append(ticket_expense(
                "Tours", "Tickets Disney World", b["disneyAdultUnit"], b["disneyChildUnit"],
                "Pase de 4 días, 1 parque/día, sin Park Hopper (tarifa oficial temporada pico, MouseSavers).",
                DISNEY_TICKETS,
            ))
        if title == "Universal Studios + Islands of Adventure":
            expenses.append(ticket_expense(
                "Tours", "Tickets Universal (Studios + Islands of Adventure)", b["universalAdultUnit"], b["universalChildUnit"],
                "1 día Park-to-Park. No incluye Epic Universe (aparte, más adelante).",
                UNIVERSAL_TICKETS,
            ))
            expenses.append(shared_expense(
                "Transporte", "Uber ida y vuelta — Universal Studios + Islands of Adventure", b["uberTotal"] / 2,
                "Estimado del grupo completo para este día. Disney va en shuttle gratis del hotel; solo Universal/Epic Universe necesitan Uber.",
            ))
        if title == "Universal Epic Universe":
            expenses.append(ticket_expense(
                "Tours", "Ticket Epic Universe", b["epicAdultUnit"], b["epicChildUnit"],
                "1 día, 1 parque — el 4to parque de Universal, abierto desde may-2025. Niño estimado a ~97% de la tarifa adulto.",
                EPIC_TICKETS,
            ))
            expenses.append(shared_expense(
                "Transporte", "Uber ida y vuelta — Universal Epic Universe", b["uberTotal"] / 2,
                "Estimado del grupo completo para este día. Disney va en shuttle gratis del hotel; solo Universal/Epic Universe necesitan Uber.",
            ))

        # Comida — 8 de los 9 días (todos menos el de llegada, cubierto por
        # las comidas del vuelo).
        if not is_first:
            expenses.append(ticket_expense(
                "Comida", "Comida del día (desayuno, almuerzo y cena)", b["foodAdultPerDay"], b["foodChildPerDay"],
                "Estimado diario de comida (no incluido en tickets ni hotel).",
            ))

        if is_last:
            expenses.append({
                "category": "Transporte", "title": "Vuelo internacional Orlando → Bogotá (regreso)", "amount": 0,
                "originalAmount": 0, "currency": "USD",
                "note": "Incluido en la tarifa ida y vuelta del vuelo de ida.", "place": "Orlando", "date": "", "link": None,
            })

        climate = city_climate("Orlando")
        day_plan = doc["dayPlans"][index]
        has_tours = any(e["category"] == "Tours" for e in expenses)
        has_lodging = any(e["category"] == "Alojamiento" for e in expenses)
        day_kind_final = "flight" if is_first else None
        days.append({
            "dayKey": day_key_, "city": "Orlando", "country": "Estados Unidos", "emoji": "🇺🇸",
            "image": image_for_day("Orlando", index),
            "title": title, "dayKind": day_kind_final,
            "climateCity": "Orlando",
            "sunrise": climate["sunrise"], "sunset": climate["sunset"], "temp": climate["temp"],
            "weatherIcon": climate["weatherIcon"], "weather": climate["weather"],
            "packing": compute_packing("Orlando", day_kind_final, is_last, climate["weather"], climate["temp"], has_lodging, has_tours, climate["packing"]),
            "weatherUrl": climate_source_url("Orlando"), "sunUrl": sun_source_url("Orlando"),
            "planNote": day_plan["planNote"], "planNoteCaption": day_plan["planNoteCaption"],
            "expenses": expenses,
        })

    total = sum(e["amount"] for day in days for e in day["expenses"])

    # The headline "perPerson" above is a blended average (total ÷
    # peopleCount) — perPersonByType gives the real figure for each fare
    # tier (shared costs split equally per head, fare-specific costs kept at
    # their real per-type price), so adults_count·adult + children_count·child
    # reproduces the exact group total, just not blended together.
    shared_per_person = (b["hotelTotal"] + b["uberTotal"] + b["photopass"] + b["souvenirs"] + b["tips"]) / people_count
    food_days = len(DISNEY_DAYS) - 1
    adult_total_usd = b["flightAdultUnit"] + shared_per_person + b["disneyAdultUnit"] + b["universalAdultUnit"] + b["epicAdultUnit"] + b["foodAdultPerDay"] * food_days
    child_total_usd = b["flightChildUnit"] + shared_per_person + b["disneyChildUnit"] + b["universalChildUnit"] + b["epicChildUnit"] + b["foodChildPerDay"] * food_days
    per_person_by_type = [{"label": "Adulto", "amount": round(adult_total_usd * rate_usd_to_cop)}]
    if has_adolescent:
        per_person_by_type.append({"label": "Adolescente (13)", "amount": round(adult_total_usd * rate_usd_to_cop)})
    per_person_by_type.append({"label": f"Niño ({child_age_label})", "amount": round(child_total_usd * rate_usd_to_cop)})

    return {
        "name": doc["name"], "dates": "20 – 28 mar 2027", "route": "Orlando", "days": len(days),
        "total": round(total), "perPerson": round(total), "color": doc["color"], "description": doc["description"],
        "peopleCount": people_count, "perPersonByType": per_person_by_type, "itinerary": days,
    }


# ============================================================
# Japón — the only option with no source spreadsheet at all: the itinerary
# came directly from a written plan (real flight quotes, estimated
# hotel/park-ticket/local-transport costs). data/options/japon.json lists
# it day by day, each with its own explicit city/title/dayKind, and a flat
# list of items — plain currency/unitAmount/quantity like everywhere else,
# or a `tiers` array for the two park tickets that price adults/juniors/
# children differently.
# ============================================================

def build_japan_expense(item: dict[str, object], people_count: int, rate_usd_to_cop: float, rate_jpy_to_cop: float) -> dict[str, object]:
    currency = item["currency"]
    link = item.get("link")
    if "tiers" in item:
        total_usd = sum(t["unitAmount"] * t["count"] for t in item["tiers"])
        per_person_usd = total_usd / people_count
        price_bits = ", ".join(f"US${t['unitAmount']:.2f} {t['label']}" for t in item["tiers"])
        note = f"{item['note']} Precio real: {price_bits}. El monto de acá es un promedio entre los {people_count} del grupo, no lo que paga cada quien."
        return {
            "category": item["category"], "title": item["title"],
            "amount": round(per_person_usd * rate_usd_to_cop), "originalAmount": round(per_person_usd, 2),
            "currency": "USD", "note": note, "place": item.get("place", "Japón"), "date": "", "link": link,
        }
    total = item["unitAmount"] * item["quantity"]
    rate = rate_jpy_to_cop if currency == "JPY" else (rate_usd_to_cop if currency == "USD" else 1.0)
    per_person = (total * rate) / people_count
    return {
        "category": item["category"], "title": item["title"],
        "amount": round(per_person), "originalAmount": round((total / people_count), 2) if currency != "COP" else round(per_person),
        "currency": currency, "note": item["note"], "place": item.get("place", "Japón"), "date": "", "link": link,
    }


def build_japan_option(doc: dict[str, object], rate_usd_to_cop: float, rate_jpy_to_cop: float) -> dict[str, object]:
    people_count = doc["peopleCount"]
    jpy_per_usd = doc["jpyPerUsd"]
    days: list[dict[str, object]] = []
    day_docs = doc["days"]
    for index, day_doc in enumerate(day_docs):
        is_last = index == len(day_docs) - 1
        city = day_doc["city"]
        climate = city_climate(city)
        expenses = [build_japan_expense(item, people_count, rate_usd_to_cop, rate_jpy_to_cop) for item in day_doc["items"]]
        has_lodging = any(e["category"] == "Alojamiento" for e in expenses)
        has_tours = any(e["category"] == "Tours" for e in expenses)
        day_kind = day_doc["dayKind"]
        country, emoji = city_country_emoji(city)
        days.append({
            "dayKey": day_doc["dayKey"], "city": city, "country": country, "emoji": emoji,
            "image": image_for_day(city, index),
            "title": day_doc["title"], "dayKind": day_kind, "climateCity": city,
            "sunrise": climate["sunrise"], "sunset": climate["sunset"], "temp": climate["temp"],
            "weatherIcon": climate["weatherIcon"], "weather": climate["weather"],
            "packing": compute_packing(city, day_kind, is_last, climate["weather"], climate["temp"], has_lodging, has_tours, climate["packing"]),
            "weatherUrl": climate_source_url(city), "sunUrl": sun_source_url(city),
            "planNote": None, "planNoteCaption": None,
            "expenses": expenses,
        })

    total = sum(e["amount"] for day in days for e in day["expenses"])

    # perPersonByType: same-cost items (flights, hotel share, shinkansen,
    # comida, extras) are identical for everyone; only the two park tickets
    # differ by fare tier. Real total per traveler type = the shared costs
    # + that type's own real ticket tiers (not blended).
    def jpy_to_usd(jpy: float) -> float:
        return jpy / jpy_per_usd

    shared_per_person_usd = 520 / people_count + 750 / people_count + 240 / people_count + jpy_to_usd(14720) * 2 + 40 * 9
    shared_per_person_cop = (
        shared_per_person_usd * rate_usd_to_cop + 2017294 + 2409162
        + (136080 / people_count) * rate_jpy_to_cop + (81935 / people_count) * rate_jpy_to_cop
    )
    adult_tickets_usd = jpy_to_usd(10900 * 2) + jpy_to_usd(11900)
    adolescent_tickets_usd = jpy_to_usd(9000 * 2) + jpy_to_usd(11900)
    child_tickets_usd = jpy_to_usd(5600 * 2) + jpy_to_usd(5700)
    per_person_by_type = [
        {"label": "Adulto", "amount": round(shared_per_person_cop + adult_tickets_usd * rate_usd_to_cop)},
        {"label": "Adolescente (13)", "amount": round(shared_per_person_cop + adolescent_tickets_usd * rate_usd_to_cop)},
        {"label": "Niño (9)", "amount": round(shared_per_person_cop + child_tickets_usd * rate_usd_to_cop)},
    ]

    # "En vuelo" is a placeholder for the transit day, not a real destination —
    # left out of the route, same treatment as "En el mar" in the cruise options.
    route: list[str] = []
    for day in days:
        if day["city"] == "En vuelo":
            continue
        if not route or route[-1] != day["city"]:
            route.append(day["city"])

    return {
        "name": doc["name"], "dates": doc["dates"], "route": " · ".join(route),
        "days": len(days), "total": round(total), "perPerson": round(total),
        "color": doc["color"], "description": doc["description"],
        "peopleCount": people_count, "perPersonByType": per_person_by_type, "itinerary": days,
    }


def main() -> None:
    options = []
    for file_id in ["europa", "alpes-suizos", "crucero-en-pareja"]:
        options.append(build_option(load_json(DATA / "options" / f"{file_id}.json")))
    for file_id in ["orlando-jero", "orlando-pachito-vale"]:
        options.append(build_disney_option(load_json(DATA / "options" / f"{file_id}.json")))

    rates = []
    for code, entry in RATES_DOC["rates"].items():
        rates.append({
            "code": code, "label": entry["label"], "symbol": entry["symbol"],
            "rate": round(entry["baseRate"] * RATES_DOC["markup"], 2), "sourceUrl": entry["sourceUrl"],
        })
    usd_rate = next(r["rate"] for r in rates if r["code"] == "USD")
    jpy_rate = next(r["rate"] for r in rates if r["code"] == "JPY")
    options.append(build_japan_option(load_json(DATA / "options" / "japon.json"), usd_rate, jpy_rate))

    ITINERARY_OUTPUT.write_text(
        "// Generated by scripts/generate_data.py — do not edit manually.\n"
        "export type GeneratedExpense = { category: string; title: string; amount: number; originalAmount: number; currency: string; note: string; place: string; date: string; link: string | null };\n"
        "export type GeneratedDay = { dayKey: string; city: string; country: string; emoji: string; image: string; title: string; dayKind: 'flight' | 'embark' | null; climateCity: string; sunrise: string; sunset: string; temp: string; weatherIcon: string; weather: string; packing: string[]; weatherUrl: string | null; sunUrl: string | null; planNote: string | null; planNoteCaption: string | null; expenses: GeneratedExpense[] };\n"
        "export type GeneratedOption = { name: string; dates: string; route: string; days: number; total: number; perPerson: number; color: string; description: string; peopleCount: number; perPersonByType?: { label: string; amount: number }[]; itinerary: GeneratedDay[] };\n"
        "export type ExchangeRate = { code: string; label: string; symbol: string; rate: number; sourceUrl: string };\n"
        f"export const generatedOptions: GeneratedOption[] = {ts(options)};\n"
        f"export const exchangeRates: ExchangeRate[] = {ts(rates)};\n"
        f"export const ratesUpdatedAt: string = {ts(RATES_DOC['updatedAt'])};\n",
        encoding="utf-8",
    )
    print(f"Generated {len(options)} itinerary options at {ITINERARY_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
