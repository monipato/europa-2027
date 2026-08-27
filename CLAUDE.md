# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page Vite + React (TypeScript) site presenting a personal Europe 2027 trip itinerary and cost quote, generated from an Excel workbook (`Europa2027_Cotizacion_plan_completo (1).xlsx`). All amounts are per-person COP figures for a party of 3 sharing triple-occupancy rooms. The UI copy is in Spanish (it's for the traveling family); code and comments are in English.

## Commands

- `npm run dev` — start the Vite dev server
- `npm run build` — typecheck (`tsc -p tsconfig.app.json`) then production build via Vite
- `npm run preview` — preview the production build
- `python3 scripts/generate_data.py` — regenerate `src/data/generated/itinerary.generated.ts` from the Excel workbook (run from the project root; requires the workbook at the repo root)

There is no test suite or linter configured.

## Architecture

Data flows one way, in one place, and everything downstream just renders it:

```
Excel workbook  →  scripts/generate_data.py  →  src/data/generated/itinerary.generated.ts  →  App.tsx + components
```

### Data layer (`src/data/`)

- **`src/data/generated/itinerary.generated.ts`** is generated (header says "do not edit manually") by `scripts/generate_data.py`. It is the app's *only* data source — never hand-edit trip options, days, or expenses in a component; fix the workbook or the script instead, then regenerate. It exports:
  - `generatedOptions: GeneratedOption[]` — one entry per trip option (Completo, Solo crucero, Zúrich y Crucero, Múnich y Crucero), each with its full per-day `itinerary`, route, and `perPerson`/`total` cost.
  - `exchangeRates` / `ratesUpdatedAt` — the reference exchange rates shown in the UI (informational only; nothing is converted using them at render time — every amount already carries its own converted COP value).
- `generate_data.py` parses the `.xlsx` directly as a zip of XML (no external dependency), reading four sheets by index (sheet4=Completo, sheet6=Zúrich y Crucero, sheet8=Múnich y Crucero, sheet10=Solo crucero) plus the `Tasas de Cambio` sheet (sheet3) for exchange rates. It keeps only rows whose category matches a fixed whitelist (Vuelos y Trenes, Traslados, Alojamiento, Crucero, Tours y Excursiones, Comidas, Seguro de Viaje, Otros y Extras), drops rows with a blank title (merged-cell formatting leftovers), and drops zero-value/"N/A" placeholder rows from what's displayed as an expense (see `is_placeholder`) while still using them to keep day continuity (a day with only zero-cost lines still gets a card). If the workbook's sheet layout, column order, or sheet-to-option assignment changes, update the script's column-letter mapping (`A`–`M`) and sheet-number list together — then re-run the script and confirm the printed per-option totals still match the workbook's own "Resumen Comparativo" sheet.
- Two Excel quirks the script corrects for, which will resurface if the workbook is edited by hand again:
  - Some sheets store the date column as a raw Excel serial number instead of formatted text (`normalize_date`/`excel_serial_to_text`) — always cross-check a fresh export's date column before assuming it's already a string.
  - `Seguro de Viaje` rows carry a coverage-period date range (e.g. "29 Abr – 30 May … cobertura"), not an itinerary stop — it's treated as dateless (like `Otros y Extras`) and attached to day one, rather than parsed as its own day.
- The script derives each day's city from its lines' `place` text via `CITY_ALIASES`/`day_city` (prioritizing that day's `Alojamiento` entry, then falling back to substring-matching known city names, then carrying forward the previous day's city) — there is no separate hand-maintained per-day city list. `CITY_INFO` supplies the cosmetic country/emoji/image per canonical city name; adding a new destination means adding it to both `CITY_INFO` and `CITY_ALIASES`.
- A day's `dayKind` (`'flight' | 'embark' | null`, also computed by the script) marks the outbound-flight day and the cruise-embarkation day so the UI can show a plane/boat icon instead of the destination's country flag for those two transit days — see `getDayDisplayLabel` below.

### App layer (`src/`)

- **`main.tsx`** is the bootstrap only (mounts `<App />`). All state and composition lives in **`App.tsx`**.
- **`App.tsx`** owns the UI state (selected trip option, current view, selected day/category, mobile menu) and composes the presentational components below. It contains no formatting or data-shaping logic — that lives in `utils/`.
- **`types.ts`** — the `Category` union (must stay in sync with `CATEGORY_BY_EXCEL` in the generator script) and `ViewMode`.
- **`constants.ts`** — `CATEGORY_META` (icon + color per category) and `CURRENCY_SYMBOLS`.
- **`utils/currency.ts`** — `formatCOP` and `formatExpenseAmount`. Every non-COP expense is always rendered as *original currency · COP equivalent* (e.g. "€ 75 · $ 281.295") — never add a path that shows only the converted COP figure for a foreign-currency line.
- **`utils/dayDisplay.ts`** — `getDayDisplayLabel`, which turns a day's `dayKind` into the ✈️ "Vuelo" / 🛳️ "Embarque" override described above.
- **`utils/tripStats.ts`** — `sumExpensesByCategory` and `collectExpensesByCategory`, the two aggregations behind the "Por rubro" view. Both read straight from a trip option's `itinerary`, which is also what the day view renders — so the two views and the summary total can never drift out of sync with each other.
- **`components/`** — one file per UI section, each a plain presentational component (props in, JSX out, no data fetching):
  - `AppHeader`, `AppFooter` — chrome.
  - `TripSelectionScreen` — the landing screen (welcome copy + the 4 option cards). Picking a card both selects the option and enters the planner in one step.
  - `PlannerHeading` — the "back to selection" bar shown once inside the planner.
  - `ExchangeRatesCard` — reused by both of the above; takes the occupancy-note copy as a prop since the wording differs slightly between the two places it appears.
  - `TripSummaryBar` — the route + per-person-price bar shown above both itinerary views.
  - `DayByDayView` — the "Por día" tab: day list + selected day's hero/expenses.
  - `CategoryBreakdownView` — the "Por rubro" tab: category grid + drill-down detail panel.

### Keeping this consistent

- If you add a new expense category or trip option shape, update it in the generator script first (`CATEGORY_BY_EXCEL`, `CITY_INFO`/`CITY_ALIASES`, `options_meta` in `main()`), regenerate, and only then touch `constants.ts`/components if the new category needs its own icon/color.
- `src/styles.css` is a single global stylesheet (not co-located per component). It's been swept of rules with no matching class in the JSX — if you remove a class from a component, grep the CSS for it and delete the now-dead rule rather than leaving it behind.
