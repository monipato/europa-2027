import type { GeneratedDay } from '../data/generated/itinerary.generated'

/** A short, true-in-general descriptor for each city — the well-known
 * highlight a traveler associates with the place (a landmark, a vibe), not
 * a trip-specific fact. Used to write a one-line "why today is exciting"
 * note per day (see `assignDayMotivationNotes`) without inventing anything
 * about this particular itinerary. Cities without an entry fall back to a
 * generic phrase rather than a wrong or overly specific guess. */
const CITY_DESCRIPTOR: Record<string, string> = {
  'Barcelona': 'la ciudad de Gaudí y las playas del Mediterráneo',
  'Basilea': 'la ciudad donde se cruzan Suiza, Francia y Alemania',
  'Berlín': 'la ciudad de la historia, el arte y el Muro',
  'Colmar': 'el pueblo de cuento de Alsacia',
  'Diavolezza': 'los glaciares y picos nevados de los Alpes suizos',
  'La Spezia': 'la puerta de entrada a Cinque Terre',
  'Los Ángeles': 'la ciudad de las estrellas y Hollywood',
  'Milán': 'la capital de la moda y el Duomo',
  'Múnich': 'la capital bávara',
  'Orlando': 'la magia de Disney y Universal',
  'Osaka': 'la mejor cocina callejera de Japón',
  'París': 'la ciudad del amor y la Torre Eiffel',
  'Praga': 'la ciudad de las cien torres',
  'Roma': 'la ciudad eterna y el Coliseo',
  'Salerno': 'la puerta a la Costa Amalfitana',
  'Tokio': 'el corazón vibrante de Japón',
  'Venecia': 'la ciudad de los canales y las góndolas',
  'Zadar': 'la joya del Adriático croata',
}
const DEFAULT_DESCRIPTOR = 'un lugar increíble para descubrir'

function descriptorFor(city: string): string {
  return CITY_DESCRIPTOR[city] ?? DEFAULT_DESCRIPTOR
}

// Several ways to say each situation, in preference order — every pool has
// at least 3 entries and `assignDayMotivationNotes` greedily skips the
// previous day's exact pick, so a multi-day city stay or a run of similar
// days (Múnich's 5 nights, a week of "day 2 of 3 in Praga") doesn't repeat
// the same opener every time. Same rotation idea as duckStickers.ts's duck
// pools, applied to copy instead of images.
const ARRIVAL = (city: string, d: string) => [
  `¡Llegamos a ${city}! Bienvenidos a ${d}.`,
  `${city} nos recibe hoy — ${d}, a la vuelta de la esquina.`,
  `Hoy toca conocer ${city}: ${d}.`,
  `Nueva ciudad, nueva aventura — bienvenidos a ${d}.`,
]
const FLIGHT_ARRIVAL = (city: string, d: string) => [
  `¡Bienvenidos a ${city}! Llegamos a ${d} — hora de instalarse y descansar.`,
  `Después de volar, aterrizamos en ${d}. ¡Bienvenidos a ${city}!`,
  `El viaje empieza en serio: ${city} y ${d} nos esperan.`,
]
const CONTINUE = (city: string, d: string) => [
  `Un día más para disfrutar de ${city}, ${d}.`,
  `Hoy seguimos explorando ${city} — no te pierdas ${d}.`,
  `${city} todavía tiene mucho que mostrar: ${d}.`,
  `Otro día para enamorarte de ${d}.`,
]
const DEPARTURE = (city: string, _d: string) => [
  `Último día en ${city} — aprovecha antes de seguir camino.`,
  `Nos despedimos de ${city}... por ahora. Disfruta cada minuto que queda.`,
  `Se acerca la siguiente parada, pero primero: un último vistazo a ${city}.`,
]
const EMBARK = () => [
  '¡Hoy zarpamos! Que comience la aventura en altamar.',
  'Motores listos — el crucero empieza hoy.',
  '¡Todos a bordo! El mar nos espera.',
]
const SEA = () => [
  'Día de descanso en altamar — disfruta del crucero sin prisa.',
  'Hoy no hay prisa: solo mar, sol y tiempo para ti.',
  'Un día flotando entre destinos — aprovecha cada rincón del barco.',
]
const TRANSIT = () => [
  'Día de vuelo — pronto aterrizamos en nuestro próximo destino.',
  'Rumbo al siguiente destino, cruzando el cielo.',
  'Hoy el avión es la casa — ya casi llegamos.',
]
const TRIP_END = (city: string) => [
  `Último día de viaje — hora de hacer las maletas y llevarte los mejores recuerdos de ${city}.`,
  `Se acaba la aventura... por ahora. Gracias por viajar con nosotros.`,
  `El viaje termina hoy en ${city} — disfruta cada último momento.`,
]

/** One motivating, "why today is exciting" line per day, computed for the
 * whole itinerary at once so it can tell an arrival apart from a day still
 * settled into the same city or the day before moving on. Rotation is
 * tracked per *situation* (arrival, mid-stay, departure...) across the
 * whole trip — not just "don't repeat yesterday" — so a 25-day trip with
 * an arrival almost every day doesn't say "¡Llegamos a...!" every single
 * time just because each arrival is a different city; the 2nd, 3rd, 4th
 * arrival in the trip each get a different opener. Deliberately
 * generic-but-true copy (a city's well-known highlight, plus where today
 * falls in the stay) rather than anything pulled from the day's own priced
 * items — those read as logistics trivia (a hotel rating, an Uber
 * estimate), not something that makes a traveler excited to open the app. */
export function assignDayMotivationNotes(days: GeneratedDay[]): string[] {
  const situationCounts: Record<string, number> = {}
  function pick(situation: string, pool: string[]): string {
    const count = situationCounts[situation] ?? 0
    situationCounts[situation] = count + 1
    return pool[count % pool.length]
  }

  return days.map((day, index) => {
    const isTripLastDay = index === days.length - 1
    const isArrivalDay = index === 0 || days[index - 1].city !== day.city
    const isDepartureDay = !isTripLastDay && days[index + 1].city !== day.city
    const descriptor = descriptorFor(day.city)

    // A flight day whose next day shares its city hasn't landed yet — the
    // flight departs today and arrives tomorrow (see crucero-en-pareja's and
    // europa's "06 MAY" departure day, both labeled with the destination
    // city for display purposes even though nobody's there yet). That next
    // day is the real arrival, even though `isArrivalDay` reads false for it
    // (same city as the flight day right before it).
    const isSameDayFlightArrival = day.dayKind === 'flight' && (isTripLastDay || days[index + 1].city !== day.city)
    const arrivesFromFlightYesterday = index > 0 && days[index - 1].dayKind === 'flight' && days[index - 1].city === day.city

    if (isTripLastDay) return pick('tripEnd', TRIP_END(day.city))
    if (day.dayKind === 'embark') return pick('embark', EMBARK())
    if (day.city === 'En el mar') return pick('sea', SEA())
    if (day.city === 'En vuelo') return pick('transit', TRANSIT())
    if (day.dayKind === 'flight' && !isSameDayFlightArrival) return pick('transit', TRANSIT())
    if ((day.dayKind === 'flight' && isSameDayFlightArrival) || arrivesFromFlightYesterday) {
      return pick('flightArrival', FLIGHT_ARRIVAL(day.city, descriptor))
    }
    if (isArrivalDay) return pick('arrival', ARRIVAL(day.city, descriptor))
    if (isDepartureDay) return pick('departure', DEPARTURE(day.city, descriptor))
    return pick('continue', CONTINUE(day.city, descriptor))
  })
}
