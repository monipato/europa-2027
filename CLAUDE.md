# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page Vite + React (TypeScript) site presenting a personal family trip-planning itinerary and cost quote for two independent 2027 trips: a month in Europe (with a Mediterranean cruise, plus an alternate "Alpes Suizos, Alsacia y Mar Mediterráneo" routing) and a Disney World/Universal Orlando trip, plus a from-scratch Japan itinerary. All amounts are per-person COP figures. The UI copy is in Spanish (it's for the traveling family); code and comments are in English.

## Commands

- `npm run dev` — start the Vite dev server
- `npm run build` — typecheck (`tsc -p tsconfig.app.json`) then production build via Vite
- `npm run preview` — preview the production build
- `python3 scripts/generate_data.py` — regenerate `src/data/generated/itinerary.generated.ts` from `data/*.json`. Run this after hand-editing any file under `data/`.
- `python3 scripts/manage_item.py add|update|delete ...` — add, update, or delete a single line item (flight, hotel, tour, SIM card, etc.) in one of the 3 day-by-day options, then regenerates automatically. See the `trip-item` skill for the full field reference.
- `python3 scripts/update_rates.py` — fetch live EUR/CHF/CZK/USD/JPY rates into `data/rates.json` and regenerate. See the `update-rates` skill.
- `python3 scripts/update_climate.py` — refresh each day's real sunrise/sunset/weather, written directly onto that day in its option's JSON file, and regenerate. See the `update-climate` skill.
- `python3 scripts/generate_brand_assets.py` — regenerate the logo/icon/favicon PNGs from `src/patitours.jpg` (requires Pillow: `pip install pillow`, e.g. in the checked-in but gitignored `.venv/`)
- `npm run validate` (or `python3 scripts/validate_data.py`) — sanity-checks every file under `data/`: unknown categories/currencies, a day missing a required field, a city with no `data/cities.json` entry, a negative amount, a note over the 20-word convention, a malformed `routeOverride`. Runs automatically as part of `npm run build` (which fails if it finds an error), so a bad hand-edit gets caught before it ever reaches `generate_data.py`. Add `--check-links` to also HEAD every item's link — slower and needs network, and a 403/405/429 there usually just means the site blocks automated requests (Viator, GetYourGuide, Hyatt, etc. do this to real browsers too), not that the link is actually dead; only a 404/410 is reported as a confident dead link.

Each day's "Qué llevar" packing tip is computed automatically inside `generate_data.py` (`compute_packing()`) from that day's `dayKind`/weather/line items — there's no data file or script for it, since packing guidance doesn't go stale the way a rate or a forecast does. See the `update-packing` skill.

There is no test suite or linter configured.

## Architecture

Data flows one way, and everything downstream just renders it:

```
data/*.json  →  scripts/generate_data.py  →  src/data/generated/itinerary.generated.ts  →  App.tsx + components
```

Every trip price, date, and note is plain JSON you can open and read directly — there's no spreadsheet, no binary format, and no XML surgery anywhere in this pipeline. `generate_data.py` only ever does arithmetic (currency conversion, per-person division) and city lookups (country/flag/photo) — it never guesses a day's city, title, or weather from its line items; every option states those directly, day by day.

### Data (`data/`)

- **`data/rates.json`** — the 5 exchange rates shown in the footer (`ExchangeRatesCard`) and used to convert every non-COP price to COP. Each entry has a `baseRate` (live, refreshed by `update_rates.py`) and shares one `markup` (currently 1.05 — the family's standing "always add 5% more" policy; edit it by hand here if that ever changes). The rate actually used anywhere is always `baseRate * markup`, computed fresh at generate time — nothing pre-computed is stored. `updatedAt` drives the "Tasas estimadas · {date}" header.
- **`data/cities.json`** — one entry per city: `country`, `emoji` (the flag), `images` (a small photo pool so a city visited on consecutive days doesn't repeat its hero photo — see `image_for_day` in `generate_data.py`), `climate` (a seasonal-estimate fallback, real data for Orlando/Japón — see below — and a `packing` tip used as the packing checklist's fallback line for every option), `weatherSourceUrl`/`sunSourceUrl` (the "Ver fuente" links).
- **`data/tours.json`** — a flat `{ "<item title>": "<details>" }` map for tours/excursions shared across the day-by-day options (the same Royal Caribbean cruise excursion, e.g., appears verbatim in "1 mes por Europa", "Alpes Suizos..." and "Crucero en pareja"). `details` is a longer free-text description (highlights, language, accessibility, duration...) that's deliberately never shown in the app UI (unlike `note`, it has no word-count convention) — its only consumer is `netlify/functions/_lib/tripContext.ts`, which folds it into the WhatsApp/chat assistant's system prompt so it can answer detailed questions about a tour. `generate_data.py` looks up an item's `details` by its exact `title` and falls back to nothing if absent — most items don't have one. Edit this file directly, or use `manage_item.py add|update --details "..."` (which writes here, keyed by the item's title, not into the option's own JSON).
- **`data/options/{europa,alpes-suizos,crucero-en-pareja}.json`** — the day-by-day options (the Europa trip plus its "Alpes Suizos..." variant, and the 2-person cruise-only option). Each file is a top-level `name`/`dates`/`color`/`description`/`peopleCount`/`routeOverride` plus a `days` array. **Every day states its own facts directly** — `dayKey`, `city`, `title`, `dayKind` (`"flight"` | `"embark"` | `null`), and a `weather` object (`sunrise`/`sunset`/`temp`/`weatherIcon`/`weather`) — followed by that day's `items`: `category` (one of `Vuelos y Trenes`, `Traslados`, `Alojamiento`, `Crucero`, `Tours y Excursiones`, `Comidas`, `Seguro de Viaje`, `Otros y Extras`), `place`, `date` (display text — can be a range like `"7 – 9 May (2 noches, pre-crucero)"`, independent of which day it's filed under), `title`, `currency`, `unitAmount`, `quantity` (the item's real total = `unitAmount × quantity`, split evenly across `peopleCount` — a per-person item sets `quantity` to the traveler count and `unitAmount` to the per-person price, a shared/bundled item sets `quantity: 1` and `unitAmount` to the group total), `note`, `link` (optional, renders a "Ver tour o sitio web" button). A day whose weather belongs to a day-trip destination rather than its own base city (e.g. an Alpine excursion) adds an explicit `climateCity` field — see `alpes-suizos.json`'s "02 MAY" for a real example; nothing is inferred from a keyword or a place string anywhere in this pipeline. `routeOverride` (an array of city names) replaces the auto-derived route badge on the selection card, when a plain "every city in day order" list isn't the story worth telling (used today only by "Alpes Suizos...", which skips the obvious arrival cities and names the actual excursion landmark instead of the port town it departs from).
- **`data/options/{orlando-jero,orlando-pachito-vale}.json`** — shaped differently on purpose: costs are bucketed per category *and* per traveler-type (adults vs. children price Disney/Universal/food differently), not one row per dated item, and the day-by-day plan is a fixed 9-day calendar (`DISNEY_DAYS` in `generate_data.py`) with a per-day `planNote`/`planNoteCaption` (a ride-by-ride plan + a height/age caveat) and its own real per-day `weather` object rather than its own priced line items. Both files' `dayPlans` carry the same 9 dates and the same weather (one calendar, shared by both subgroups) — `update_climate.py` fetches it once and writes it into both. `composition` (adults/children counts, the child's age label, whether a "hasAdolescent" pays the adult fare) and `budget` (named fields like `disneyAdultUnit`/`foodChildPerDay` — no cryptic cell references) drive `build_disney_option()`'s blended-vs-real pricing math (see that function's own comments for the reasoning: the day/category views show a blended per-person average, while `perPersonByType` on the option gives each traveler type's real total). `rateUsdToCop` is this option's own TRM, deliberately independent from `rates.json`'s USD rate (real, differently-sourced numbers — not a bug if they don't match `ExchangeRatesCard`'s footer).
- **`data/options/japon.json`** — the only option with no source spreadsheet ever, still: the itinerary came directly from a written plan (real ticketed flights, estimated hotel/park-ticket/local-transport costs) and lives as day-by-day JSON like the Europa options above, each day with its own real per-day `weather` too (except "En vuelo", the transit day, which has no real location and keeps a static placeholder), with one addition — a `tiers` array on an item (instead of `unitAmount`/`quantity`) for a ticket priced differently per traveler type (Tokyo Disney's adult/junior/child fares, USJ's adult/child fares): `{"label": "adulto (18+)", "unitAmount": 143.42, "count": 4}`. `jpyPerUsd` is a fixed rate (152.0, the rate implied by the plan's own JPY→USD approximations at the time it was written) used only for the JPY-quoted tickets/train fares; the two real hotel bookings are priced in true `"currency": "JPY"` instead, converted at `rates.json`'s live JPY rate. `composition` records the traveler mix (adults/adolescents/children) used by `perPersonByType`.

### Editing trip data

- **A price, note, date, or link on an existing item** — `python3 scripts/manage_item.py update --option <id> --match-title "..." ...` (or edit the JSON directly — it's the same file either way; the script just adds a safety net against an ambiguous match and a 20-word note-length check). See the `trip-item` skill.
- **A new line item on an existing day** — same script, `add` action; it places the item on the day matching `--date`.
- **A new day, or changing which city/title/weather a day itself shows** — edit `data/options/<id>.json` directly; a day needs more than one line item's worth of fields (city, title, weather), so there's no guided command for it. Always re-run `python3 scripts/generate_data.py` afterward (or let `manage_item.py`/`update_rates.py`/`update_climate.py` do it for you, since they all call it at the end).
- **Exchange rates** — `python3 scripts/update_rates.py` (the `update-rates` skill).
- **Weather/sunrise/sunset** — `python3 scripts/update_climate.py` (the `update-climate` skill).
- **A brand-new trip option** (day-by-day shape only) — two skills run back to back: `new-trip` turns a plain-language description of the trip into `data/options/<id>.json`, then `wire-up-trip` registers that id in the 3 scripts that hardcode the day-by-day option list (`generate_data.py`, `manage_item.py`, `validate_data.py`), adds any new cities to `data/cities.json`, and regenerates/validates.
- `manage_item.py` only covers the day-by-day options (`europa`, `alpes-suizos`, `crucero-en-pareja`, and any added since via `new-trip`/`wire-up-trip` — the `--option` flag takes this file id, not the display name shown in the app, so renaming an option's `"name"` field never requires touching this script). Orlando and Japón are edited by hand in their own JSON files, for the reasons described above.

### App layer (`src/`)

- **`main.tsx`** is the bootstrap only (mounts `<App />`). All state and composition lives in **`App.tsx`**.
- **`App.tsx`** owns the UI state (selected trip option, current view, selected day/category, mobile menu) and composes the presentational components below. It contains no formatting or data-shaping logic — that lives in `utils/`.
- **`types.ts`** — the `Category` union (must stay in sync with `CATEGORY_BY_EXCEL` in the generator script) and `ViewMode`.
- **`constants.ts`** — `CATEGORY_META`: icon, color, and a `duck` sticker per category, shown in the "Por rubro" cards (`CategoryBreakdownView`). `CURRENCY_SYMBOLS` — the symbol shown next to a non-COP expense's original amount (`€`, `US$`, `¥`, etc.).
- **`hooks/useTheme.ts`** — light/dark theme state; see "Brand assets and theming" below.
- **`utils/currency.ts`** — `formatCOP` and `formatExpenseAmount`. Every non-COP expense is always rendered as *original currency · COP equivalent* (e.g. "€ 75 · $ 281.295") — never add a path that shows only the converted COP figure for a foreign-currency line.
- **`utils/dayDisplay.ts`** — `getDayDisplayLabel`, which turns a day's `dayKind` into the ✈️ "Vuelo" / 🛳️ "Embarque" override.
- **`utils/tripStats.ts`** — `sumExpensesByCategory` and `collectExpensesByCategory`, the two aggregations behind the "Por rubro" view. Both read straight from a trip option's `itinerary`, which is also what the day view renders — so the two views and the summary total can never drift out of sync with each other, regardless of how the source JSON is organized. `collectCountryFlags` — the deduplicated flag row on each selection-screen card.
- **`utils/expenseLink.ts`** — `isDownloadableLink`/`expenseLinkLabel`: a `.pdf` expense link (a hotel confirmation) renders as a real download button; anything else opens in a new tab as an external site.
- **`utils/duckStickers.ts`** — `assignDuckStickers`, the small decorative duck shown on each day's hero photo in `DayByDayView`; see "Brand assets and theming" below.
- **`components/`** — one file per UI section, each a plain presentational component (props in, JSX out, no data fetching):
  - `AppHeader`, `AppFooter` — chrome. `AppHeader` also hosts `ThemeToggle`.
  - `ThemeToggle` — the light/dark switch button.
  - `TripSelectionScreen` — the landing screen (welcome copy + the option cards). Picking a card both selects the option and enters the planner in one step.
  - `PlannerHeading` — the "back to selection" bar shown once inside the planner.
  - `ExchangeRatesCard` — reused by both of the above; takes the occupancy-note copy as a prop since the wording differs slightly between the two places it appears.
  - `TripSummaryBar` — the route + per-person-price bar shown above both itinerary views.
  - `DayByDayView` — the "Por día" tab: day list + selected day's hero/expenses, with a small duck sticker overlaid on the hero photo when one fits.
  - `CategoryBreakdownView` — the "Por rubro" tab: compact category cards (icon + name + total) and a drill-down detail popup.

### Brand assets and theming

- **`src/patitours.jpg`** is the source-of-truth logo lockup. `scripts/generate_brand_assets.py` derives everything else from it into `src/assets/brand/` (light/dark full lockup + icon-only crops, plus `public/favicon.png`). Never hand-edit those generated PNGs — replace `src/patitours.jpg` and re-run the script.
- Theming is CSS custom properties (`src/styles.css`), not two parallel stylesheets — every color is a `--token` in `:root` with overrides in both `@media (prefers-color-scheme: dark)` and `:root[data-theme="dark"]`. `src/hooks/useTheme.ts` resolves the initial theme and persists explicit choices to `localStorage`. When adding a new color, add a token pair (light + dark) rather than hardcoding a hex.
- **`src/assets/ducks/*.png`** are the app's small decorative "traveling duck" stickers (not the logo, not emoji) — final, hand-cropped, checked-in assets with no generator script. `src/utils/duckStickers.ts`/`weatherDuck.ts`/`tourDuck.ts` each assign a duck from a *pool* (≥2 candidates) per day, so a run of similar days never repeats one fixed duck — see each file's own top comment for its reserved pool and priority order.

### WhatsApp/chat AI assistant (`netlify/functions/`)

Separate concern from the React app above, unaffected by anything in this file's "Data" section: `netlify/functions/twilio-whatsapp-webhook.mts` answers WhatsApp questions about the trip using Twilio's WhatsApp channel + Gemini, and there's also an in-app chat panel. Both reuse the same generated trip data as their source of truth (`netlify/functions/_lib/tripContext.ts` builds the AI's system prompt directly from `generatedOptions`), but have no UI dependency on how that data file was produced.

- The webhook replies as **TwiML in its own HTTP response** (`<Response><Message>...</Message></Response>`), not a separate Twilio API call — this avoids needing Twilio's compliance/KYC approval for outbound messages. It validates `X-Twilio-Signature` (`netlify/functions/_lib/twilio.ts`'s `verifyTwilioSignature`) against the parsed form body.
- `netlify/functions/_lib/db.ts` stores conversations/messages in Postgres (Neon, via `@neondatabase/serverless`) — reads `DATABASE_URL`/`POSTGRES_URL`.
- `netlify/functions/_lib/gemini.ts` calls the Gemini API with the system prompt + conversation history. `GEMINI_MODEL` defaults to `gemini-flash-lite-latest` (an alias Google keeps pointed at the current lightweight Flash model, not a pinned snapshot).
- Required env vars are listed in `.env.example` — set them in the Netlify UI, never in a committed file. Never log `TWILIO_AUTH_TOKEN` or `GEMINI_API_KEY`, and never expose them to the client bundle.
- `tsconfig.api.json` typechecks `netlify/functions/` separately from the app (it targets Node with Web-standard `Request`/`Response`, not the browser DOM); it's not part of `npm run build`. Netlify bundles each function itself at deploy time (esbuild, per `netlify.toml`).

### Keeping this consistent

- If you add a new expense category or trip option shape, decide its JSON shape first (does it fit the day-by-day `items` model, or does it need its own bucketed shape like Orlando?), wire it into `generate_data.py`'s `main()`, regenerate, and only then touch `constants.ts`/components if a new category needs its own icon/color.
- `src/styles.css` is a single global stylesheet. If you remove a class from a component, grep the CSS for it and delete the now-dead rule.
- `src/assets/` is organized by subfolder (`brand/`, `ducks/`) — put a new image asset in an existing subfolder if it fits, or create a new one.
