import type { GeneratedExpense } from '../data/generated/itinerary.generated'
import { CURRENCY_SYMBOLS } from '../constants'

/**
 * Formats a COP amount as currency, e.g. "$ 1.886.015".
 *
 * A zero amount means the cost is bundled into another line item (the data
 * generator drops real zero-value "N/A" placeholder rows — see
 * `is_placeholder` in `scripts/generate_data.py`), so it reads as "Incluido"
 * instead of a bare "$ 0".
 */
export function formatCOP(amount: number): string {
  if (amount === 0) return 'Incluido'
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(amount)
}

/**
 * Formats an expense amount for display. A non-COP expense always shows its
 * original quoted currency next to its COP equivalent (e.g. "€ 75 · $ 281.295"),
 * so the reader never sees a converted number without the source amount
 * alongside it.
 */
export function formatExpenseAmount(expense: GeneratedExpense): string {
  const copAmount = formatCOP(expense.amount)
  if (expense.currency === 'COP') return copAmount
  const symbol = CURRENCY_SYMBOLS[expense.currency] ?? expense.currency
  const originalAmount = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(expense.originalAmount)
  return `${symbol} ${originalAmount} · ${copAmount}`
}
