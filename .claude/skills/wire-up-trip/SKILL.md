# Wiring a new `data/options/<id>.json` into the live app

Step 2 of adding a trip option — run this right after `new-trip` has
produced `data/options/<id>.json` (or after a JSON file has otherwise been
hand-written in that same day-by-day shape). This skill only covers that
shape — see `new-trip`'s own scope note if the file is Orlando- or
Japón-shaped instead.

Nothing here is optional or reorderable — each step depends on the one
before it.

## 1. Register the option id in the 3 places that list it

Every day-by-day option's filename id is hardcoded in three scripts. Add
the new id to all three, matching the existing entries' style exactly:

- `scripts/generate_data.py` — inside `main()`, the list literal
  `for file_id in ["europa", "alpes-suizos", "crucero-en-pareja"]:`. Add
  the new id to this list (order doesn't matter functionally, but put it
  wherever reads naturally, e.g. next to a similar trip).
- `scripts/manage_item.py` — the `OPTION_IDS = [...]` list near the top.
  This is what makes `--option <id>` valid for future hand-edits via
  `manage_item.py`.
- `scripts/validate_data.py` — the `DAY_OPTION_IDS = [...]` list.

Miss one of these and the symptom is different depending on which:
skipped in `generate_data.py` → the trip silently never appears in the
app at all; skipped in `manage_item.py` → future edits to this trip via
that script fail with an unrecognized `--option`; skipped in
`validate_data.py` → this trip's data quietly never gets checked.

## 2. Add any new cities to `data/cities.json`

For every city that appears in the new file's `days[].city` (and any
`climateCity` overrides) that *isn't* already a key in `cities.json`'s
`cities` object, add an entry:

```json
"Kioto": {
  "country": "Japón",
  "emoji": "🇯🇵",
  "images": ["https://images.unsplash.com/photo-...?auto=format&fit=crop&w=900&q=80", "..."],
  "climate": { "sunrise": "6:00 AM", "sunset": "5:30 PM", "temp": "12–20°C", "weatherIcon": "⛅", "weather": "Variable", "packing": "Ropa en capas, paraguas ligero" },
  "weatherSourceUrl": "https://www.weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,kyoto,Japan",
  "sunSourceUrl": "https://sunrise-sunset.org/search?location=Kyoto"
}
```

- **`images`** — 2–3 real, working photo URLs of that city (a small pool
  so a multi-day stay doesn't repeat one hero photo — see how existing
  cities do this). Search for genuine Unsplash (or similarly licensed)
  photo URLs of the actual place; never fabricate a URL, and don't reuse
  another city's photo.
- **`climate`** — the same placeholder-now, real-later approach as
  `new-trip`'s per-day weather: a reasonable seasonal guess, since step 4
  below overwrites it with real data anyway.
- **`weatherSourceUrl`/`sunSourceUrl`** — check the URL pattern actually
  resolves for this city (weather-and-climate.com's slug format, a
  sunrise-sunset.org search query) before trusting it, same as `CLAUDE.md`
  says for any new city.
- A city that's a day-trip destination only (a mountain, a small town) —
  not a place anyone actually stays overnight — still needs `country`/
  `emoji`/`climate`, but `images` can be a single representative photo
  rather than a pool, since no day repeats there back-to-back for the
  no-repeat pool logic to matter.

Skip this step entirely for any city that's already in `cities.json` —
don't overwrite an existing entry.

## 3. Regenerate and validate

```
python3 scripts/generate_data.py
npm run validate
```

`generate_data.py` must print one more option than before and finish with
no traceback. `npm run validate` (== `python3 scripts/validate_data.py`)
must report the new file with no errors — warnings about a note being a
few words over 20, or a link returning 403/405/429 (bot-blocked, not
actually dead), are fine to leave; an unknown category, a missing city, or
a note wildly over the limit are not — go fix those in the JSON file
directly (or via `manage_item.py update --option <id> ...`) and re-run
both commands.

## 4. Get real weather instead of the placeholder guess

```
python3 scripts/update_climate.py
```

This walks every option's built itinerary (including the new one now that
step 1 wired it in) and replaces every placeholder `weather` block —
both the per-day ones in `data/options/<id>.json` and the per-city
fallback in `data/cities.json` — with real sunrise/sunset astronomy and
climate-normal data for the exact dates involved. It regenerates
automatically at the end (re-running `generate_data.py` again after this
is redundant, not wrong).

If any city prints a "no coordinates on file" warning, add it to
`CITY_COORDS` in `scripts/update_climate.py` (see that skill's own
"If a new city is ever added" section) and re-run.

## 5. Final check

```
npx tsc -p tsconfig.app.json && npm run build
```

Must be clean — this is the same gate the real deploy goes through, and it
would only ever fail here if something upstream (an unescaped character
in a note, a malformed `routeOverride`) slipped past `npm run validate`.

Then a quick look in the browser (`npm run dev`): the new option's card
should appear on the selection screen with a sensible photo and price, and
its day-by-day view should show the placeholder-turned-real weather on
each day. Report back to the user what you added and anything you had to
guess (a city photo, a placeholder note) so they can double-check it.

Never commit or push unless the user explicitly asks.
