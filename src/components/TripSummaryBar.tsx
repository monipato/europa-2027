import { formatCOP } from '../utils/currency'

interface TripSummaryBarProps {
  name: string
  peopleCount: number
  perPersonCop: number
  perPersonByType?: { label: string; amount: number }[]
}

/** The compact one-line bar showing the selected trip's name, headcount and
 * per-person price. It stays visible across both the day and category
 * views. `perPersonByType` — only set for options where adults/children
 * are priced differently (see "Orlando con..." in generate_data.py) —
 * shows the real per-fare-type price next to the blended headline instead
 * of hiding the difference. */
export function TripSummaryBar({ name, peopleCount, perPersonCop, perPersonByType }: TripSummaryBarProps) {
  return (
    <section className="trip-summary">
      <div className="summary-copy">
        <span>{name} · {peopleCount} personas</span>
        {perPersonByType && (
          <div className="summary-by-type">
            {perPersonByType.map((entry) => (
              <span key={entry.label}>{entry.label}: {formatCOP(entry.amount)}</span>
            ))}
          </div>
        )}
      </div>
      <div className="summary-cost">
        <strong>{formatCOP(perPersonCop)}</strong>
      </div>
    </section>
  )
}
