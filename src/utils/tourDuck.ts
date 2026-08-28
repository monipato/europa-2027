import type { GeneratedDay } from '../data/generated/itinerary.generated'
import duckEmbarkFamily from '../assets/ducks/duck2-family-cruise.png'
import duckEmbarkGroup from '../assets/ducks/duck3-group-cruise.png'
import duckFlightSeat from '../assets/ducks/duck2-airplane-seat.png'
import duckFlightAirport from '../assets/ducks/duck-airport.png'
import duckFlightAirport2 from '../assets/ducks/duck2-airport.png'
import duckTrain from '../assets/ducks/duck-train.png'
import duckSeaPaddleboard from '../assets/ducks/duck2-paddleboard.png'
import duckSeaJetski from '../assets/ducks/duck2-jetski.png'
import duckPisaCamera from '../assets/ducks/duck3-camera-canyon.png'
import duckPisaCamera2 from '../assets/ducks/duck2-camera.png'
import duckWalkHiking from '../assets/ducks/duck2-hiking-group.png'
import duckWalkTrekking from '../assets/ducks/duck2-trekking.png'
import duckFoodPasta from '../assets/ducks/duck2-pasta-chef.png'
import duckFoodPizza from '../assets/ducks/duck2-pizza.png'
import duckFoodPicnic from '../assets/ducks/duck3-picnic-couple.png'
import duckParisCouple from '../assets/ducks/duck2-couple-paris.png'
import duckParisCouple2 from '../assets/ducks/duck3-couple-paris.png'
import duckColosseumSolo from '../assets/ducks/duck2-colosseum.png'
import duckColosseumGroup from '../assets/ducks/duck3-group-colosseum.png'
import duckGondola from '../assets/ducks/duck2-gondola.png'
import duckVeneciaCruise from '../assets/ducks/duck-cat-cruise.png'
import duckFlamenco from '../assets/ducks/duck-flamenco.png'
import duckFlamingo from '../assets/ducks/duck2-flamingo.png'
import duckArrivalSuitcase from '../assets/ducks/duck3-suitcase-city.png'
import duckArrivalCatCity from '../assets/ducks/duck-cat-city.png'
import duckDefaultAdventure from '../assets/ducks/duck-cat-adventure.png'
import duckDefaultEco from '../assets/ducks/duck-cat-eco.png'
import duckTourCultural from '../assets/ducks/duck-cat-cultural.png'
import duckTourDreamtrip from '../assets/ducks/duck-cat-dreamtrip.png'

// Candidate ducks per situation, in preference order — every pool has at
// least 2 entries (assignTourDucks greedily skips the previous day's exact
// pick) so e.g. Zúrich's 6 flight-free days or Múnich's 5-day stretch don't
// show one fixed duck on every card. None of these overlap with
// duckStickers.ts's hero-photo pools (duck-airplane-window, duck-cruise,
// duck-paris, duck-pisa, duck-gondola, duck-photographer, duck-map-sit, ...),
// CATEGORY_META, the trip-selection headcount badges, or the footer duck —
// this popup sits right next to the hero sticker, so reusing one of those
// would show the identical image twice in the same view.
const EMBARK_POOL = [duckEmbarkFamily, duckEmbarkGroup]
const FLIGHT_POOL = [duckFlightSeat, duckFlightAirport, duckFlightAirport2]
const SEA_POOL = [duckSeaPaddleboard, duckSeaJetski]
const PISA_POOL = [duckPisaCamera, duckPisaCamera2]
const WALK_TOUR_POOL = [duckWalkHiking, duckWalkTrekking]
const FOOD_TOUR_POOL = [duckFoodPasta, duckFoodPizza, duckFoodPicnic]
const PARIS_POOL = [duckParisCouple, duckParisCouple2]
const ROMA_POOL = [duckColosseumSolo, duckColosseumGroup]
const VENECIA_POOL = [duckGondola, duckVeneciaCruise]
const BARCELONA_POOL = [duckFlamenco, duckFlamingo]
const ARRIVAL_POOL = [duckArrivalSuitcase, duckArrivalCatCity]
const GENERIC_TOUR_POOL = [duckTourCultural, duckTourDreamtrip]
const DEFAULT_POOL = [duckDefaultAdventure, duckDefaultEco]

// Landmark/cultural duck pool per city, for cities where a good one exists
// in the library — checked by day.city (the base city, not climateCity), so
// it applies to any day spent there, tour or not. Cities without a good
// match (Zúrich, Zadar, Salerno, Praga, Berlín, Múnich) fall through to the
// generic pools below rather than forcing a mismatched sticker.
const CITY_TOUR_POOL: Record<string, string[]> = {
  'París': PARIS_POOL,
  'Roma': ROMA_POOL,
  'Venecia': VENECIA_POOL,
  'Barcelona': BARCELONA_POOL,
}

function tourPool(day: GeneratedDay): string[] {
  if (day.dayKind === 'embark') return EMBARK_POOL
  if (day.dayKind === 'flight') return FLIGHT_POOL
  if (day.climateCity === 'Jungfraujoch') return [duckTrain]
  if (day.city === 'En el mar') return SEA_POOL

  const tours = day.expenses.filter(expense => expense.category === 'Tours')
  if (tours.length > 0) {
    const titles = tours.map(tour => tour.title.toLowerCase()).join(' ')
    if (titles.includes('pisa')) return PISA_POOL
    if (titles.includes('gratis') || titles.includes('a pie') || titles.includes('caminata')) return WALK_TOUR_POOL
    if (titles.includes('chocolate') || titles.includes('gastron') || titles.includes('comida') || titles.includes('food')) return FOOD_TOUR_POOL
  }

  const cityPool = CITY_TOUR_POOL[day.city]
  if (cityPool) return cityPool

  if (tours.length > 0) return GENERIC_TOUR_POOL
  if (day.expenses.some(expense => expense.category === 'Alojamiento')) return ARRIVAL_POOL
  return DEFAULT_POOL
}

/** Assigns the duck sticker shown on the tour/plan side of the "Qué
 * llevar" popup for every day at once (like assignDuckStickers), so a
 * multi-day stay in the same city or a run of similar days rotates
 * through a matching pool instead of repeating one fixed duck. Where
 * possible each pool actually matches what the day's plans are: flight,
 * cruise embarkation, the Jungfraujoch mountain train, a Pisa excursion, a
 * walking tour, a food-focused outing, or a city with its own landmark
 * duck (Paris/Eiffel Tower, Rome/Colosseum, Venice/gondola, Barcelona's
 * flamenco) — checked in that priority order, falling back to a generic
 * "touring" or "just arrived"/"exploring" pool only when nothing more
 * specific applies. */
export function assignTourDucks(days: GeneratedDay[]): string[] {
  let previousDuck: string | undefined
  return days.map(day => {
    const candidates = tourPool(day)
    const choice = candidates.find(candidate => candidate !== previousDuck) ?? candidates[0]
    previousDuck = choice
    return choice
  })
}
