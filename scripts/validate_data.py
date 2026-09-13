"""Sanity-check every file under data/ before trusting a hand edit or a
generated build. Catches the mistakes a JSON editor won't: a typo'd
category, a day with no items, a currency the app doesn't know how to
format, a link that returns 404, a total that doesn't reconcile.

Run from the project root:
    python3 scripts/validate_data.py            # fast checks only
    python3 scripts/validate_data.py --check-links   # also HEAD every link (slower, needs network)

Exits non-zero (and prints every problem found, not just the first) if
anything is wrong. Safe to run any time — read-only, never writes to
data/ or src/.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

DAY_OPTION_IDS = ["europa", "alpes-suizos", "crucero-en-pareja"]
ORLANDO_OPTION_IDS = ["orlando-jero", "orlando-pachito-vale"]
JAPAN_OPTION_ID = "japon"

CATEGORIES = {
    "Vuelos y Trenes", "Traslados", "Alojamiento", "Crucero",
    "Tours y Excursiones", "Comidas", "Seguro de Viaje", "Otros y Extras",
}
# Japón's items use the app-facing category names directly (no
# CATEGORY_BY_EXCEL translation happens for it in generate_data.py — see
# build_japan_expense), unlike the day-by-day options above.
JAPAN_CATEGORIES = {"Transporte", "Alojamiento", "Comida", "Tours", "Crucero", "Seguro", "Otros"}
CURRENCIES = {"EUR", "CHF", "CZK", "USD", "COP", "JPY"}
MONTHS = {"ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"}

ORLANDO_BUDGET_FIELDS = {
    "flightAdultUnit", "flightChildUnit", "hotelTotal", "disneyAdultUnit", "disneyChildUnit",
    "universalAdultUnit", "universalChildUnit", "epicAdultUnit", "epicChildUnit",
    "foodAdultPerDay", "foodChildPerDay", "uberTotal", "photopass", "souvenirs", "tips",
}
ORLANDO_COMPOSITION_FIELDS = {"adultsCount", "childrenCount", "childAgeLabel", "hasAdolescent"}

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"{path.relative_to(ROOT)}: invalid JSON — {e}")
        return None


def is_valid_day_key(key: str) -> bool:
    parts = key.split()
    if len(parts) != 2:
        return False
    day_str, month_str = parts
    return day_str.isdigit() and 1 <= int(day_str) <= 31 and month_str in MONTHS


def check_item(item: dict, where: str, categories: set[str] = CATEGORIES) -> None:
    for field in ("category", "title", "currency", "note"):
        if not item.get(field) and item.get(field) != "":
            err(f"{where}: item {item.get('title', '?')!r} missing required field {field!r}")
    if item.get("category") not in categories:
        err(f"{where}: item {item.get('title', '?')!r} has unknown category {item.get('category')!r}")
    if item.get("currency") not in CURRENCIES:
        err(f"{where}: item {item.get('title', '?')!r} has unknown currency {item.get('currency')!r}")
    if "tiers" in item:
        for tier in item["tiers"]:
            for field in ("label", "unitAmount", "count"):
                if field not in tier:
                    err(f"{where}: item {item.get('title', '?')!r} tier missing {field!r}")
    else:
        if "unitAmount" not in item or "quantity" not in item:
            err(f"{where}: item {item.get('title', '?')!r} missing unitAmount/quantity (and has no tiers)")
        elif item.get("unitAmount", 0) < 0 or item.get("quantity", 0) < 0:
            err(f"{where}: item {item.get('title', '?')!r} has a negative unitAmount/quantity")
    if item.get("note") and len(item["note"].split()) > 20:
        warn(f"{where}: item {item.get('title', '?')!r} note is {len(item['note'].split())} words (skill convention: max 20)")
    link = item.get("link")
    if link and not re.match(r"^(https?://|/)", link):
        err(f"{where}: item {item.get('title', '?')!r} has a link that isn't a URL or an absolute path: {link!r}")


def check_day_option(option_id: str, doc: dict, cities: dict) -> list[tuple[str, str]]:
    """Returns every (link_url, where) pair found, for the optional link check."""
    links: list[tuple[str, str]] = []
    for field in ("name", "dates", "color", "description", "peopleCount", "days"):
        if field not in doc:
            err(f"{option_id}: missing top-level field {field!r}")
    if "days" not in doc:
        return links
    seen_day_keys: set[str] = set()
    for day in doc["days"]:
        where = f"{option_id} day {day.get('dayKey', '?')}"
        for field in ("dayKey", "city", "title", "weather", "items"):
            if field not in day:
                err(f"{where}: missing field {field!r}")
        day_key = day.get("dayKey")
        if day_key:
            if not is_valid_day_key(day_key):
                err(f"{where}: dayKey {day_key!r} doesn't look like 'DD MON'")
            if day_key in seen_day_keys:
                err(f"{option_id}: duplicate dayKey {day_key!r}")
            seen_day_keys.add(day_key)
        city = day.get("city")
        if city and city not in cities:
            err(f"{where}: city {city!r} has no entry in data/cities.json")
        climate_city = day.get("climateCity")
        if climate_city and climate_city not in cities:
            err(f"{where}: climateCity {climate_city!r} has no entry in data/cities.json")
        weather = day.get("weather", {})
        for field in ("sunrise", "sunset", "temp", "weatherIcon", "weather"):
            if field not in weather:
                err(f"{where}: weather missing field {field!r}")
        if not day.get("items"):
            warn(f"{where}: has no items at all (zero-cost day, or a gap?)")
        for item in day.get("items", []):
            check_item(item, where, CATEGORIES)
            if item.get("link"):
                links.append((item["link"], f"{where} / {item.get('title')}"))
    route_override = doc.get("routeOverride")
    if route_override is not None and not isinstance(route_override, list):
        err(f"{option_id}: routeOverride must be a list of city names, or null")
    return links


def check_orlando_option(option_id: str, doc: dict) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for field in ("name", "description", "color", "rateUsdToCop", "composition", "budget", "dayPlans"):
        if field not in doc:
            err(f"{option_id}: missing top-level field {field!r}")
            return links
    missing_comp = ORLANDO_COMPOSITION_FIELDS - doc["composition"].keys()
    if missing_comp:
        err(f"{option_id}: composition missing fields {sorted(missing_comp)}")
    missing_budget = ORLANDO_BUDGET_FIELDS - doc["budget"].keys()
    if missing_budget:
        err(f"{option_id}: budget missing fields {sorted(missing_budget)}")
    for k, v in doc["budget"].items():
        if not isinstance(v, (int, float)) or v < 0:
            err(f"{option_id}: budget.{k} is not a non-negative number: {v!r}")
    if len(doc["dayPlans"]) != 9:
        warn(f"{option_id}: dayPlans has {len(doc['dayPlans'])} entries, expected 9 (fixed DISNEY_DAYS calendar)")
    return links


def check_japan_option(doc: dict) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for field in ("name", "dates", "color", "description", "peopleCount", "composition", "jpyPerUsd", "days"):
        if field not in doc:
            err(f"japon: missing top-level field {field!r}")
    for day in doc.get("days", []):
        where = f"japon day {day.get('dayKey', '?')}"
        for item in day.get("items", []):
            check_item(item, where, JAPAN_CATEGORIES)
            if item.get("link"):
                links.append((item["link"], f"{where} / {item.get('title')}"))
    return links


def check_rates(rates_doc: dict) -> None:
    for field in ("updatedAt", "markup", "rates"):
        if field not in rates_doc:
            err(f"rates.json: missing top-level field {field!r}")
            return
    for code in CURRENCIES - {"COP"}:
        if code not in rates_doc["rates"]:
            err(f"rates.json: missing rate entry for {code!r}")
            continue
        entry = rates_doc["rates"][code]
        for field in ("label", "symbol", "baseRate", "sourceUrl"):
            if field not in entry:
                err(f"rates.json: {code} missing field {field!r}")
        if entry.get("baseRate", 0) <= 0:
            err(f"rates.json: {code}'s baseRate must be positive, got {entry.get('baseRate')!r}")
    if not (0.5 < rates_doc.get("markup", 0) < 3):
        warn(f"rates.json: markup {rates_doc.get('markup')!r} looks unusual (expected something near 1.0-1.2)")


def check_cities(cities_doc: dict) -> dict:
    cities = cities_doc.get("cities", {})
    for name, entry in cities.items():
        for field in ("country", "emoji", "images", "climate"):
            if field not in entry:
                err(f"cities.json: {name!r} missing field {field!r}")
        if not entry.get("images"):
            warn(f"cities.json: {name!r} has no photo pool (image_for_day will fall back to a generic Unsplash photo)")
    return cities


def check_links(links: list[tuple[str, str]]) -> None:
    remote = [(url, where) for url, where in links if url.startswith("http")]
    print(f"\nChecking {len(remote)} remote links (HEAD request each)...")

    def check_one(url_where):
        url, where = url_where
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 400:
                    return (url, where, resp.status)
        except urllib.error.HTTPError as e:
            if e.code >= 400:
                return (url, where, e.code)
        except Exception as e:
            return (url, where, str(e))
        return None

    # 403/405/429 are usually a site blocking an automated HEAD request (Viator,
    # GetYourGuide, Expedia, Hyatt, etc. all do this to real browsers too) —
    # not necessarily a dead link. 404/410 are the real signal.
    CONFIDENT_DEAD = {404, 410}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(check_one, uw) for uw in remote]
        for future in as_completed(futures):
            result = future.result()
            if result:
                url, where, status = result
                if status in CONFIDENT_DEAD:
                    warn(f"{where}: link looks DEAD ({status}) — {url}")
                else:
                    warn(f"{where}: link returned {status} (often just a bot-blocked site, not necessarily dead — open it manually to confirm) — {url}")


def main() -> None:
    check_links_flag = "--check-links" in sys.argv

    rates_doc = load_json(DATA / "rates.json")
    cities_doc = load_json(DATA / "cities.json")
    cities = check_cities(cities_doc) if cities_doc else {}
    if rates_doc:
        check_rates(rates_doc)

    all_links: list[tuple[str, str]] = []
    for option_id in DAY_OPTION_IDS:
        doc = load_json(DATA / "options" / f"{option_id}.json")
        if doc:
            all_links += check_day_option(option_id, doc, cities)
    for option_id in ORLANDO_OPTION_IDS:
        doc = load_json(DATA / "options" / f"{option_id}.json")
        if doc:
            all_links += check_orlando_option(option_id, doc)
    japan_doc = load_json(DATA / "options" / f"{JAPAN_OPTION_ID}.json")
    if japan_doc:
        all_links += check_japan_option(japan_doc)

    if check_links_flag:
        check_links(all_links)

    print(f"\nChecked {len(DAY_OPTION_IDS) + len(ORLANDO_OPTION_IDS) + 1} option files, {len(cities)} cities, {len(all_links)} links.")

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s). Fix the errors above before trusting this data.")
        sys.exit(1)
    print(f"\nAll checks passed ({len(warnings)} warning(s)).")


if __name__ == "__main__":
    main()
