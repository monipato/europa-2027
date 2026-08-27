import type { GeneratedOption } from '../data/generated/itinerary.generated'
import { formatCOP } from '../utils/currency'
import { ExchangeRatesCard } from './ExchangeRatesCard'
import duckFamily from '../assets/ducks/duck-cat-family.png'

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
          <p className="eyebrow">Tu viaje, más fácil de entender</p>
          <h1>Elige tu forma de viajar</h1>
          <p className="intro">Compara las opciones y revisa cada gasto con calma. Todo está organizado para que encuentres lo que necesitas.</p>
        </div>
      </section>

      <section className="option-area">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Paso 1 de 2</p>
            <h2>Selecciona una cotización</h2>
          </div>
          <span className="people-badge"><img src={duckFamily} alt="" aria-hidden="true" /> 3 personas</span>
        </div>
        <div className="option-grid">
          {options.map((option, index) => (
            <button
              className={`option-card ${selectedOptionIndex === index ? 'active' : ''}`}
              key={option.name}
              onClick={() => onSelectOption(index)}
            >
              <span className="option-accent" style={{ background: option.color }} />
              <div className="option-top">
                <span className="radio">{selectedOptionIndex === index ? '✓' : ''}</span>
                <span className="days">{option.days} días</span>
              </div>
              <h3>{option.name}</h3>
              <p>{option.description}</p>
              <strong>{formatCOP(option.perPerson)}</strong>
              <small>{option.dates}</small>
              <div className="route">{option.route}</div>
            </button>
          ))}
        </div>
      </section>

      <ExchangeRatesCard
        className="rates-bottom"
        occupancyNote={<>Gastos por persona con alojamiento en habitación triple (3 personas). En habitación doble, el precio por persona cambia.</>}
      />
    </>
  )
}
