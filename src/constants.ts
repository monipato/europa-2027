import type { Category } from './types'
import duckAirplaneWindow from './assets/ducks/duck-airplane-window.png'
import duckCamping from './assets/ducks/duck-camping.png'
import duckCatFood from './assets/ducks/duck-cat-food.png'
import duckCity from './assets/ducks/duck-city.png'
import duckCruise from './assets/ducks/duck-cruise.png'
import duckArctic from './assets/ducks/duck-arctic.png'
import duckShopping from './assets/ducks/duck-shopping.png'

/** Icon + accent color shown for each expense category, in both the day
 * view's expense rows and the category view's grid/detail panel. `duck`
 * replaces the emoji with a small duck sticker in the category-view card —
 * Seguro has no exact match among the available stickers, so it uses the
 * closest fit (a bundled-up "protected from the elements" duck) rather than
 * a literal one. */
export const CATEGORY_META: Record<Category, { icon: string; color: string; duck: string }> = {
  Transporte: { icon: '✈️', color: '#e7a663', duck: duckAirplaneWindow },
  Alojamiento: { icon: '🏨', color: '#889fc9', duck: duckCamping },
  Comida: { icon: '🍴', color: '#e8bd6f', duck: duckCatFood },
  Tours: { icon: '🗺️', color: '#75a995', duck: duckCity },
  Crucero: { icon: '🛳️', color: '#77a9c8', duck: duckCruise },
  Seguro: { icon: '🛡️', color: '#96a7a2', duck: duckArctic },
  Otros: { icon: '🎒', color: '#b08cc2', duck: duckShopping },
}

/** Currency symbol shown next to an expense's original (non-COP) amount. */
export const CURRENCY_SYMBOLS: Record<string, string> = { EUR: '€', CHF: 'CHF', CZK: 'Kč', USD: 'US$', COP: '$' }

/** PatiTours' WhatsApp Business number (the one wired to the Twilio webhook
 * + AI assistant — see `netlify/functions/twilio-whatsapp-webhook.mts`).
 * Digits only, country code first, no "+" or spaces — this is the format
 * `wa.me` links expect. Public by design, not a secret. */
export const WHATSAPP_NUMBER = '573042519907'
