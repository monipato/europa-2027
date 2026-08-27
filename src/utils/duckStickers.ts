import duckAirplaneWindow from '../assets/ducks/duck-airplane-window.png'
import duckCruise from '../assets/ducks/duck-cruise.png'
import duckGondola from '../assets/ducks/duck-gondola.png'
import duckPisa from '../assets/ducks/duck-pisa.png'
import duckParis from '../assets/ducks/duck-paris.png'
import duckSki from '../assets/ducks/duck-ski.png'
import duckHiking from '../assets/ducks/duck-hiking.png'
import duckKayak from '../assets/ducks/duck-kayak.png'
import duckBeach from '../assets/ducks/duck-beach.png'
import duckSurf from '../assets/ducks/duck-surf.png'
import duckCity from '../assets/ducks/duck-city.png'
import duckMapSit from '../assets/ducks/duck-map-sit.png'
import duckWaterfall from '../assets/ducks/duck-waterfall.png'
import duckSailboat from '../assets/ducks/duck-sailboat.png'
import duckSnorkel from '../assets/ducks/duck-snorkel.png'
import duckBike from '../assets/ducks/duck-bike.png'
import duckPhotographer from '../assets/ducks/duck-photographer.png'
import type { GeneratedDay } from '../data/generated/itinerary.generated'

/** Candidate duck stickers per city, in preference order. Every pool here
 * must have at least 2 distinct entries — assignDuckStickers greedily picks
 * "first candidate that isn't the previous day's duck", which is only
 * guaranteed to succeed (avoiding consecutive-day repeats, even across a
 * city boundary) when there's always an alternative to fall back to. Cities
 * with no clear match (Praga, Múnich, ...) are left out on purpose — better
 * no sticker than a forced, meaningless one. */
const DUCK_POOL_BY_CITY: Record<string, string[]> = {
  'París': [duckParis, duckCity, duckPhotographer],
  'Venecia': [duckGondola, duckSailboat],
  'La Spezia': [duckPisa, duckHiking],
  'Zúrich': [duckSki, duckHiking, duckKayak],
  'Barcelona': [duckBeach, duckSurf, duckCity],
  'Roma': [duckPhotographer, duckCity, duckMapSit],
  'Berlín': [duckBike, duckCity],
  'Salerno': [duckWaterfall, duckHiking],
  'Zadar': [duckSailboat, duckSnorkel],
  'En el mar': [duckSailboat, duckSnorkel],
}

/**
 * Picks a small "traveling duck" sticker (checked-in static crops under
 * src/assets/ducks/) for each day's hero photo, when one clearly fits. The
 * flight and embarkation days always get their own duck; everything else
 * comes from that city's candidate pool, walked in order so a multi-day
 * stay never shows the same duck on two days in a row.
 */
export function assignDuckStickers(days: GeneratedDay[]): Array<string | undefined> {
  let previousDuck: string | undefined
  return days.map(day => {
    let candidates: string[] | undefined
    if (day.dayKind === 'flight') candidates = [duckAirplaneWindow]
    else if (day.dayKind === 'embark') candidates = [duckCruise]
    else candidates = DUCK_POOL_BY_CITY[day.city]

    if (!candidates || candidates.length === 0) {
      previousDuck = undefined
      return undefined
    }
    const choice = candidates.find(candidate => candidate !== previousDuck) ?? candidates[0]
    previousDuck = choice
    return choice
  })
}
