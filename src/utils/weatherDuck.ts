import duckRainUmbrella from '../assets/ducks/duck3-rain-city-umbrella.webp'
import duckRainWalk from '../assets/ducks/duck3-rain-walk-green.webp'
import duckRainBackpack from '../assets/ducks/duck3-rain-backpack.webp'
import duckColdArctic from '../assets/ducks/duck3-arctic-explorer.webp'
import duckColdWinter from '../assets/ducks/duck2-winter-3.webp'
import duckColdSnowHiking from '../assets/ducks/duck3-snow-hiking.webp'
import duckSnowSki from '../assets/ducks/duck3-ski.webp'
import duckSnowboard from '../assets/ducks/duck3-snowboard.webp'
import duckSnowman from '../assets/ducks/duck3-snowman-couple.webp'
import duckFogOnsen from '../assets/ducks/duck2-onsen.webp'
import duckFogHotSpring from '../assets/ducks/duck3-hot-spring.webp'
import duckSunBeach from '../assets/ducks/duck3-beach-lounger.webp'
import duckSunPalm from '../assets/ducks/duck3-palm-coconut.webp'
import duckSunSunset from '../assets/ducks/duck2-sunset-beach.webp'
import duckCloudyCompass from '../assets/ducks/duck-compass.webp'
import duckCloudyMap from '../assets/ducks/duck2-map.webp'
import duckCloudySelfie from '../assets/ducks/duck2-selfie.webp'
import duckCloudyBirdwatching from '../assets/ducks/duck3-birdwatching.webp'
import type { GeneratedDay } from '../data/generated/itinerary.generated'

const TEMP_RANGE_RE = /(-?\d+)\D+(-?\d+)/

function parseLowTemp(temp: string): number | null {
  const match = TEMP_RANGE_RE.exec(temp)
  return match ? parseInt(match[1], 10) : null
}

// Candidate ducks per weather bucket, in preference order — every pool has
// at least 2 entries (assignWeatherDucks greedily skips the previous day's
// exact pick, same rule as assignDuckStickers) so a long run of the same
// weather condition (this itinerary is mostly "Nublado") still rotates
// instead of showing one fixed duck on every single card. None of these
// overlap with duckStickers.ts's hero-photo pools or any other duck used
// elsewhere in the app — see the reserved-set comment in tourDuck.ts.
const RAIN_POOL = [duckRainUmbrella, duckRainWalk, duckRainBackpack]
const COLD_POOL = [duckColdArctic, duckColdWinter, duckColdSnowHiking]
const SNOW_POOL = [duckSnowSki, duckSnowboard, duckSnowman]
const FOG_POOL = [duckFogOnsen, duckFogHotSpring]
const SUN_POOL = [duckSunBeach, duckSunPalm, duckSunSunset]
const CLOUDY_POOL = [duckCloudyCompass, duckCloudyMap, duckCloudySelfie, duckCloudyBirdwatching]

function weatherPool(weather: string, temp: string): string[] {
  const label = weather.toLowerCase()
  if (label.includes('nieve')) return SNOW_POOL
  const lowTemp = parseLowTemp(temp)
  // A freezing low wins over the label even on a day merely described as
  // "Parcialmente nublado" (e.g. the Jungfraujoch's -11–-5°C) — the label
  // alone would otherwise show the same neutral duck as any other cloudy day.
  if (lowTemp !== null && lowTemp < 5) return COLD_POOL
  // "lluv" catches "Lluvia", "llov" catches "Llovizna" — not the same substring.
  if (label.includes('lluv') || label.includes('llov') || label.includes('chubasco') || label.includes('tormenta')) return RAIN_POOL
  if (label.includes('nebl')) return FOG_POOL
  if (label.includes('sole')) return SUN_POOL
  return CLOUDY_POOL
}

/** Assigns the duck sticker shown on the weather side of the "Qué llevar"
 * popup for every day at once (like assignDuckStickers), so a run of
 * consecutive days with the same weather condition rotates through that
 * condition's pool instead of repeating one fixed duck. Weather/temp are
 * the same fields scripts/update_climate.py refreshes, so the assignment
 * updates automatically whenever the climate skill runs and regenerates —
 * no extra wiring needed. */
export function assignWeatherDucks(days: GeneratedDay[]): string[] {
  let previousDuck: string | undefined
  return days.map(day => {
    const candidates = weatherPool(day.weather, day.temp)
    const choice = candidates.find(candidate => candidate !== previousDuck) ?? candidates[0]
    previousDuck = choice
    return choice
  })
}
