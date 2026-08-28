---
name: update-packing
description: Explains how each day's "Qué llevar" (what to pack) tip is generated, combining that day's own plans (flight, cruise embarkation, tours, hotel check-in) with its weather. Use whenever the user asks to update, refresh, improve, or extend the packing tips/suggestions.
---

# How the "Qué llevar" tips work

Unlike `update-rates` or `update-climate`, **there is no separate script to
run.** Packing guidance doesn't go stale day to day the way an exchange
rate or a weather forecast does, so it's computed automatically, every
time, inside `build_itinerary()` in `scripts/generate_data.py` — via
`compute_packing()`. Running `python3 scripts/generate_data.py` (or any
script that calls it, like `manage_item.py`, `update_rates.py`, or
`update_climate.py`) always regenerates every day's tip fresh from whatever
that day's `dayKind`, weather, and line items currently are.

## What `compute_packing()` combines

Returns a checklist (`list[str]`, capped at 5 items) — `DayByDayView` renders
it as a vertical checklist in the "Qué llevar" popup, not a single sentence.
For each day, in order of priority:

1. **What that day's plans require** (documents/logistics), based on
   `dayKind` and that day's actual line items:
   - `dayKind == "flight"` → passport (6-month validity reminder) + a
     printed/offline boarding pass.
   - `dayKind == "embark"` (cruise day) → passport + cruise boarding
     documents, plus a day-bag reminder (checked luggage takes hours to
     reach the cabin).
   - The trip's last day (return flight, not otherwise a flight/embark day)
     → passport + return-flight documents.
   - A day with an `Alojamiento` (hotel) line → reservation confirmation.
   - A day with a real `Tours y Excursiones` line → cash for small expenses
     + camera.
   - The destination is `"En el mar"` → swimsuit, sunscreen,
     motion-sickness remedy.
2. **What that day's weather calls for**, from the same `weather`/`temp`
   values `update_climate.py` refreshes: a rain-ish label (`Lluvia`,
   `Llovizna`, `Chubascos`, `Tormenta`) adds an umbrella/rain jacket; a low
   under 10°C adds a warm coat, under 16°C a light jacket; a high of 22°C+
   adds sun-appropriate clothing, sunglasses, and sunscreen.
3. A reusable water bottle, as a baseline, only added if the day already
   triggered at least one of the rules above — an otherwise uneventful day
   (no flight/embark, mild weather) falls back to a single-item checklist
   with that destination's static `CITY_CLIMATE[...]["packing"]` tip
   instead of forcing a generic item onto every single day.

Note it's the *destination*, not necessarily the day's base `city` —
`compute_packing()` is called with `climateCity`, which differs from `city`
on a day-trip day (e.g. the Jungfraujoch excursion out of Zürich; see the
"Day trips" section of the `update-climate` skill). A cold mountain
excursion out of a mild base city correctly gets "chaqueta abrigada" from
rule 2 because it's judged against the excursion's own temperature, not the
base city's.

The rules themselves were researched once against common travel-prep
checklists (passport validity windows, printed-boarding-pass advice, cruise
embarkation-day packing) rather than fetched live — see Sources below. This
is deliberate: it's the same "aprox" framing as `CITY_CLIMATE` itself, just
for packing instead of weather.

Sources used when writing the rule set:
- [15 Items for Your International Travel Checklist](https://traveladdicts.net/international-travel-checklist/)
- [The Essential Packing List for an International Flight](https://www.betterroaming.com/blog/guides-and-how-to/essential-packing-list-international-flight/)
- [International Travel Checklist — U.S. State Department](https://travel.state.gov/en/international-travel/planning/checklist.html)
- [What to Pack for a Mediterranean Cruise — Life Well Cruised](https://lifewellcruised.com/what-to-pack-for-a-mediterranean-cruise/)
- [10 Must-Pack Items for a Mediterranean Cruise — Cruise Critic](https://www.cruisecritic.com/articles/what-to-pack-for-a-europe-cruise-to-the-mediterranean)

## Extending the rules

To add a new trigger (e.g. a new activity category, a destination-specific
document requirement), edit `compute_packing()` directly in
`scripts/generate_data.py` — add the condition and its `items.append(...)`
line, keeping each item short (it's one row in a checklist, not its own
paragraph). Re-run `python3 scripts/generate_data.py` afterward; no other
step is needed. If the new rule should only apply to certain destinations,
gate it on the function's `city` parameter (which is actually
`climateCity`, the day's resolved destination — see above) the same way the
`"En el mar"` rule does.

## Where this shows up in the app

`DayByDayView`'s "Qué llevar" button opens a popup rendering
`activeDay.packing` as a vertical checklist (`.packing-checklist`, a
`<ul>`/`<li>` with a check icon per item) — not a single sentence.
