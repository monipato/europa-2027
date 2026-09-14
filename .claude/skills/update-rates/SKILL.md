---
name: update-rates
description: Refresh the live exchange rates (EUR/CHF/CZK/USD/JPY to COP) in data/rates.json, and regenerate the app. Use whenever the user asks to update, refresh, or check the exchange rates, or mentions the rates being stale/outdated.
---

# Updating exchange rates

Run the backing script:

```
python3 scripts/update_rates.py
```

That's it — it fetches live rates, writes them into `data/rates.json`, and
regenerates `src/data/generated/itinerary.generated.ts` automatically. Then
just typecheck/build (`npx tsc -p tsconfig.app.json && npm run build`) and
report the new per-option totals to the user — no manual editing needed.

## What it does, and why it's safe to just run

- Fetches live USD-based rates from `open.er-api.com` (free, no API key)
  and derives EUR/CHF/CZK/JPY → COP from them.
- Writes each currency's new `baseRate` into `data/rates.json`. The rate
  actually used anywhere in the app — every price conversion, and the
  number shown in the footer — is `baseRate * markup`, computed fresh by
  `scripts/generate_data.py`'s `rate_for()` every time it runs. There's no
  cached total to re-price and no formula to touch: changing `baseRate`
  here is the entire update.
- `markup` (1.05, the family's standing "always add 5% more" policy) is
  read from the same file and left untouched by this script — if that
  policy ever changes, edit `data/rates.json`'s `"markup"` value by hand.
- Updates `data/rates.json`'s `updatedAt` to today's date.

## Where this shows up in the app

`ExchangeRatesCard` (shown on the selection screen and in the planner
header): the "Tasas estimadas · {date}" header shows `ratesUpdatedAt` right
next to the rates themselves. Each currency (EUR/CHF/CZK/USD/JPY) below it
is a clickable link — labelled with a dashed underline — that opens an
XE.com currency-converter page for that exact pair in a new tab. The source
URL for each currency lives in `data/rates.json`'s own `sourceUrl` field;
edit it there if the reference source is ever swapped.

## If you need to change the markup

Edit `data/rates.json`'s `"markup"` value directly, then re-run
`python3 scripts/generate_data.py` (no need to re-run `update_rates.py` —
the base rates aren't changing, only what they're multiplied by).
