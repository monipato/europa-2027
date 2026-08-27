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
