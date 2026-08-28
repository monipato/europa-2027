# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page Vite + React (TypeScript) site presenting a personal Europe 2027 trip itinerary and cost quote, generated from an Excel workbook (`Europa2027_Cotizacion_plan_completo (1).xlsx`). All amounts are per-person COP figures for a party of 3 sharing triple-occupancy rooms. The UI copy is in Spanish (it's for the traveling family); code and comments are in English.

## Commands

- `npm run dev` — start the Vite dev server
- `npm run build` — typecheck (`tsc -p tsconfig.app.json`) then production build via Vite
- `npm run preview` — preview the production build
- `python3 scripts/generate_data.py` — regenerate `src/data/generated/itinerary.generated.ts` from the Excel workbook (run from the project root; requires the workbook at the repo root)
- `python3 scripts/manage_item.py add|update ...` — add or update a single line item (flight, hotel, tour, SIM card, etc.) directly in the workbook, then regenerates the data file automatically. This is the only supported way to hand-edit a line item — see the `trip-item` skill (`.claude/skills/trip-item/SKILL.md`) for the full field reference and conventions (note ≤ 20 words, optional link, per-person vs. shared amounts, live currency-rate lookups).
- `python3 scripts/generate_brand_assets.py` — regenerate the logo/icon/favicon PNGs from `src/patitours.jpg` (requires Pillow: `pip install pillow`, e.g. in the checked-in but gitignored `.venv/`)

There is no test suite or linter configured.

## Architecture

Data flows one way, in one place, and everything downstream just renders it:

```
Excel workbook  →  scripts/generate_data.py  →  src/data/generated/itinerary.generated.ts  →  App.tsx + components
```

### Data layer (`src/data/`)

- **`src/data/generated/itinerary.generated.ts`** is generated (header says "do not edit manually") by `scripts/generate_data.py`. It is the app's *only* data source — never hand-edit trip options, days, or expenses in a component; fix the workbook or the script instead, then regenerate. It exports:
  - `generatedOptions: GeneratedOption[]` — one entry per trip option (Completo, Solo crucero, Solo crucero (2 personas), Zúrich y Crucero, Múnich y Crucero), each with its full per-day `itinerary`, route, `perPerson`/`total` cost, and `peopleCount`.
  - `exchangeRates` / `ratesUpdatedAt` — the reference exchange rates shown in the UI (informational only; nothing is converted using them at render time — every amount already carries its own converted COP value).
- `generate_data.py` parses the `.xlsx` directly as a zip of XML (no external dependency), reading each option's sheet by index (sheet4=Completo, sheet6=Zúrich y Crucero, sheet8=Múnich y Crucero, sheet10=Solo crucero, sheet12=Solo crucero 2P) plus the `Tasas de Cambio` sheet (sheet3) for exchange rates and the shared traveler count. It keeps only rows whose category matches a fixed whitelist (Vuelos y Trenes, Traslados, Alojamiento, Crucero, Tours y Excursiones, Comidas, Seguro de Viaje, Otros y Extras), drops rows with a blank title (merged-cell formatting leftovers), and drops "N/A" placeholder rows from what's displayed as an expense (see `is_placeholder`) while still using them to keep day continuity (a day with only placeholder lines still gets a card) — a genuine zero-cost item with a real title (e.g. "Tour a pie gratis") *is* displayed, rendered as "Incluido". If the workbook's sheet layout, column order, or sheet-to-option assignment changes, update the script's column-letter mapping (`A`–`M`) and sheet-number list together, then re-run the script.
- `peopleCount` is per-option, not a single global number: every sheet's per-person amounts (column K) divide by the same `'Tasas de Cambio'!$C$5` cell *except* sheets built for a different headcount (like sheet12, a duplicate of Solo crucero for 2 travelers — see `scripts/duplicate_option.py`), whose K-column formulas divide by a literal number instead. `generate_data.py`'s `options_meta` carries each option's own `people_count`; `manage_item.py`'s `OPTION_PEOPLE_OVERRIDE` does the same for future edits to that sheet. Read the K-column cached values directly rather than assuming a shared divisor.
- To duplicate an existing option's sheet for a different headcount, see `scripts/duplicate_option.py` — it copies the sheet's worksheet/drawing/rels parts via targeted regex row-surgery (never a full-document XML parse/reserialize on these large sheets; see the module docstring for why), reduces quantity on truly per-person rows while keeping their unit price, and clears bundled/shared-total rows (hotel, SIM, cruise cabin fare, group transfers) to a "Pendiente cotizar" placeholder rather than guessing a new total. It's written for this one duplication; adapt the row classification (`CLEAR_ROWS`) for a future one.
- The workbook has 11 sheets total, but only these 5 are ever read: `Tasas de Cambio` and the four detail sheets above. The other 6 — `Resumen Comparativo`, `Instrucciones`, and one per-option `Resumen`/`Resumen CZ`/`Resumen Opción 4`/`Resumen Crucero` sheet (in-Excel SUMIF category summaries, not read by the generator) — are hidden (not deleted) in the workbook and should be ignored entirely: don't keep them in sync, don't duplicate them when adding a new trip-option sheet, don't treat their numbers as a source of truth.
- Two Excel quirks the script corrects for, which will resurface if the workbook is edited by hand again:
  - Some sheets store the date column as a raw Excel serial number instead of formatted text (`normalize_date`/`excel_serial_to_text`) — always cross-check a fresh export's date column before assuming it's already a string.
  - `Seguro de Viaje` rows carry a coverage-period date range (e.g. "29 Abr – 30 May … cobertura"), not an itinerary stop — it's treated as dateless (like `Otros y Extras`) and attached to day one, rather than parsed as its own day.
- The script derives each day's city from its lines' `place` text via `CITY_ALIASES`/`day_city` (prioritizing that day's `Alojamiento` entry, then falling back to substring-matching known city names, then carrying forward the previous day's city) — there is no separate hand-maintained per-day city list. `CITY_INFO` supplies the cosmetic country/emoji/image per canonical city name; adding a new destination means adding it to both `CITY_INFO` and `CITY_ALIASES`.
- A day's `dayKind` (`'flight' | 'embark' | null`, also computed by the script) marks the outbound-flight day and the cruise-embarkation day so the UI can show a plane/boat icon instead of the destination's country flag for those two transit days — see `getDayDisplayLabel` below.

### App layer (`src/`)

- **`main.tsx`** is the bootstrap only (mounts `<App />`). All state and composition lives in **`App.tsx`**.
- **`App.tsx`** owns the UI state (selected trip option, current view, selected day/category, mobile menu) and composes the presentational components below. It contains no formatting or data-shaping logic — that lives in `utils/`.
- **`types.ts`** — the `Category` union (must stay in sync with `CATEGORY_BY_EXCEL` in the generator script) and `ViewMode`.
- **`constants.ts`** — `CATEGORY_META`: icon, color, and a `duck` sticker per category, shown in the "Por rubro" cards (`CategoryBreakdownView`). Every category has a duck; two (Comida, Seguro) have no exact thematic match among the available stickers, so they use the closest fit rather than a literal one — see the comment there before swapping one out. `icon` (the emoji) is still what's used for the small per-expense icon in the day view.
- **`hooks/useTheme.ts`** — light/dark theme state; see "Brand assets and theming" below.
- **`utils/currency.ts`** — `formatCOP` and `formatExpenseAmount`. Every non-COP expense is always rendered as *original currency · COP equivalent* (e.g. "€ 75 · $ 281.295") — never add a path that shows only the converted COP figure for a foreign-currency line.
- **`utils/dayDisplay.ts`** — `getDayDisplayLabel`, which turns a day's `dayKind` into the ✈️ "Vuelo" / 🛳️ "Embarque" override described above.
- **`utils/tripStats.ts`** — `sumExpensesByCategory` and `collectExpensesByCategory`, the two aggregations behind the "Por rubro" view. Both read straight from a trip option's `itinerary`, which is also what the day view renders — so the two views and the summary total can never drift out of sync with each other.
- **`utils/duckStickers.ts`** — `assignDuckStickers`, the small decorative duck shown on each day's hero photo in `DayByDayView`; see "Brand assets and theming" below.
- **`components/`** — one file per UI section, each a plain presentational component (props in, JSX out, no data fetching):
  - `AppHeader`, `AppFooter` — chrome. `AppHeader` also hosts `ThemeToggle`.
  - `ThemeToggle` — the light/dark switch button.
  - `TripSelectionScreen` — the landing screen (welcome copy + the 4 option cards). Picking a card both selects the option and enters the planner in one step.
  - `PlannerHeading` — the "back to selection" bar shown once inside the planner.
  - `ExchangeRatesCard` — reused by both of the above; takes the occupancy-note copy as a prop since the wording differs slightly between the two places it appears.
  - `TripSummaryBar` — the route + per-person-price bar shown above both itinerary views.
  - `DayByDayView` — the "Por día" tab: day list + selected day's hero/expenses, with a small duck sticker overlaid on the hero photo when one fits.
  - `CategoryBreakdownView` — the "Por rubro" tab: compact category cards (icon + name + total, no other filler) and a drill-down detail panel that opens as a true centered popup (with a click-outside-to-close backdrop) at every screen width — it is not inline content, don't reintroduce a non-modal fallback for narrow viewports.

### Brand assets and theming

- **`src/patitours.jpg`** is the source-of-truth logo lockup (flat JPEG, white background, icon + "PATITOURS" wordmark). `scripts/generate_brand_assets.py` derives everything else from it into `src/assets/brand/`: a transparent-background full lockup and an icon-only crop, each in a light-ink (navy) and dark-ink (cream) variant, plus `public/favicon.png`. Never hand-edit those generated PNGs or design new ones by hand — replace `src/patitours.jpg` and re-run the script. `AppHeader` picks the light/dark logo variant based on the active theme. (Only the full lockup, light and dark, is actually imported anywhere in code today — the icon-only crops are generated and available but currently unused, same as several `src/assets/ducks/*.png`; that's fine, they're not dead *code*, just an unused asset sitting in the library.)
- Theming is CSS custom properties, not two parallel stylesheets. `src/styles.css` defines every color as a `--token` in `:root` (light values) with overrides in both `@media (prefers-color-scheme: dark)` (pre-JS default) and `:root[data-theme="dark"]` (explicit, wins either way). `src/hooks/useTheme.ts` resolves the initial theme (stored choice, else OS preference), writes `data-theme` onto `<html>`, and persists explicit choices to `localStorage`; `ThemeToggle` in the header flips it. When adding a new color anywhere in the app, add a token pair (light + dark value) rather than hardcoding a hex — a hardcoded color will look right in light mode and wrong (or invisible) in dark mode.
- The header is intentionally light in both themes' "chrome sense" — i.e. it always matches the logo's native context (light ink on a light bg, or the recolored light-ink-on-dark variant in dark mode) rather than the old fixed dark-navy bar. If you redesign the header, keep this pairing: the logo variant and the header background token must change together.
- **`src/assets/ducks/*.png`** are the app's small decorative "traveling duck" stickers (not the logo, not emoji) — reach for one here before adding an emoji duck or new artwork. They're final, hand-cropped, checked-in assets; there is no generator script or source sheet in the repo for them anymore. They came from three source sheets, each deleted once fully cropped (at the user's request, to avoid keeping large unused source images around):
  - `patitos.png` — a 6×7 sheet of ~42 activity stickers (`duck-paris.png`, `duck-gondola.png`, `duck-airplane-window.png`, ...).
  - a 4×3 "Catálogo de Patitos Viajeros" catalog (12 travel-style cards) — cropped into `duck-romantic.png` (the "Romántico" card, used in the footer) and `duck-cat-*.png` (`duck-cat-food.png`, `duck-cat-family.png`, `duck-cat-mountain.png`, ...; see the `GRID`/`COLS`/`ROWS` values used when this was cropped if a similarly-laid-out sheet ever needs slicing again). `duck-cat-food.png` is what `Comida` uses in `CATEGORY_META` — none of the first sheet's 42 fit "food" at all, this catalog's "Gastronómico" card does.
  - `patos.png` — a second 40-sticker activity sheet (uneven grid: 5 rows of 6 cutout stickers plus 2 wider rows of 5 multi-duck group scenes) — cropped into `duck2-*.png` (`duck2-map.png`, `duck2-diving.png`, `duck2-family-3.png`, ...). The `duck2-family-*`/`duck2-couple-paris` group shots are what the "N personas" badge on each trip-option card uses (`PEOPLE_DUCK_BY_COUNT` in `TripSelectionScreen.tsx`, keyed by headcount — 2 → `duck2-family-car.png`, 3 → `duck2-family-3.png`, 4 → `duck2-family-4.png`).

  All three sheets' cards have a baked-in illustrated or cutout-with-white-border background (not transparent) — style these as small rounded badges/stickers, not rotated transparent cutouts. If a new duck crop is ever needed, it has to be sourced from a freshly re-saved sheet — there's nothing left in the repo to re-slice.
- `src/utils/duckStickers.ts` maps a day's `dayKind`/`city` to a *pool* of matching ducks (not a single fixed one) for the small sticker shown on its hero photo (`DayByDayView`); `assignDuckStickers` walks the whole itinerary picking, for each day, the first pool candidate that differs from the previous day's duck — every pool must have ≥2 entries or that guarantee breaks. Cities with no good match are left out on purpose rather than forcing one.

### Keeping this consistent

- If you add a new expense category or trip option shape, update it in the generator script first (`CATEGORY_BY_EXCEL`, `CITY_INFO`/`CITY_ALIASES`, `options_meta` in `main()`), regenerate, and only then touch `constants.ts`/components if the new category needs its own icon/color.
- `src/styles.css` is a single global stylesheet (not co-located per component). It's been swept of rules with no matching class in the JSX — if you remove a class from a component, grep the CSS for it and delete the now-dead rule rather than leaving it behind.
- `src/assets/` is organized by subfolder, not a flat dump — `brand/` (logo/icon variants) and `ducks/` (sticker crops) so far. Put a new image asset in an existing subfolder if it fits, or create a new one; don't add loose files directly under `src/assets/`.
