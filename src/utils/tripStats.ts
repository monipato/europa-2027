import type { GeneratedDay, GeneratedExpense } from '../data/generated/itinerary.generated'
import type { Category } from '../types'

/** Sums every expense across all days of an itinerary, grouped by category.
 * Used to drive the "Por rubro" (by category) view — since it reads from
 * the same `days` array as the day view, the two views can never drift out
 * of sync with each other or with the trip's advertised total. */
export function sumExpensesByCategory(days: GeneratedDay[]): Partial<Record<Category, number>> {
  const totals: Partial<Record<Category, number>> = {}
  for (const day of days) {
    for (const expense of day.expenses) {
      const category = expense.category as Category
      totals[category] = (totals[category] ?? 0) + expense.amount
    }
  }
  return totals
}

/** Every expense in a single category across the whole itinerary, each
 * tagged with the day it happened on — the data behind the "Detalle del
 * rubro" drill-down. */
export function collectExpensesByCategory(days: GeneratedDay[], category: Category): Array<GeneratedExpense & { dayKey: string }> {
  return days.flatMap(day =>
    day.expenses
      .filter(expense => expense.category === category)
      .map(expense => ({ ...expense, dayKey: day.dayKey })),
  )
}

/** The country flags an itinerary actually visits, in the order they first
 * appear, deduplicated. Days at sea ("En el mar", country "Mediterráneo")
 * aren't a real country, so they're excluded rather than showing a boat
 * emoji next to a row of flags. */
export function collectCountryFlags(days: GeneratedDay[]): string[] {
  const seen = new Set<string>()
  const flags: string[] = []
  for (const day of days) {
    if (day.country === 'Mediterráneo' || day.country === 'Europa') continue
    if (seen.has(day.emoji)) continue
    seen.add(day.emoji)
    flags.push(day.emoji)
  }
  return flags
}
