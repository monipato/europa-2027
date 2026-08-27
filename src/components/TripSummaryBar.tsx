import { formatCOP } from '../utils/currency'

interface TripSummaryBarProps {
  route: string
  perPersonCop: number
}

/** The dark bar showing the selected trip's route and per-person price. It
 * stays visible across both the day and category views. */
export function TripSummaryBar({ route, perPersonCop }: TripSummaryBarProps) {
  return (
    <section className="trip-summary">
      <div className="summary-copy">
        <span>{route}</span>
      </div>
      <div className="summary-cost">
        <strong>{formatCOP(perPersonCop)}</strong>
      </div>
    </section>
  )
}
