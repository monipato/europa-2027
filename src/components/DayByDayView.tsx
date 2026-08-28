import { useEffect, useMemo, useRef } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, ExternalLink, MapPin } from 'lucide-react'
import type { Category } from '../types'
import type { GeneratedDay } from '../data/generated/itinerary.generated'
import { CATEGORY_META } from '../constants'
import { formatCOP, formatExpenseAmount } from '../utils/currency'
import { getDayDisplayLabel } from '../utils/dayDisplay'
import { assignDuckStickers } from '../utils/duckStickers'

interface DayByDayViewProps {
  days: GeneratedDay[]
  selectedDayIndex: number
  onSelectDay: (index: number) => void
}

/** "Por día" view: a scrollable list of days on the left, and the selected
 * day's photo, title and full expense list on the right. */
export function DayByDayView({ days, selectedDayIndex, onSelectDay }: DayByDayViewProps) {
  const activeIndex = days[selectedDayIndex] ? selectedDayIndex : 0
  const activeDay = days[activeIndex]
  const activeDayLabel = getDayDisplayLabel(activeDay)
  const activeDayTotal = activeDay.expenses.reduce((sum, expense) => sum + expense.amount, 0)
  const dayDucks = useMemo(() => assignDuckStickers(days), [days])
  const activeDayDuck = dayDucks[activeIndex]

  const touchStartX = useRef<number | null>(null)
  const SWIPE_THRESHOLD = 40
  const selectedNavRef = useRef<HTMLButtonElement | null>(null)
  const dayListRef = useRef<HTMLElement | null>(null)
  const layoutRef = useRef<HTMLDivElement | null>(null)
  const isFirstRender = useRef(true)

  // Keep the selected day-nav button in view by scrolling only the day-list
  // strip itself (never window.scrollTo / scrollIntoView on ancestors) —
  // otherwise the browser can also drag the whole page's vertical scroll
  // along with it whenever the day-list isn't fully in view, which is what
  // made using the prev/next arrows feel like it randomly moved the page.
  // Instant (no smooth): an animated scroll here can race the day-list's
  // own CSS scroll-snap, which then nudges the final position by a couple
  // px once the animation settles — instant removes that timing window.
  useEffect(() => {
    const container = dayListRef.current
    const button = selectedNavRef.current
    if (!container || !button) return
    if (container.scrollWidth > container.clientWidth) {
      const target = button.offsetLeft - (container.clientWidth - button.clientWidth) / 2
      container.scrollTo({ left: target, behavior: 'auto' })
    }
    if (container.scrollHeight > container.clientHeight) {
      const target = button.offsetTop - (container.clientHeight - button.clientHeight) / 2
      container.scrollTo({ top: target, behavior: 'auto' })
    }
  }, [activeIndex])

  // Every time the selected day changes (arrows, swipe, or the list), snap
  // back to a stable landing spot: the day-nav row together with the hero
  // image just below it, instead of wherever the page happened to be
  // scrolled to (e.g. deep in the expense list). Anchored on the whole
  // day-list + day-detail section — not just the detail — so the nav row
  // stays visible with the hero, matching how this view is meant to be
  // read. Instant (no smooth) so it doesn't fight the day-list's own
  // smooth horizontal scroll above. Skipped on first mount so opening the
  // planner doesn't jump.
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    layoutRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' })
  }, [activeIndex])

  function handleTouchStart(event: React.TouchEvent) {
    touchStartX.current = event.touches[0].clientX
  }

  function handleTouchEnd(event: React.TouchEvent) {
    if (touchStartX.current === null) return
    const deltaX = event.changedTouches[0].clientX - touchStartX.current
    touchStartX.current = null
    if (Math.abs(deltaX) < SWIPE_THRESHOLD) return
    if (deltaX < 0 && activeIndex < days.length - 1) onSelectDay(activeIndex + 1)
    else if (deltaX > 0 && activeIndex > 0) onSelectDay(activeIndex - 1)
  }

  return (
    <div className="day-layout" ref={layoutRef}>
      <aside className="day-list" ref={dayListRef}>
        {days.map((day, index) => {
          const label = getDayDisplayLabel(day)
          return (
            <button
              className={`day-nav ${selectedDayIndex === index ? 'selected' : ''}`}
              key={day.dayKey}
              ref={selectedDayIndex === index ? selectedNavRef : undefined}
              onClick={() => onSelectDay(index)}
            >
              <span>{day.dayKey}</span>
              <div>
                <strong>{label.emoji} {day.city}</strong>
                <small>{label.label}</small>
              </div>
              <ChevronDown />
            </button>
          )
        })}
      </aside>

      <article className="day-detail">
        <div className="day-hero" onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
          <img src={activeDay.image} alt={`Paisaje de ${activeDay.city}`} />
          {activeIndex > 0 && (
            <button className="day-hero-nav prev" aria-label="Día anterior" onClick={() => onSelectDay(activeIndex - 1)}>
              <ChevronLeft />
            </button>
          )}
          {activeIndex < days.length - 1 && (
            <button className="day-hero-nav next" aria-label="Día siguiente" onClick={() => onSelectDay(activeIndex + 1)}>
              <ChevronRight />
            </button>
          )}
          <div className="day-hero-overlay">
            <span>{activeDayLabel.emoji} {activeDayLabel.label}</span>
            <h2>{activeDay.title}</h2>
            <p><MapPin size={15} /> {activeDay.city}</p>
          </div>
          {activeDayDuck && <img className="day-duck-sticker" src={activeDayDuck} alt="" aria-hidden="true" />}
        </div>

        <div className="expense-header">
          <div>
            <p className="eyebrow">{activeDay.dayKey} · gastos del día</p>
            <h3>¿En qué se va el dinero?</h3>
          </div>
          <strong>{formatCOP(activeDayTotal)}</strong>
        </div>

        <div className="expense-list">
          {activeDay.expenses.map((expense, index) => (
            <div className="expense-row" key={expense.title + index}>
              <span className="category-icon" style={{ background: CATEGORY_META[expense.category as Category].color }}>
                <img src={CATEGORY_META[expense.category as Category].duck} alt="" />
              </span>
              <div className="expense-info">
                <strong>{expense.title}</strong>
                <span>{expense.category}{expense.note && ` · ${expense.note}`}</span>
                {expense.link && (
                  <a href={expense.link} target="_blank" rel="noreferrer">
                    Ver tour o sitio web <ExternalLink size={14} />
                  </a>
                )}
              </div>
              <b>{formatExpenseAmount(expense)}</b>
            </div>
          ))}
        </div>
      </article>
    </div>
  )
}
