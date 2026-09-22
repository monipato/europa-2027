import type { Category } from '../types'
import type { GeneratedOption } from '../data/generated/itinerary.generated'
import { formatCOP, formatExpenseAmount } from '../utils/currency'
import { collectExpensesByCategory, sumExpensesByCategory } from '../utils/tripStats'
import { getDayDisplayLabel } from '../utils/dayDisplay'

interface PrintViewProps {
  mode: 'all-days' | 'by-category'
  option: GeneratedOption
}

/**
 * Off-screen printable listing — only ever mounted while App's `printMode`
 * is set (see App.tsx's `handlePrint`) and only ever visible under
 * `@media print` (styles.css's `.print-all-days`/`.print-by-category`
 * rules). The normal on-screen day/category views stay mounted underneath,
 * unaffected; this is a separate flat rendering built to lay out well on
 * paper — every day (or every category) back to back, rather than the
 * single-selection view the live UI shows.
 */
export function PrintView({ mode, option }: PrintViewProps) {
  const days = option.itinerary

  return (
    <div className="print-view">
      <header className="print-view-header">
        <h1>{option.name}</h1>
        <p>
          {option.dates} · {option.peopleCount} persona{option.peopleCount === 1 ? '' : 's'} ·{' '}
          {formatCOP(option.perPerson)} por persona
        </p>
      </header>

      {mode === 'all-days' && (
        <>
          {days.map((day) => {
            const label = getDayDisplayLabel(day)
            const dayTotal = day.expenses.reduce((sum, expense) => sum + expense.amount, 0)
            return (
              <section className="print-block" key={day.dayKey}>
                <h2>
                  {day.dayKey} · {label.emoji} {day.city} — {day.title}
                </h2>
                <p className="print-block-meta">
                  {label.label && `${label.label} · `}🌅 {day.sunrise} · 🌇 {day.sunset} · {day.weatherIcon} {day.temp}
                </p>
                <table>
                  <tbody>
                    {day.expenses.map((expense, index) => (
                      <tr key={expense.title + index}>
                        <td>{expense.category}</td>
                        <td>
                          {expense.time && <span className="print-time">🕐 {expense.time}</span>}
                          {expense.title}
                          {expense.note && ` · ${expense.note}`}
                        </td>
                        <td>{formatExpenseAmount(expense)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="print-block-total">Total del día: {formatCOP(dayTotal)}</p>
              </section>
            )
          })}
          <p className="print-view-grand-total">
            Total del viaje: {formatCOP(days.flatMap((day) => day.expenses).reduce((sum, expense) => sum + expense.amount, 0))}
          </p>
        </>
      )}

      {mode === 'by-category' && (
        <>
          {Object.entries(sumExpensesByCategory(days)).map(([category, total]) => (
            <section className="print-block" key={category}>
              <h2>
                {category} — {formatCOP(total ?? 0)}
              </h2>
              <table>
                <tbody>
                  {collectExpensesByCategory(days, category as Category).map((expense, index) => (
                    <tr key={expense.title + index}>
                      <td>
                        {expense.dayKey} · {expense.place}
                      </td>
                      <td>
                        {expense.time && <span className="print-time">🕐 {expense.time}</span>}
                        {expense.title}
                        {expense.note && ` · ${expense.note}`}
                      </td>
                      <td>{formatExpenseAmount(expense)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
          <p className="print-view-grand-total">
            Total de todos los rubros: {formatCOP(Object.values(sumExpensesByCategory(days)).reduce((sum, amount) => sum + (amount ?? 0), 0))}
          </p>
        </>
      )}
    </div>
  )
}
