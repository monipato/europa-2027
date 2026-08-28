import { useMemo } from 'react'
import { ExternalLink, X } from 'lucide-react'
import type { Category } from '../types'
import type { GeneratedDay } from '../data/generated/itinerary.generated'
import { CATEGORY_META } from '../constants'
import { formatCOP, formatExpenseAmount } from '../utils/currency'
import { collectExpensesByCategory, sumExpensesByCategory } from '../utils/tripStats'

interface CategoryBreakdownViewProps {
  days: GeneratedDay[]
  selectedCategory: Category | null
  onSelectCategory: (category: Category | null) => void
}

/** "Por rubro" view: one card per expense category with its total, and an
 * optional drill-down list (in a popup) of every expense in the selected
 * category. */
export function CategoryBreakdownView({ days, selectedCategory, onSelectCategory }: CategoryBreakdownViewProps) {
  const totalsByCategory = useMemo(() => sumExpensesByCategory(days), [days])
  const totalOfAllCategories = Object.values(totalsByCategory).reduce((sum, amount) => sum + amount, 0)
  const selectedCategoryExpenses = useMemo(
    () => (selectedCategory ? collectExpensesByCategory(days, selectedCategory) : []),
    [days, selectedCategory],
  )

  return (
    <div className="category-layout">
      <div className="category-grid">
        {Object.entries(totalsByCategory).map(([category, amount]) => {
          const meta = CATEGORY_META[category as Category]
          return (
            <button
              className={`category-card ${selectedCategory === category ? 'selected' : ''}`}
              key={category}
              onClick={() => onSelectCategory(category as Category)}
            >
              <div className="category-card-head">
                <span className="category-big-icon" style={{ background: meta.color }}>
                  <img src={meta.duck} alt="" />
                </span>
                <span className="category-name">{category}</span>
              </div>
              <strong>{formatCOP(amount)}</strong>
            </button>
          )
        })}
      </div>

      <div className="category-total">
        <div>
          <span>Total de gastos detallados</span>
          <strong>{formatCOP(totalOfAllCategories)}</strong>
        </div>
        <p>Los valores son estimados y pueden cambiar según la fecha de compra.</p>
      </div>

      {selectedCategory && (
        <>
          <div className="category-detail-backdrop" onClick={() => onSelectCategory(null)} />
          <div className="category-detail">
            <div className="detail-title">
              <div>
                <p className="eyebrow">Detalle del rubro</p>
                <h3>{CATEGORY_META[selectedCategory].icon} {selectedCategory}</h3>
              </div>
              <button onClick={() => onSelectCategory(null)} aria-label="Cerrar detalle">
                <X />
              </button>
            </div>
            {selectedCategoryExpenses.map((expense, index) => (
              <div className="mini-row" key={expense.title + index}>
                <span>{expense.dayKey} · {expense.place}</span>
                <strong>{expense.title}</strong>
                {expense.note && <p>{expense.note}</p>}
                <b>{formatExpenseAmount(expense)}</b>
                {expense.link && (
                  <a href={expense.link} target="_blank" rel="noreferrer">
                    Ver tour o sitio web <ExternalLink size={13} />
                  </a>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
