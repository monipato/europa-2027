/**
 * UI-facing domain types.
 *
 * The itinerary data itself (trip options, days, expenses) is generated from
 * the quote spreadsheet — see `src/data/generated/itinerary.generated.ts`
 * and `scripts/generate_data.py`. This file only holds types used to
 * *render* that data.
 */

/**
 * The seven expense categories shown throughout the UI (day view, category
 * view). Must stay in sync with `CATEGORY_BY_EXCEL` in
 * `scripts/generate_data.py` — every generated expense's `category` field
 * is one of these strings.
 */
export type Category = 'Transporte' | 'Alojamiento' | 'Comida' | 'Tours' | 'Crucero' | 'Seguro' | 'Otros'

/** Which of the two itinerary views the user is currently looking at. */
export type ViewMode = 'day' | 'category'
