---
name: update-rates
description: Refresh the workbook's exchange rates (EUR/CHF/CZK/USD to COP) from a live source, re-price every line item across every trip option against the new rates, and regenerate the app. Use whenever the user asks to update, refresh, or check the exchange rates, or mentions the rates being stale/outdated.
---

# Updating exchange rates

Run the backing script:

```
python3 scripts/update_rates.py
```

That's it for the normal case — it fetches live rates, applies the
workbook's own markup, re-prices every affected row, and regenerates
`src/data/generated/itinerary.generated.ts` automatically. Then just
typecheck/build (`npx tsc -p tsconfig.app.json && npm run build`) and
report the new per-option totals to the user — no manual cell editing.

## What it does, and why it's safe to just run

- Fetches live USD-based rates from `open.er-api.com` (free, no API key)
  and derives EUR/CHF/CZK → COP from them.
- The workbook's `'Tasas de Cambio'` sheet already stores each rate as a
  formula like `=3572*$E$7`, where `E7` is a markup factor already sitting
  at **1.05** in this workbook — that's the user's standing "always add 5%
  more" policy for this trip, not something the script invents. The script
  only replaces the *base* number in that formula (e.g. `3572` → the fresh
  live rate) and reads whatever markup factor is already in `E7` — if that
  factor is ever changed by hand, the script respects it rather than
  hardcoding 5% itself.
- Updates "Fecha de actualización de tasas" to today.
- Re-prices every line item in every option sheet (Completo, Solo crucero
  i.e. "Crucero para 3", Solo crucero 2P i.e. "Crucero en pareja", Zúrich y
  Crucero, Múnich y Crucero — the sheet labels stay "Solo crucero"/"Solo
  crucero 2P" internally, only the app-facing display name changed): any
  row priced in EUR/CHF/CZK/USD gets its cached rate/total/per-person
  values recomputed against the new rate. Titles, notes, links, unit
  prices, and quantities are untouched — only the numbers that actually
  depend on the exchange rate change. COP-priced rows are already
  rate-independent and are skipped entirely.
- The 2-person "Crucero en pareja" sheet divides by 2 instead of the
  shared 3-person cell (see `scripts/duplicate_option.py`) — the script
  already knows this and uses the right divisor per sheet.

## Where this shows up in the app

- `ExchangeRatesCard` (shown on the selection screen and in the planner
  header): the "Tasas estimadas · {date}" header shows `ratesUpdatedAt`
  right next to the rates themselves — deliberately kept there rather than
  duplicated in `AppFooter`, per the user's explicit preference. Each
  currency (EUR/CHF/CZK/USD) below it is a clickable link — labelled with a
  dashed underline — that opens an XE.com currency-converter page for that
  exact pair in a new tab, so the user can independently verify the rate.
  The source URL comes from `CURRENCY_SOURCE_URL` in
  `scripts/generate_data.py`; change it there if the reference source is
  ever swapped.

## If you need to change the markup

Editing `E7` in the `'Tasas de Cambio'` sheet by hand (via
`scripts/manage_item.py`-style cell surgery, or ask the user to edit it in
Excel and re-supply the workbook) changes the markup for *all four*
currencies at once, since every rate formula multiplies by that same cell.
Re-run `python3 scripts/update_rates.py` afterward so the cached values and
the app data reflect the new markup.

## Verifying before trusting a run

`scripts/update_rates.py` edits the raw `.xlsx` XML directly (same style as
`generate_data.py` / `manage_item.py` / `duplicate_option.py` — targeted
row/cell regex substitution, not a full-document parse). If you're ever
modifying this script itself, test on a scratch copy first (`cp` the
workbook to `/tmp`, point `update_rates.WORKBOOK` at the copy) and verify
zip/XML integrity plus a few spot-checked rows before running it against
the real file — see the script's own module docstring and
`duplicate_option.py`'s docstring for the reasoning and the specific regex
pitfall (greedy quantifiers inside an optional `<f>` group) that bit this
project twice before the current helpers were hardened against it.
