import type { Category } from './types'

/** Icon + accent color shown for each expense category, in both the day
 * view's expense rows and the category view's grid/detail panel. */
export const CATEGORY_META: Record<Category, { icon: string; color: string }> = {
  Transporte: { icon: '✈️', color: '#e7a663' },
  Alojamiento: { icon: '🏨', color: '#889fc9' },
  Comida: { icon: '🍴', color: '#e8bd6f' },
  Tours: { icon: '🗺️', color: '#75a995' },
  Crucero: { icon: '🛳️', color: '#77a9c8' },
  Seguro: { icon: '🛡️', color: '#96a7a2' },
  Otros: { icon: '🎒', color: '#b08cc2' },
}

/** Currency symbol shown next to an expense's original (non-COP) amount. */
export const CURRENCY_SYMBOLS: Record<string, string> = { EUR: '€', CHF: 'CHF', CZK: 'Kč', USD: 'US$', COP: '$' }
