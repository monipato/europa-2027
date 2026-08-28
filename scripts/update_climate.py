"""Refresh CITY_CLIMATE / CITY_CLIMATE_BY_DAY in generate_data.py from live
sources, then regenerate the app.

Run from the project root:
    python3 scripts/update_climate.py

Unlike exchange rates, this data does not live in the Excel workbook — it's
plain Python dicts in scripts/generate_data.py. This script re-derives the
values and rewrites those dict blocks in place (a text-level edit, not an
XML one — see `_rewrite_dict_block` below), then calls generate_data.py
exactly like update_rates.py does.

What "live" means here, since no real forecast exists ~a year out:
  - Sunrise/sunset are exact astronomy — different per exact calendar date,
    fetched from the free, keyless api.sunrise-sunset.org and converted
    from UTC to local time using a fixed UTC+2 (CEST) offset, which every
    city in this itinerary shares in April/May.
  - Temperature range and the dominant weather condition are real seasonal
    normals: Open-Meteo's free archive API, averaged over a +/-7 day window
    around each exact calendar date across the last 3 years, per city.
  - Both vary per (city, day), not just per city: this script imports
    generate_data.py itself to walk every option's built itinerary and
    collect the actual (city, dayKey) pairs in use — so a city visited on
    two different dates gets two different climate readings, matching
    what that date of year actually looks like.
  - CITY_CLIMATE (per-city only) is still refreshed too, using each city's
    first occurrence date — it now serves purely as the fallback for any
    (city, day) pair not covered by CITY_CLIMATE_BY_DAY (e.g. right after a
    new day is added to the workbook and before the next run of this
    script).
  - "packing" tips are editorial, not fetched data, and are left untouched.

Only run this against the real generate_data.py after confirming the
rewritten blocks still parse and the printed per-day values look sane —
see the safety check near the end of main().
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
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
GENERATE_SCRIPT = ROOT / "scripts" / "generate_data.py"

TRIP_YEAR = 2027
LOCAL_UTC_OFFSET_HOURS = 2  # CEST, shared by every city in this itinerary in April/May
HISTORY_YEARS = [2022, 2023, 2024]
WINDOW_DAYS = 7  # +/- around each exact date, per history year

# lat/lon per city already in CITY_CLIMATE, plus a representative point for
# "En el mar" (roughly mid-Adriatic/Tyrrhenian, where the itinerary's cruise
# days actually sail) so it gets real per-day values too, not just a guess.
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
    "En el mar": (40.5, 15.5),
    # Day-trip destination, not a base city — see DAY_TRIP_DESTINATIONS in
    # generate_data.py. Summit coordinates, not the valley town.
    "Jungfraujoch": (46.5475, 7.9847),
}

# WMO weather codes (Open-Meteo's `weathercode`) collapsed into the small set
# of icon+label pairs already used in CITY_CLIMATE.
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
    """"30 Abr" -> date(2027, 4, 30)."""
    day_str, month_str = day_key.split()
    return date(TRIP_YEAR, MONTH_NUMBER[month_str.upper()], int(day_str))


def load_generate_data():
    spec = importlib.util.spec_from_file_location("generate_data", GENERATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_city_day_pairs(gd) -> list[tuple[str, str]]:
    """Every (climateCity, dayKey) pair actually used across all 5 option
    sheets, in first-seen order, deduplicated. climateCity, not city: a
    day-trip day (see DAY_TRIP_DESTINATIONS in generate_data.py, e.g. the
    Jungfraujoch excursion out of Zürich) needs weather fetched for the
    excursion destination, not the base city the day is otherwise filed
    under — build_itinerary() already resolves which one applies per day."""
    sheets = [
        (4, "Completo"), (6, "Zúrich y Crucero"), (8, "Múnich y Crucero"),
        (10, "Solo crucero"), (12, "Solo crucero 2P"),
    ]
    rows = [line for sheet, name in sheets for line in gd.read_rows(sheet, name)]
    seen: dict[tuple[str, str], None] = {}
    for _, sheet_option in sheets:
        option_rows = [r for r in rows if r["option"] == sheet_option]
        for day in gd.build_itinerary(option_rows):
            seen[(day["climateCity"], day["dayKey"])] = None
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
    # e.g. "2027-05-15T03:47:32+00:00" -> local hour = 3 + offset, minute = 47
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


def _find_dict_block(source: str, var_name: str) -> tuple[int, int, int]:
    """Returns (assignment_start, brace_start, brace_end) for `var_name = {...}`
    or `var_name: <type annotation> = {...}`."""
    match = re.search(rf"^{re.escape(var_name)}\b[^=\n]*=\s*\{{", source, re.M)
    if match is None:
        raise SystemExit(f"update_climate.py: could not find {var_name!r} assignment in generate_data.py")
    start = match.start()
    brace_start = match.end() - 1
    depth = 0
    end = brace_start
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return start, brace_start, end


def _rewrite_dict_block(source: str, var_name: str, new_dict: dict, type_annotation: str = "") -> str:
    """Replace the `var_name = {...}` dict literal in generate_data.py's
    source text with a freshly serialized version of new_dict, one entry
    per line, in new_dict's iteration order."""
    start, brace_start, end = _find_dict_block(source, var_name)
    lines = ["{"]
    for key, fields in new_dict.items():
        parts = ", ".join(f'"{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items())
        lines.append(f'    "{key}": {{{parts}}},')
    lines.append("}")
    new_block = "\n".join(lines)
    assignment = f"{var_name}{type_annotation} = "
    return source[:start] + assignment + new_block + source[end:]


MAX_WORKERS = 8  # concurrent (city, day) fetches — polite to the free APIs, still a big speedup over serial


def _fetch_one(city: str, day_key: str) -> tuple[str, str, dict[str, str]]:
    lat, lon = CITY_COORDS[city]
    on_date = day_key_to_date(day_key)
    sunrise, sunset = fetch_sun_times(lat, lon, on_date)
    temp, icon, weather = fetch_climate_normal(lat, lon, on_date)
    return city, day_key, {"sunrise": sunrise, "sunset": sunset, "temp": temp, "weatherIcon": icon, "weather": weather}


def main() -> None:
    gd = load_generate_data()
    pairs = collect_city_day_pairs(gd)
    print(f"Found {len(pairs)} (city, day) pairs across all options.")

    fetchable = [(city, day_key) for city, day_key in pairs if city in CITY_COORDS]
    for city, day_key in pairs:
        if city not in CITY_COORDS:
            print(f"  skipping {city!r} ({day_key}) — no coordinates on file")

    by_day: dict[str, dict[str, str]] = {}
    by_city_first_date: dict[str, str] = {}
    # Fetches run in parallel across (city, day) pairs — each pair's own two
    # calls (sunrise/sunset, then climate normal) still run sequentially
    # inside _fetch_one, since the climate normal needs the same lat/lon and
    # there's no benefit splitting a single pair's calls across threads.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, city, day_key): (city, day_key) for city, day_key in fetchable}
        for future in as_completed(futures):
            city, day_key = futures[future]
            result_city, result_day_key, fields = future.result()
            by_day[f"{result_city}|{result_day_key}"] = fields
            print(f"  {result_city} ({result_day_key}): {fields['sunrise']}-{fields['sunset']}  {fields['temp']}  {fields['weatherIcon']} {fields['weather']}")

    # Deterministic "first occurrence" per city, independent of thread completion order.
    for city, day_key in pairs:
        if f"{city}|{day_key}" in by_day:
            by_city_first_date.setdefault(city, day_key)

    source = GENERATE_SCRIPT.read_text(encoding="utf-8")

    # Refresh the per-city fallback dict too (CITY_CLIMATE), keeping its
    # "packing" tips untouched, using each city's first-occurrence reading
    # from the loop above so the fallback is at least internally consistent.
    _, city_brace_start, city_end = _find_dict_block(source, "CITY_CLIMATE")
    current_city_climate = ast.literal_eval(source[city_brace_start:city_end])
    for city in current_city_climate:
        day_key = by_city_first_date.get(city)
        if day_key is None:
            continue
        current_city_climate[city].update(by_day[f"{city}|{day_key}"])

    new_source = _rewrite_dict_block(source, "CITY_CLIMATE", current_city_climate)
    new_source = _rewrite_dict_block(new_source, "CITY_CLIMATE_BY_DAY", by_day, type_annotation=": dict[str, dict[str, str]]")

    # Safety check: the rewritten file must still be syntactically valid
    # Python before we trust it enough to write.
    compile(new_source, str(GENERATE_SCRIPT), "exec")

    GENERATE_SCRIPT.write_text(new_source, encoding="utf-8")
    print(f"Updated CITY_CLIMATE and CITY_CLIMATE_BY_DAY in {GENERATE_SCRIPT}")

    subprocess.run([sys.executable, str(GENERATE_SCRIPT)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
