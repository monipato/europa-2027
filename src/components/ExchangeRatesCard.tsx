import type { ReactNode } from 'react'
import { exchangeRates, ratesUpdatedAt } from '../data/generated/itinerary.generated'

interface ExchangeRatesCardProps {
  /** Extra class, e.g. to tweak spacing when shown at the bottom of the trip-selection screen. */
  className?: string
  /** The occupancy disclaimer shown under the rates — copy differs slightly between
   * where this card appears, so the caller supplies it rather than the card guessing. */
  occupancyNote: ReactNode
}

/** Reference exchange rates card, shown both on the trip-selection screen and
 * in the itinerary planner header. Rates come from `data/rates.json` — they
 * are informational only and are not used to convert any displayed amount. */
export function ExchangeRatesCard({ className, occupancyNote }: ExchangeRatesCardProps) {
  return (
    <details className={className ? `rates-card ${className}` : 'rates-card'}>
      {/* "Ver " and the "· fecha" bit only make sense as a clickable
          on-screen toggle — print forces this card open regardless (see
          styles.css's `@media print`), so both are hidden there, leaving
          just "tasas de cambio" as a plain heading over the values. */}
      <summary>
        <span className="rates-card-verb">Ver </span>
        tasas de cambio
        <span className="rates-card-updated"> · {ratesUpdatedAt}</span>
      </summary>
      <div className="rates-card-body">
        <div>
          {exchangeRates.map(rate => (
            <a key={rate.code} href={rate.sourceUrl} target="_blank" rel="noreferrer" title="Ver fuente de esta tasa">
              <b>{rate.code}</b> {rate.symbol} 1 = {new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(rate.rate)} COP
            </a>
          ))}
        </div>
        <p className="occupancy-note">👤 {occupancyNote}</p>
      </div>
    </details>
  )
}
