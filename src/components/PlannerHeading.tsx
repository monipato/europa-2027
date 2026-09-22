import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronLeft, Printer, Wallet } from 'lucide-react'
import type { ViewMode } from '../types'
import { ExchangeRatesCard } from './ExchangeRatesCard'

export type PrintMode = 'current' | 'all-days' | 'by-category'

interface PlannerHeadingProps {
  onBack: () => void
  view: ViewMode
  onChangeView: (view: ViewMode) => void
  onPrint: (mode: PrintMode) => void
}

/** Shown at the top of the itinerary planner (once a trip option has been
 * picked): a way back to the selection screen and the "Por día"/"Por
 * categoría" switch share one compact row (the switch used to be its own
 * full-width row lower down — moved up here so it doesn't cost its own
 * block of vertical space), plus the exchange-rates card below. */
export function PlannerHeading({ onBack, view, onChangeView, onPrint }: PlannerHeadingProps) {
  const [printMenuOpen, setPrintMenuOpen] = useState(false)
  const printMenuRef = useRef<HTMLDivElement | null>(null)

  // Close the print options menu on an outside click, same as any other
  // dropdown — otherwise it stays open until the print dialog itself opens.
  useEffect(() => {
    if (!printMenuOpen) return
    function handleClickOutside(event: MouseEvent) {
      if (printMenuRef.current && !printMenuRef.current.contains(event.target as Node)) {
        setPrintMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [printMenuOpen])

  function choosePrint(mode: PrintMode) {
    setPrintMenuOpen(false)
    onPrint(mode)
  }

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
        <div className="planner-print-wrap" ref={printMenuRef}>
          <button className="planner-print" onClick={() => setPrintMenuOpen((open) => !open)} title="Imprimir o guardar como PDF">
            <Printer size={15} /> <span>Imprimir</span>
          </button>
          {printMenuOpen && (
            <div className="planner-print-menu" role="menu">
              <button role="menuitem" onClick={() => choosePrint('current')}>
                Vista actual
                <small>{view === 'day' ? 'El día que estás viendo' : 'El rubro que estás viendo'}</small>
              </button>
              <button role="menuitem" onClick={() => choosePrint('all-days')}>
                Todos los días
                <small>Itinerario completo, día por día</small>
              </button>
              <button role="menuitem" onClick={() => choosePrint('by-category')}>
                Todo por rubro
                <small>Cada categoría con su detalle</small>
              </button>
            </div>
          )}
        </div>
      </div>
      <ExchangeRatesCard
        occupancyNote={<>Todos los gastos detallados se muestran <b>por persona</b>, según la ocupación de este plan. El precio por persona cambia si se comparte una habitación distinta.</>}
      />
    </div>
  )
}
