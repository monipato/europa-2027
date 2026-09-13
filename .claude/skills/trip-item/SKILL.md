---
name: trip-item
description: Add or update a single expense/itinerary line item (flight, hotel, tour, SIM card, etc.) in one of the day-by-day trip options and have it show up correctly in the app. Use whenever the user asks to add a new line item to a trip option, or change the price/note/link/date of an existing one.
---

# Adding or updating a trip item

This app has one data source: plain JSON files under `data/`. Never
hand-edit `src/data/generated/itinerary.generated.ts` — always go through
`scripts/manage_item.py` (which edits the JSON and regenerates that file
automatically), or edit the JSON directly and run
`python3 scripts/generate_data.py` yourself afterward. Either path ends at
the same file, so pick whichever is easier for the change at hand — the
script is mainly there to protect against an ambiguous match on a title
that appears more than once (e.g. "Comida del día" repeated across days).

**Scope**: this only covers the 3 day-by-day options — `europa`,
`alpes-suizos`, `crucero-en-pareja`. Orlando (`orlando-jero`,
`orlando-pachito-vale`) and Japón (`japon`) are shaped differently (bucketed
by traveler type, or with fare `tiers`) — edit those JSON files directly;
see CLAUDE.md's "Data" section for their shapes.

## 1. Gather the required fields from the user

Ask for whatever isn't already clear from context:

- **option**: the file id — `europa`, `alpes-suizos`, or `crucero-en-pareja`
  (NOT the display name shown in the app — check `data/options/<id>.json`'s
  own `"name"` field if unsure which id matches which trip)
- **category**: one of `Vuelos y Trenes`, `Traslados`, `Alojamiento`,
  `Crucero`, `Tours y Excursiones`, `Comidas`, `Seguro de Viaje`, `Otros y Extras`
- **place**: short city/place label (can be blank for trip-wide items)
- **date**: either a real date string like `"14 May 2027"` (must contain a
  Spanish month abbreviation — Ene/Feb/Mar/Abr/May/Jun/Jul/Ago/Sep/Oct/Nov/Dic
  — so it lands on the right day), or a dateless label like `"Durante el
  viaje"` for trip-wide items (SIM cards, insurance, contingency) — those
  land on the option's first day, same as every existing one
- **title**: the line item's name, shown as the expense title in the app
- **currency**: one of `EUR`, `CHF`, `CZK`, `USD`, `COP`
- **unit-amount** and **quantity**: see the "per-person vs. shared" note below
- **note**: **max 20 words** — the single most relevant fact about this
  item (what's included, timing, anything the traveler needs to know at a
  glance). Don't restate the title.
- **link** (optional): a booking/info URL. If given, the app renders a "Ver
  tour o sitio web" button that opens in a new tab (or a download button,
  for a `.pdf` link — see `src/utils/expenseLink.ts`), in *both* the "Por
  día" and "Por rubro" views, since they read the exact same `note`/`link`
  fields. If omitted, no link button appears. Never invent a link — if the
  user hasn't given you one, leave it out rather than guessing a URL.

**Per-person vs. shared amount** — look at how similar existing items in
that day/category are modeled (read `data/options/<id>.json`, or ask)
before picking:
- Per-person items (most flights, transfers, meals): `quantity` = number of
  travelers, `unit-amount` = the per-person price.
- Shared/bundled items (a hotel stay, travel insurance, a private tour
  quoted as one lump sum for the group): `quantity` = 1, `unit-amount` =
  the total price for the group — the generator automatically divides it by
  the option's `peopleCount` to get the per-person figure shown in the app.

## 2. Run the script

```
python3 scripts/manage_item.py add \
  --option alpes-suizos \
  --category "Tours y Excursiones" \
  --place "Zadar" \
  --date "14 May 2027" \
  --title "Tour a pie por el casco antiguo" \
  --currency EUR --unit-amount 15 --quantity 3 \
  --note "Tour guiado 2h, incluye entrada a la catedral" \
  --link "https://example.com/tour"
```

To change an existing item instead, use `update` with `--match-title` (a
substring of the current title is enough) and only the fields that actually
changed — anything you omit keeps its current value:

```
python3 scripts/manage_item.py update \
  --option alpes-suizos --match-title "SIM card" \
  --currency USD --unit-amount 45 --note "..." --link "..."
```

`--match-title` is safe against ambiguity: an exact title always wins, and
if a substring matches more than one item the script refuses to guess — it
exits listing every candidate (with the day it's on) instead of silently
picking the first one. If that happens, re-run with a more specific
`--match-title`, or add `--match-date` (an exact match against the item's
own `date` text, e.g. `"14 May 2027"`) for a title that's intentionally
repeated once per day (e.g. "Comida del día"):

```
python3 scripts/manage_item.py update \
  --option europa --match-title "Comida del día" --match-date "26 May 2027" \
  --note ""
```

`delete` (drop a line item) works the same way:

```
python3 scripts/manage_item.py delete --option alpes-suizos --match-title "Free tour"
```

The script:
- Places a new item (`add`) on the day whose `dayKey` matches `--date` — if
  no such day exists yet, it tells you to add the day itself directly in
  the JSON first (a day needs a city/title/weather, which isn't something
  a line-item edit can invent).
- Rejects a note over 20 words outright — shorten it and re-run.
- Regenerates `src/data/generated/itinerary.generated.ts` automatically at
  the end. Don't run `generate_data.py` again separately unless you're
  troubleshooting.

## 3. Adding a whole new day

That's a bigger edit than one line item — a day needs its own
`dayKey`/`city`/`title`/`dayKind`/`weather`, not just a price. Edit
`data/options/<id>.json` directly: copy the shape of a neighboring day,
fill in its real city/title, and give it a reasonable starting `weather`
(then run `python3 scripts/update_climate.py` to refresh it with a real
value, or just `python3 scripts/generate_data.py` if the estimate is fine
for now). Add the day's `items` the same way you'd add any item above.

## 4. Verify

After running the script (or a hand-edit + `generate_data.py`):
1. `npx tsc -p tsconfig.app.json && npm run build` — must be clean.
2. Spot-check the new/changed item in a browser (`npm run dev`), in both
   the "Por día" view (find the right day) and the "Por rubro" view (open
   the category's detail popup) — the note text and link button must be
   identical in both places, since they render from the same fields.
3. If a link was given, confirm the button opens in a new tab (or
   downloads, for a `.pdf`).

Never commit or push unless the user explicitly asks.
