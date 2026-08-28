---
name: trip-item
description: Add or update a single expense/itinerary line item (flight, hotel, tour, SIM card, etc.) in the Europa 2027 quote workbook and have it show up correctly in the app. Use whenever the user asks to add a new line item to a trip option, or change the price/note/link/date of an existing one.
---

# Adding or updating a trip item

This app has exactly one data source: the Excel workbook at the repo root
(`Europa2027_Cotizacion_plan_completo (1).xlsx`). Never hand-edit
`src/data/generated/itinerary.generated.ts` and never hand-edit the `.xlsx`
by opening it in a spreadsheet app for this kind of change — always go
through `scripts/manage_item.py`, which edits the workbook's raw XML
directly (same zero-dependency approach as `scripts/generate_data.py`) and
then regenerates the app's data file automatically.

## 1. Gather the required fields from the user

Ask for whatever isn't already clear from context:

- **option**: one of `Completo`, `Zúrich y Crucero`, `Múnich y Crucero`, `Solo crucero`
- **category**: one of `Vuelos y Trenes`, `Traslados`, `Alojamiento`, `Crucero`, `Tours y Excursiones`, `Comidas`, `Seguro de Viaje`, `Otros y Extras`
- **place**: short city/place label (can be blank for trip-wide items)
- **date**: either a real date string like `"14 May 2027"` (must contain a
  Spanish month abbreviation — Ene/Feb/Mar/Abr/May/Jun/Jul/Ago/Sep/Oct/Nov/Dic
  — so it lands on the right day), or a dateless label like `"Durante el
  viaje"` for trip-wide items (SIM cards, insurance, contingency)
- **title**: the line item's name, shown as the expense title in the app
- **currency**: one of `EUR`, `CHF`, `CZK`, `USD`, `COP`
- **unit-amount** and **quantity**: see the "per-person vs. shared" note below
- **note**: **max 20 words** — the single most relevant fact about this
  item (what's included, timing, anything the traveler needs to know at a
  glance). Don't restate the title. Never write "Confirmado" or a
  confirmation date in here — see step 3.
- **link** (optional): a booking/info URL. If given, it's automatically
  appended to the note and rendered in the app as a "Ver tour o sitio web"
  button that opens in a new tab — in *both* the "Por día" and "Por rubro"
  views, since they read the exact same note/link fields. If omitted, no
  link button appears anywhere. Never invent a link — if the user hasn't
  given you one, leave it out rather than guessing a URL.

**Per-person vs. shared amount** — look at how similar existing rows in that
category are modeled (read the sheet or ask) before picking:
- Per-person items (most flights, transfers, meals): `quantity` = number of
  travelers (3), `unit-amount` = the per-person price.
- Shared/bundled items (SIM card, travel insurance, a private tour quoted
  as one lump sum for the group): `quantity` = 1, `unit-amount` = the total
  price for the group — the sheet automatically divides it by the traveler
  count to get the per-person figure shown in the app.

## 2. Run the script

```
python3 scripts/manage_item.py add \
  --option "Solo crucero" \
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
  --option "Solo crucero" --match-title "SIM card" \
  --currency USD --unit-amount 45 --note "..." --link "..."
```

`--match-title` is safe against ambiguity: an exact title always wins, and
if a substring matches more than one row the script refuses to guess — it
exits listing every candidate row and title instead of silently picking the
first one. If that happens, re-run with a more specific `--match-title`
(more of the title text) rather than trying to work around it. The same
applies to `delete`.

`delete` (drop a line item, e.g. removing a duplicated tour) works the
same way:

```
python3 scripts/manage_item.py delete --option "Solo crucero" --match-title "Free tour"
```

The script:
- Reads the current exchange rate for the given currency live from the
  workbook's "Tasas de Cambio" sheet (never hardcode a rate).
- Writes real Excel formulas for the computed columns (not just cached
  numbers) so the row keeps recalculating correctly if a human ever edits
  it directly in Excel later.
- For `add`, reuses one of the sheet's existing blank template rows (every
  sheet has hundreds already pre-styled past its last real item) — no risky
  row-insertion or formula-range shifting involved.
- Rejects a note over 20 words outright — shorten it and re-run.
- Regenerates `src/data/generated/itinerary.generated.ts` automatically at
  the end. Don't run `generate_data.py` again separately unless you're
  troubleshooting.

## 3. What "confirmed" means here

The script stamps today's date into column M ("Fecha confirmación precio")
automatically — that's Excel-only bookkeeping the generator never reads, so
it never leaks into the app. Don't add "Confirmado" or a date into `--note`;
that's exactly the clutter this column exists to keep out of the UI.

## 4. Verify

After running the script:
1. `npx tsc -p tsconfig.app.json && npm run build` — must be clean.
2. Spot-check the new/changed item in a browser (`npm run dev`), in both
   the "Por día" view (find the right day) and the "Por rubro" view (open
   the category's detail popup) — the note text and link button must be
   identical in both places, since they render from the same fields.
3. If a link was given, confirm the "Ver tour o sitio web" button opens in
   a new tab.

Never commit or push unless the user explicitly asks.
