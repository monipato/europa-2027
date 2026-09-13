# Patitours — Europe/Orlando/Japan 2027 trip planner

A single-page site presenting a family trip-planning itinerary and cost
quote: a month in Europe (with a Mediterranean cruise), a Disney
World/Universal Orlando trip, and a Japan trip. All amounts are per-person
COP. The UI is in Spanish; code and comments are in English.

## Quickstart

```
npm install
npm run dev       # start the dev server
npm run build     # typecheck + production build
```

## How the data works

There's no database and no spreadsheet — every trip price, date, and note
lives in plain JSON files under `data/`, one file per trip option (plus two
shared files for exchange rates and city info). A small Python script turns
that JSON into the file the React app actually reads:

```
data/*.json  →  scripts/generate_data.py  →  src/data/generated/itinerary.generated.ts  →  the app
```

**To change a price, date, or note on an existing item:**

```
python3 scripts/manage_item.py update --option europa --match-title "Hotel Barcelona" \
  --unit-amount 550000 --note "..."
```

Or just open `data/options/europa.json` in any editor and change it by
hand — it's the same file either way. Either way, run
`python3 scripts/generate_data.py` afterward (the `manage_item.py` command
above does this for you automatically).

**To add or remove a line item**, use `scripts/manage_item.py add|delete` —
see `.claude/skills/trip-item/SKILL.md` for the full field reference.

**To refresh exchange rates or weather**, run
`python3 scripts/update_rates.py` / `python3 scripts/update_climate.py` —
both fetch live data and write straight into `data/`.

See `CLAUDE.md` for the full architecture (the exact JSON shape for each
file, the app's component structure, and the WhatsApp/chat assistant).
