import type { GeneratedDay } from '../data/generated/itinerary.generated'

/**
 * The small icon + label shown above a day's title (the day hero banner)
 * and next to its city name in the day list.
 *
 * Transit days — the outbound flight, the cruise embarkation — are marked
 * with their own icon/label (✈️ "Vuelo", 🛳️ "Embarque") instead of the
 * destination's country flag, to call out that this day is about getting
 * somewhere rather than being there. `day.dayKind` is computed once by the
 * data generator (`scripts/generate_data.py`), not re-derived here.
 */
export function getDayDisplayLabel(day: GeneratedDay): { emoji: string; label: string } {
  if (day.dayKind === 'flight') return { emoji: '✈️', label: 'Vuelo' }
  if (day.dayKind === 'embark') return { emoji: '🛳️', label: 'Embarque' }
  return { emoji: day.emoji, label: day.country }
}
