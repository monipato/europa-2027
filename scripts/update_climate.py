"""Refresh each day's real sunrise/sunset/weather, embedded directly on that
day in its option's JSON file, then regenerate the app.

Run from the project root:
    python3 scripts/update_climate.py

What "live" means here, since no real forecast exists ~a year out:
  - Sunrise/sunset are exact astronomy — different per exact calendar date,
    fetched from the free, keyless api.sunrise-sunset.org and converted
    from UTC to local time using a fixed UTC+2 (CEST) offset, which every
    city in this itinerary shares in April/May.
  - Temperature range and the dominant weather condition are real seasonal
    normals: Open-Meteo's free archive API, averaged over a +/-7 day window
    around each exact calendar date across the last 3 years, per city.
  - Both vary per (city, day), not just per city — this script reads every
    day of data/options/{europa,alpes-suizos,crucero-en-pareja}.json,
    fetches weather for its `climateCity` (falling back to `city` if that
    key is absent — see "Day trips" below), and writes the result straight
    into that day's own `weather` object. A city visited on two different
    dates gets two different readings.
  - Orlando and Japón are NOT touched by this script — both use a single
    seasonal estimate (data/cities.json's per-city `climate`), which is
    accurate enough for them and isn't meant to be this precise; edit
    those by hand if they ever need refining.
  - data/cities.json's per-city `climate` field is also refreshed here,
    from each city's first-occurrence date across the 3 options above —
    it's dead weight for those cities today (their days already carry
    their own weather), but it's the fallback a brand-new day would get
    before its own exact-date fetch has run once.
  - "packing" tips are editorial, not fetched data, and are left untouched.

Day trips: a day whose weather belongs to a different place than the day's
own `city` (e.g. an Alpine excursion out of a city-base day) carries an
explicit `climateCity` field — see data/options/alpes-suizos.json's "02 MAY"
for an example. Add the excursion's own coordinates to CITY_COORDS below
the same as any other city.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OPTION_IDS = ["europa", "alpes-suizos", "crucero-en-pareja"]

TRIP_YEAR = 2027
LOCAL_UTC_OFFSET_HOURS = 2  # CEST, shared by every city in this itinerary in April/May
HISTORY_YEARS = [2022, 2023, 2024]
WINDOW_DAYS = 7  # +/- around each exact date, per history year

CITY_COORDS = {
    "Zúrich": (47.3769, 8.5417),
    "París": (48.8566, 2.3522),
    "Barcelona": (41.3874, 2.1686),
    "La Spezia": (44.1024, 9.8241),
    "Salerno": (40.6824, 14.7681),
    "Zadar": (44.1194, 15.2314),
    "Venecia": (45.4408, 12.3155),
    "Roma": (41.9028, 12.4964),
    "Praga": (50.0755, 14.4378),
    "Berlín": (52.5200, 13.4050),
    "Múnich": (48.1351, 11.5820),
    "Milán": (45.4642, 9.1900),
    "Florencia": (43.7696, 11.2558),
    "Colmar": (48.0794, 7.3585),
    "Basilea": (47.5596, 7.5886),
    "En el mar": (40.5, 15.5),
    # Day-trip destinations, not base cities (see the module docstring).
    "Jungfraujoch": (46.5475, 7.9847),  # summit, not the Interlaken valley
    "Diavolezza": (46.4106, 9.9671),  # mountain station, not the Pontresina valley
}

WMO_ICON_LABEL = {
    0: ("☀️", "Soleado"),
    1: ("🌤️", "Mayormente soleado"),
    2: ("⛅", "Parcialmente nublado"),
    3: ("☁️", "Nublado"),
    45: ("🌫️", "Neblina"), 48: ("🌫️", "Neblina"),
    51: ("🌦️", "Llovizna"), 53: ("🌦️", "Llovizna"), 55: ("🌦️", "Llovizna"),
    61: ("🌧️", "Lluvia"), 63: ("🌧️", "Lluvia"), 65: ("🌧️", "Lluvia"),
    80: ("🌦️", "Chubascos"), 81: ("🌦️", "Chubascos"), 82: ("🌧️", "Chubascos fuertes"),
    95: ("⛈️", "Tormenta"), 96: ("⛈️", "Tormenta"), 99: ("⛈️", "Tormenta"),
}
DEFAULT_ICON_LABEL = ("⛅", "Parcialmente nublado")

MONTH_NUMBER = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}


def day_key_to_date(day_key: str) -> date:
    """"30 ABR" -> date(2027, 4, 30)."""
    day_str, month_str = day_key.split()
    return date(TRIP_YEAR, MONTH_NUMBER[month_str.upper()], int(day_str))


def load_option(option_id: str) -> dict:
    return json.loads((DATA / "options" / f"{option_id}.json").read_text(encoding="utf-8"))


def save_option(option_id: str, doc: dict) -> None:
    (DATA / "options" / f"{option_id}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_city_day_pairs(docs: dict[str, dict]) -> list[tuple[str, str]]:
    """Every (climateCity, dayKey) pair actually used across the 3 Europa-
    shaped options, in first-seen order, deduplicated — climateCity, not
    city, so a day-trip day fetches weather for the excursion, not the base
    city the day is otherwise filed under."""
    seen: dict[tuple[str, str], None] = {}
    for doc in docs.values():
        for day in doc["days"]:
            climate_city = day.get("climateCity", day["city"])
            seen[(climate_city, day["dayKey"])] = None
    return list(seen.keys())


def fetch_json(url: str, attempts: int = 4) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; patitours-climate-update/1.0)"})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    raise SystemExit(f"update_climate.py: failed to fetch {url} after {attempts} attempts: {last_error}")


def fetch_sun_times(lat: float, lon: float, on_date: date) -> tuple[str, str]:
    url = f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&date={on_date}&formatted=0"
    data = fetch_json(url)["results"]
    return _to_local_12h(data["sunrise"]), _to_local_12h(data["sunset"])


def _to_local_12h(iso_utc: str) -> str:
    hour_utc = int(iso_utc[11:13])
    minute = iso_utc[14:16]
    hour_local = (hour_utc + LOCAL_UTC_OFFSET_HOURS) % 24
    suffix = "AM" if hour_local < 12 else "PM"
    hour_12 = hour_local % 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12}:{minute} {suffix}"


def fetch_climate_normal(lat: float, lon: float, on_date: date) -> tuple[str, str, str]:
    """Returns (temp range string, weatherIcon, weather label), averaged over
    a window of days around on_date's month/day across HISTORY_YEARS."""
    highs: list[float] = []
    lows: list[float] = []
    codes: list[int] = []
    for year in HISTORY_YEARS:
        center = date(year, on_date.month, on_date.day)
        start = center - timedelta(days=WINDOW_DAYS)
        end = center + timedelta(days=WINDOW_DAYS)
        url = (
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
            "&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=UTC"
        )
        daily = fetch_json(url)["daily"]
        highs.extend(v for v in daily["temperature_2m_max"] if v is not None)
        lows.extend(v for v in daily["temperature_2m_min"] if v is not None)
        codes.extend(v for v in daily["weathercode"] if v is not None)
        time.sleep(0.5)
    avg_low = round(sum(lows) / len(lows))
    avg_high = round(sum(highs) / len(highs))
    dominant_code = Counter(codes).most_common(1)[0][0]
    icon, label = WMO_ICON_LABEL.get(dominant_code, DEFAULT_ICON_LABEL)
    return f"{avg_low}–{avg_high}°C", icon, label


MAX_WORKERS = 8  # concurrent (city, day) fetches — polite to the free APIs, still a big speedup over serial


def _fetch_one(city: str, day_key: str) -> tuple[str, str, dict[str, str]]:
    lat, lon = CITY_COORDS[city]
    on_date = day_key_to_date(day_key)
    sunrise, sunset = fetch_sun_times(lat, lon, on_date)
    temp, icon, weather = fetch_climate_normal(lat, lon, on_date)
    return city, day_key, {"sunrise": sunrise, "sunset": sunset, "temp": temp, "weatherIcon": icon, "weather": weather}


def main() -> None:
    docs = {option_id: load_option(option_id) for option_id in OPTION_IDS}
    pairs = collect_city_day_pairs(docs)
    print(f"Found {len(pairs)} (city, day) pairs across {len(OPTION_IDS)} options.")

    fetchable = [(city, day_key) for city, day_key in pairs if city in CITY_COORDS]
    for city, day_key in pairs:
        if city not in CITY_COORDS:
            print(f"  skipping {city!r} ({day_key}) — no coordinates on file (add one to CITY_COORDS)")

    by_day: dict[str, dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, city, day_key): (city, day_key) for city, day_key in fetchable}
        for future in as_completed(futures):
            result_city, result_day_key, fields = future.result()
            by_day[f"{result_city}|{result_day_key}"] = fields
            print(f"  {result_city} ({result_day_key}): {fields['sunrise']}-{fields['sunset']}  {fields['temp']}  {fields['weatherIcon']} {fields['weather']}")

    # Write straight into each day's own `weather` object.
    for option_id, doc in docs.items():
        updated = 0
        for day in doc["days"]:
            climate_city = day.get("climateCity", day["city"])
            key = f"{climate_city}|{day['dayKey']}"
            if key in by_day:
                day["weather"] = by_day[key]
                updated += 1
        save_option(option_id, doc)
        print(f"{option_id}: updated {updated}/{len(doc['days'])} days")

    # Per-city fallback in data/cities.json, from each city's first-occurrence
    # date — dead weight for cities whose every day already has its own
    # reading, but a reasonable starting point for a brand-new day before its
    # own exact-date fetch has run.
    cities_path = DATA / "cities.json"
    cities_doc = json.loads(cities_path.read_text(encoding="utf-8"))
    by_city_first_date: dict[str, str] = {}
    for city, day_key in pairs:
        if f"{city}|{day_key}" in by_day:
            by_city_first_date.setdefault(city, day_key)
    for city, entry in cities_doc["cities"].items():
        first_key = by_city_first_date.get(city)
        if first_key is None or "climate" not in entry:
            continue
        fields = by_day[f"{city}|{first_key}"]
        entry["climate"].update(fields)
    cities_path.write_text(json.dumps(cities_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated per-city fallback climate in {cities_path.relative_to(ROOT)}")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_data.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
