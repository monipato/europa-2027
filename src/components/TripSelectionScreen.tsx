import type { GeneratedOption } from '../data/generated/itinerary.generated'
import { formatCOP } from '../utils/currency'
import { collectCountryFlagsWithNames } from '../utils/tripStats'
import { ExchangeRatesCard } from './ExchangeRatesCard'
import duckFamily2 from '../assets/ducks/duck2-family-car.png'
import duckFamily3 from '../assets/ducks/duck2-family-3.png'
import duckFamily4 from '../assets/ducks/duck2-family-4.png'

// Small duck icon next to the "N personas" badge on each option card — picked
// to roughly match the actual traveler count, falling back to the 3-duck one
// (the common case) for any other count.
const PEOPLE_DUCK_BY_COUNT: Record<number, string> = { 2: duckFamily2, 3: duckFamily3, 4: duckFamily4 }

interface TripSelectionScreenProps {
  options: GeneratedOption[]
  selectedOptionIndex: number | null
  onSelectOption: (index: number) => void
}

/** The landing screen: pick one of the four trip options. Selecting a card
 * takes the user straight into the itinerary planner — there is no separate
 * "confirm" step. */
export function TripSelectionScreen({ options, selectedOptionIndex, onSelectOption }: TripSelectionScreenProps) {
  return (
    <>
      <section className="welcome">
        <div className="welcome-copy">
          <p className="eyebrow">Tu pasaporte de viajes</p>
          <h1>Elige tu próximo <span className="accent-word">sello</span> de viaje</h1>
          <p className="intro">Cada viaje trae su propia postal y su sello. Toca "Ver detalle" para abrir el itinerario completo.</p>
        </div>
      </section>

      <section className="option-area">
        <div className="option-grid">
          {options.map((option, index) => (
            <button
              className={`option-card ${selectedOptionIndex === index ? 'active' : ''}`}
              key={option.name}
              onClick={() => onSelectOption(index)}
            >
              <span className="option-card-stripe" aria-hidden="true" />
              <div className="option-photo">
                <img src={option.itinerary[0]?.image} alt="" />
                <span className="option-people-badge">
                  <img src={PEOPLE_DUCK_BY_COUNT[option.peopleCount] ?? duckFamily3} alt="" aria-hidden="true" /> {option.peopleCount} personas
                </span>
                <span className="option-stamp stamp-label" aria-hidden="true">
                  <span className="option-stamp-ring" />
                  <strong>{option.days}</strong>
                  <small>días</small>
                </span>
              </div>
              <div className="option-body">
                <h3>{option.name}</h3>
                <div className="option-flags">
                  {collectCountryFlagsWithNames(option.itinerary).map(({ emoji, country }) => (
                    <span key={country}>{emoji} {country}</span>
                  ))}
                </div>
                <p>{option.description}</p>
                <div className="option-price-row">
                  <div>
                    <span className="option-price-label stamp-label">por persona</span>
                    <strong>{formatCOP(option.perPerson)}</strong>
                  </div>
                  <span className="option-cta">Ver detalle →</span>
                </div>
                {option.perPersonByType && (
                  <div className="option-by-type">
                    {option.perPersonByType.map((entry) => (
                      <span key={entry.label}>{entry.label}: {formatCOP(entry.amount)}</span>
                    ))}
                  </div>
                )}
                <small>{option.dates}</small>
                <div className="route">{option.route}</div>
              </div>
            </button>
          ))}
        </div>
      </section>

      <ExchangeRatesCard
        className="rates-bottom"
        occupancyNote={<>Gastos mostrados <b>por persona</b>, según la ocupación de cada plan. El precio por persona cambia si se comparte una habitación distinta.</>}
      />
    </>
  )
}
