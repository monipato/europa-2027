---
name: update-climate
description: Refresh each day's sunrise, sunset, and weather (temperature range + condition) shown in the day-by-day planner, per exact city and calendar date. Use whenever the user asks to update, refresh, or check the weather/climate/sunrise/sunset data, or mentions it being stale/outdated.
---

# Updating weather, sunrise, and sunset

Run the backing script:

```
python3 scripts/update_climate.py
```

That's it for the normal case — it walks every option's built itinerary,
fetches real astronomy and climate-normal data per (city, exact date) in
parallel (up to 8 pairs at once — see `MAX_WORKERS`), and regenerates
`src/data/generated/itinerary.generated.ts` automatically. Takes well under
two minutes even across the ~40 (city, day) pairs in this itinerary — a
fully serial version of this took 15+ minutes and was replaced for that
reason. Then just typecheck/build (`npx tsc -p tsconfig.app.json && npm run
build`) and report anything that looks off (e.g. a city with no coordinates
on file) to the user.

## What it does, and why it's safe to just run

- Unlike exchange rates, this data doesn't live in the Excel workbook — it's
  two plain Python dicts in `scripts/generate_data.py`:
  - `CITY_CLIMATE_BY_DAY` — keyed by `"{city}|{dayKey}"` (e.g.
    `"Zúrich|30 Abr"`), the values actually shown in the app. Populated
    fresh every run, one entry per (city, day) pair that's actually used
    across all 5 option sheets — so the same city visited on two different
    dates gets two different readings.
  - `CITY_CLIMATE` — the older per-city-only dict, kept as a fallback for
    any (city, day) not covered by `CITY_CLIMATE_BY_DAY` (e.g. right after
    a new day is added to the workbook, before this script has run again).
    Also refreshed each run, from each city's first-occurrence date.
- Sunrise/sunset are exact astronomy (not a forecast) for the day's real
  calendar date in 2027 — fetched from the free, keyless
  `api.sunrise-sunset.org` and converted from UTC to local time via a fixed
  UTC+2 (CEST) offset, which every city in this itinerary shares in
  April/May.
- Temperature range and the dominant weather condition are real seasonal
  normals — Open-Meteo's free `archive-api.open-meteo.com`, averaged over a
  +/-7 day window around that exact calendar date across the last 3 years
  (2022-2024) per city. This is the honest ceiling on "live" weather data a
  year ahead: no real forecast exists that far out, so a historical normal
  for that time of year is what's shown, same as before — just computed per
  exact date now instead of one static value per city.
- "packing" tips are editorial text, not fetched data, and are left
  untouched by this script.
- `CLIMATE_SOURCE_URL` and `SUN_SOURCE_URL` (also in `generate_data.py`, per
  city) are static reference links, not something this script refreshes —
  they don't change.
- Fetches for different (city, day) pairs run concurrently (a
  `ThreadPoolExecutor`, `MAX_WORKERS = 8`); within one pair, the sunrise
  call and the 3-year climate-normal calls still run sequentially since
  they share the same lat/lon and there's no benefit splitting them further.

## Where this shows up in the app

- `DayByDayView`'s `.day-conditions` row shows sunrise, sunset, and the
  weather chip for the day currently selected — specific to that exact
  date, not just the city.
- All three chips are clickable links — labelled with a dashed underline,
  same treatment as the currency links in `ExchangeRatesCard`:
  - Sunrise and sunset both link to a sunrise-sunset.org page for that city
    (`SUN_SOURCE_URL`) — one page shows the full day's sun schedule, so
    both chips share the same URL per city.
  - The weather chip (icon + temp) links to a weather-and-climate.com
    monthly-normals page for that city (`CLIMATE_SOURCE_URL`).
  - "En el mar" has no fixed location, so it gets no links on any of the
    three chips.
  - All three links are repeated on their matching stat inside the "Qué
    llevar" packing popup.
- That popup also shows a weather-themed duck sticker (`getWeatherDuck` in
  `src/utils/weatherDuck.ts`), chosen purely from the day's `weather` label.
  This script is the reason it updates: `weather` is exactly the field
  refreshed above, so re-running this script and regenerating changes both
  the number and the duck together — no extra step, no extra wiring.

## If a new city is ever added

Add its lat/lon to `CITY_COORDS` in `scripts/update_climate.py` (and, if you
want "Ver clima"/"Ver amanecer"/"Ver atardecer" links for it too, matching
entries in `CLIMATE_SOURCE_URL` and `SUN_SOURCE_URL` in `generate_data.py`
— check both URL patterns actually resolve with a plain city/city,Country
slug before trusting them, same as the existing entries). Cities missing
from `CITY_COORDS` are skipped with a printed warning rather than crashing,
and fall back to `DEFAULT_CLIMATE`.

## Day trips to somewhere other than the base city

A day's weather doesn't always belong to the city it's otherwise filed
under. E.g. 02 May is a Zürich-based day (hotel stays there), but one Tours
line is a day trip up to the Jungfraujoch — a 3,454m glacier summit that's
well below freezing even when Zürich itself is mild. `climateCity` on each
`GeneratedDay` is a separate field from `city` for exactly this: it's
resolved by `day_trip_destination()` in `generate_data.py`, which matches a
keyword (see `DAY_TRIP_DESTINATIONS`) against that day's Tours line titles.
When it matches, weather/sunrise/sunset/packing all key off `climateCity`
instead of `city` — the day's own city/title/hero image are untouched, and
the app shows a small "🚠 Clima de {climateCity} — la excursión del día"
note (`DayByDayView`) so it's clear why the numbers look different from the
base city. `collect_city_day_pairs()` here also reads `climateCity`, not
`city`, so the excursion destination gets its own live-fetched entry in
`CITY_CLIMATE_BY_DAY` too — the Jungfraujoch entry isn't the same as
Zürich's despite being the same calendar day. To add another such day trip,
add a keyword→destination entry to `DAY_TRIP_DESTINATIONS`, then give that
destination the same three things any climate-tracked place needs:
`CITY_COORDS` here, and a `CITY_CLIMATE` fallback entry plus
`CLIMATE_SOURCE_URL`/`SUN_SOURCE_URL` links in `generate_data.py` (a
mountain/attraction may need a nearby town substituted for the
weather-and-climate.com link, the way Jungfraujoch uses Interlaken — see
the comment there).

## Verifying before trusting a run

`scripts/update_climate.py` edits `generate_data.py`'s Python source
directly (parses the `CITY_CLIMATE` / `CITY_CLIMATE_BY_DAY` dict literals
with `ast.literal_eval`, re-serializes them, and `compile()`s the result
before writing — so a malformed rewrite fails loudly instead of corrupting
the file). If you're ever modifying this script itself, test it against a
scratch copy of `generate_data.py` first (point `update_climate.GENERATE_SCRIPT`
at a `/tmp` copy and patch the loaded module's `WORKBOOK` back to the real
workbook path, since the copy's own `ROOT`-relative path won't resolve) and
read through the printed per-(city, day) values before running it for real.
