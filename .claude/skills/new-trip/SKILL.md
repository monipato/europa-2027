# Turning a trip idea into `data/options/<id>.json`

This is step 1 of adding a brand-new trip option to the app — it produces
one JSON file. It does **not** make the trip show up anywhere; that's step
2, the separate `wire-up-trip` skill, run right after this one.

This skill only covers **day-by-day options** — a trip with one line item
per dated flight/hotel/tour/meal, like `europa`, `alpes-suizos`, or
`crucero-en-pareja`. It does not cover Orlando's bucketed-by-category shape
(that one is hand-edited directly, per `CLAUDE.md`) or Japón's tiered-ticket
shape — if the new trip needs either of those, say so and adapt by hand
rather than forcing this shape.

## 1. Interview the user

Ask for whatever isn't already clear from what they've given you:

- **A short internal id** for the filename — lowercase, hyphenated, e.g.
  `japon-otono`, `andes-2028`. This is forever the `--option` value for
  `manage_item.py` and never shown to the traveler.
- **Display name** (`name`) — what the trip is called in the app, e.g.
  "Otoño en Japón". Can be reworded later with zero ripple effects, since
  the filename id is separate from it.
- **Dates** as shown in the UI (`dates`), e.g. `"12 – 24 oct 2028"`.
- **A card accent color** (`color`) — a hex string. Pick one that doesn't
  clash with the existing options' colors (check the other files in
  `data/options/`) unless the user names one.
- **One-line description** — shown under the option name on the selection
  card.
- **`peopleCount`** — how many travelers this option is priced for.
- **Every day of the trip**: the date, the city, a short title (what
  DayByDayView's hero banner says — "Llegada a Barcelona", "Día libre en
  Roma", "Embarque en el crucero"), and every priced item that day (flight,
  transfer, hotel, tour, meal, insurance, everything).
- **Per item**: category, place, currency, amount (see "per-person vs.
  shared" below), a note (≤ 20 words — the single most useful fact: what's
  included, timing, confirmation status), and a link if they have one.
  Never invent a link.

Don't block on having every last detail — a `$0`/"Pendiente cotizar"
placeholder item with a real title is normal and matches how every
existing option handles an unquoted leg (see any "Pendiente cotizar" row
in `data/options/europa.json` for the pattern).

## 2. The file shape

Top level:

```json
{
  "name": "Otoño en Japón",
  "dates": "12 – 24 oct 2028",
  "color": "#7a9b6f",
  "description": "Kioto en temporada de momiji, luego Tokio",
  "peopleCount": 2,
  "routeOverride": null,
  "days": [ /* see below */ ]
}
```

`routeOverride` is `null` unless the auto-derived "every city in day order"
route badge tells the wrong story (see `alpes-suizos.json` for a real
example, which names the excursion landmark instead of the port town) —
leave it `null` unless asked to override it.

Each entry in `days`:

```json
{
  "dayKey": "12 OCT",
  "city": "Kioto",
  "title": "Llegada a Kioto",
  "dayKind": null,
  "weather": { "sunrise": "6:00 AM", "sunset": "5:30 PM", "temp": "12–20°C", "weatherIcon": "⛅", "weather": "Variable" },
  "climateCity": null,
  "items": [ /* see below */ ]
}
```

- `dayKey` — short display key, `"DD MMM"` in Spanish month abbreviation
  (EN/FEB/MAR/ABR/MAY/JUN/JUL/AGO/SEP/OCT/NOV/DIC), uppercase, matching
  the `date` fields of that day's items.
- `city` — the day's base city. Drives the hero photo pool, country flag,
  and default weather lookup.
- `title` — one line, shown big on the day's hero banner.
- `dayKind` — `"flight"` for the outbound-flight day, `"embark"` for a
  cruise-embarkation day, `null` otherwise. Only used for the ✈️/🛳️ badge
  override — don't set it just because a flight happens that day if it
  isn't *the* transit day.
- `weather` — put in a **reasonable placeholder** here (a seasonal guess
  is fine, e.g. "Variable" / "⛅" / a plausible temp range for that city
  and month) — the `wire-up-trip` skill's `update_climate.py` run replaces
  every one of these with real sunrise/sunset/climate-normal data
  immediately after this file is wired in. Never leave a field out; every
  key here is required.
- `climateCity` — omit entirely (or `null`) unless this day's weather
  belongs to a day-trip destination rather than the base city (see
  `CLAUDE.md`'s "Day trips" note) — this is rare, don't add it
  speculatively.

Each entry in a day's `items`:

```json
{
  "category": "Vuelos y Trenes",
  "place": "Bogotá / Kioto",
  "date": "12 Oct 2028",
  "title": "Vuelo internacional Bogotá → Osaka (ida y vuelta)",
  "currency": "COP",
  "unitAmount": 3200000,
  "quantity": 2,
  "note": "Aeroméxico, vía Ciudad de México. Incluye regreso",
  "link": null
}
```

- `category` — exactly one of: `Vuelos y Trenes`, `Traslados`,
  `Alojamiento`, `Crucero`, `Tours y Excursiones`, `Comidas`,
  `Seguro de Viaje`, `Otros y Extras`. Nothing else — `wire-up-trip`'s
  validation step rejects anything outside this list.
- `currency` — one of `EUR`, `CHF`, `CZK`, `USD`, `COP`, `JPY`.
- **Per-person vs. shared amount**: a per-person item (most flights,
  transfers, meals) sets `quantity` to the traveler count and `unitAmount`
  to the per-person price. A shared/bundled item (a hotel room, a private
  tour quoted as one lump sum) sets `quantity: 1` and `unitAmount` to the
  group total — the generator divides it by `peopleCount` automatically.
- `note` — **max 20 words**. Don't restate the title. Never write
  "Confirmado" or a confirmation date — that convention doesn't exist in
  this pipeline (there's no Excel column for it anymore).
- `link` — a real booking/info URL if the user gave one, otherwise `null`.
  Never invent one.
- `date` — display text, can be a range like `"12 – 14 Oct 2028 (2 noches)"`
  — independent of which day it's filed under, but should contain a
  Spanish month abbreviation somewhere so it reads consistently with the
  rest of the app.

## 3. Write the file, then hand off

Write the finished JSON to `data/options/<id>.json` (2-space indent, like
the existing files). Don't run `generate_data.py` yourself and don't touch
any other file — that's exactly what the `wire-up-trip` skill does next.
Tell the user the file is ready and that `wire-up-trip` is the next step.

## 4. Before handing off, sanity-check the file yourself

- Every day has at least one item (a placeholder is fine, an empty list
  isn't).
- `dayKey` values are in chronological order and match each item's `date`
  for that day.
- Every `category` is spelled exactly as in the list above (Spanish, with
  the "y"/accents) — a near-miss like "Vuelos" or "Tours" alone fails
  validation silently until `wire-up-trip`'s validate step catches it.
- Every note is short — skim for anything that reads like a paragraph.
- `python3 -m json.tool data/options/<id>.json > /dev/null` parses clean
  (catches a stray trailing comma or unescaped quote before it reaches the
  next skill).
