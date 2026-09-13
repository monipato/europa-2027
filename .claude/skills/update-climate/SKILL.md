---
name: update-climate
description: Refresh each day's sunrise, sunset, and weather (temperature range + condition) shown in the day-by-day planner, per exact city and calendar date. Use whenever the user asks to update, refresh, or check the weather/climate/sunrise/sunset data, or mentions it being stale/outdated.
---

# Updating weather, sunrise, and sunset

Run the backing script:

```
python3 scripts/update_climate.py
```

That's it for the normal case — it walks every day of `data/options/
{europa,alpes-suizos,crucero-en-pareja}.json`, fetches real astronomy and
climate-normal data per (city, exact date) in parallel (up to 8 pairs at
once — see `MAX_WORKERS`), writes the result straight into each day's own
`weather` object, and regenerates `src/data/generated/itinerary.generated.ts`
automatically. Takes well under two minutes even across the ~40 (city, day)
pairs across those three options. Then just typecheck/build (`npx tsc -p
tsconfig.app.json && npm run build`) and report anything that looks off
(e.g. a city with no coordinates on file) to the user.

## What it does, and why it's safe to just run

- Every day already states its own weather directly (`data/options/
  <id>.json`'s `days[].weather` — `sunrise`/`sunset`/`temp`/`weatherIcon`/
  `weather`), so this script's whole job is: for each day, figure out which
  real place its weather should reflect, fetch that place's numbers for
  that exact date, and overwrite the `weather` object in place.
- Which place: normally the day's own `city`, but a day trip whose weather
  belongs somewhere else (e.g. an Alpine excursion out of a city-base day)
  carries an explicit `climateCity` field instead — see
  `alpes-suizos.json`'s "02 MAY" for a real example. This script reads that
  field when present; nothing is inferred from a keyword or place string.
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
  for that time of year is what's shown.
- `data/cities.json`'s per-city `climate` field is also refreshed (from
  each city's first-occurrence date) — it's a fallback for a brand-new day
  that hasn't had its own exact-date fetch run yet, and it's what Orlando
  and Japón actually use for their (single, static, not-per-day) weather —
  this script does **not** touch those two options' own JSON files.
- "packing" tips are editorial text, not fetched data, and are left
  untouched by this script.

## Where this shows up in the app

- `DayByDayView`'s `.day-conditions` row shows sunrise, sunset, and the
  weather chip for the day currently selected — specific to that exact
  date, not just the city.
- All three chips are clickable links — labelled with a dashed underline:
  sunrise and sunset both link to a sunrise-sunset.org page for that city
  (`sunSourceUrl` in `data/cities.json`), and the weather chip links to a
  weather-and-climate.com monthly-normals page (`weatherSourceUrl`).
  "En el mar" has no fixed location, so it gets no links on any of the
  three chips. All three links are repeated on their matching stat inside
  the "Qué llevar" packing popup.
- That popup also shows a weather-themed duck sticker
  (`getWeatherDuck` in `src/utils/weatherDuck.ts`), chosen purely from the
  day's `weather` label. This script is the reason it updates: `weather` is
  exactly the field refreshed above, so re-running this script changes both
  the number and the duck together — no extra wiring.

## If a new city is ever added

Add its lat/lon to `CITY_COORDS` in `scripts/update_climate.py` (and, if
you want "Ver clima"/"Ver amanecer"/"Ver atardecer" links for it too, add
`weatherSourceUrl`/`sunSourceUrl` to its entry in `data/cities.json` —
check the URL pattern actually resolves with a plain city/city,Country
slug before trusting it). A city missing from `CITY_COORDS` is skipped with
a printed warning rather than crashing, and its days keep whatever weather
they already had.

## Day trips

A day's weather doesn't always belong to the city it's otherwise filed
under — see the "What it does" section above. To add a new one: give that
day in its `data/options/<id>.json` file a `climateCity` field naming the
real destination, add that destination's coordinates to `CITY_COORDS` here,
and (optionally) a fallback entry in `data/cities.json` if you want a
sensible starting value before the first live fetch. The day's own
`city`/`title`/hero image are untouched either way — only the `weather`
block and the "Clima de {climateCity}" note the UI shows when the two
differ.
