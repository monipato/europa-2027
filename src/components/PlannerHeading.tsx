import { CalendarDays, ChevronLeft, Wallet } from 'lucide-react'
import type { ViewMode } from '../types'
import { ExchangeRatesCard } from './ExchangeRatesCard'

interface PlannerHeadingProps {
  onBack: () => void
  view: ViewMode
  onChangeView: (view: ViewMode) => void
}

/** Shown at the top of the itinerary planner (once a trip option has been
 * picked): a way back to the selection screen and the "Por día"/"Por
 * categoría" switch share one compact row (the switch used to be its own
 * full-width row lower down — moved up here so it doesn't cost its own
 * block of vertical space), plus the exchange-rates card below. */
export function PlannerHeading({ onBack, view, onChangeView }: PlannerHeadingProps) {
  return (
    <div className="planner-heading">
      <div className="planner-top-row">
        <button className="planner-back" onClick={onBack}>
          <ChevronLeft size={18} /> Cambiar viaje
        </button>
        <div className="view-toggle" role="tablist">
          <button className={view === 'day' ? 'selected' : ''} onClick={() => onChangeView('day')} title="Ver por día">
            <CalendarDays size={15} /> Día
          </button>
          <button className={view === 'category' ? 'selected' : ''} onClick={() => onChangeView('category')} title="Ver por categoría">
            <Wallet size={15} /> Categoría
          </button>
        </div>
      </div>
      <ExchangeRatesCard
        occupancyNote={<>Todos los gastos detallados se muestran <b>por persona</b>, según la ocupación de este plan. El precio por persona cambia si se comparte una habitación distinta.</>}
      />
    </div>
  )
}
