import { ChevronLeft } from 'lucide-react'
import { ExchangeRatesCard } from './ExchangeRatesCard'

interface PlannerHeadingProps {
  onBack: () => void
}

/** Shown at the top of the itinerary planner (once a trip option has been
 * picked): a way back to the selection screen, plus the exchange-rates card. */
export function PlannerHeading({ onBack }: PlannerHeadingProps) {
  return (
    <div className="planner-heading">
      <button className="planner-back" onClick={onBack}>
        <ChevronLeft size={18} /> Cambiar viaje
      </button>
      <p className="eyebrow">Tu itinerario seleccionado</p>
      <ExchangeRatesCard
        occupancyNote={<>Todos los gastos detallados se muestran <b>por persona</b>, según la ocupación de este plan. El precio por persona cambia si se comparte una habitación distinta.</>}
      />
    </div>
  )
}
