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
 * a literal one.
 *
 * Kept out of `constants.ts` on purpose: these PNG imports need Vite's asset
 * pipeline, which `netlify/functions/` doesn't have (its esbuild bundle has
 * no loader for `.png`) — anything importable from a Netlify function
 * (`tripContext.ts` → `utils/currency.ts` → `constants.ts`) must stay
 * asset-free, so this file exists to keep the two apart. */
export const CATEGORY_META: Record<Category, { icon: string; color: string; duck: string }> = {
  Transporte: { icon: '✈️', color: '#e7a663', duck: duckAirplaneWindow },
  Alojamiento: { icon: '🏨', color: '#889fc9', duck: duckCamping },
  Comida: { icon: '🍴', color: '#e8bd6f', duck: duckCatFood },
  Tours: { icon: '🗺️', color: '#75a995', duck: duckCity },
  Crucero: { icon: '🛳️', color: '#77a9c8', duck: duckCruise },
  Seguro: { icon: '🛡️', color: '#96a7a2', duck: duckArctic },
  Otros: { icon: '🎒', color: '#b08cc2', duck: duckShopping },
}
