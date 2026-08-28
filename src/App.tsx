import { useEffect, useState } from 'react'
import { CalendarDays, Wallet } from 'lucide-react'
import { generatedOptions } from './data/generated/itinerary.generated'
import type { Category, ViewMode } from './types'
import { useTheme } from './hooks/useTheme'
import { AppHeader } from './components/AppHeader'
import { AppFooter } from './components/AppFooter'
import { PlannerHeading } from './components/PlannerHeading'
import { TripSelectionScreen } from './components/TripSelectionScreen'
import { TripSummaryBar } from './components/TripSummaryBar'
import { DayByDayView } from './components/DayByDayView'
import { CategoryBreakdownView } from './components/CategoryBreakdownView'

/**
 * Top-level component. Owns all UI state and wires the presentational
 * components together; it holds no formatting or data-shaping logic of its
 * own — that lives in `utils/` and the generated data itself.
 */
export function App() {
  const [selectedOptionIndex, setSelectedOptionIndex] = useState<number | null>(null)
  const [hasStartedPlanning, setHasStartedPlanning] = useState(false)
  const [view, setView] = useState<ViewMode>('day')
  const [selectedDayIndex, setSelectedDayIndex] = useState(0)
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const { theme, toggleTheme } = useTheme()

  const selectedOption = generatedOptions[selectedOptionIndex ?? 0]
  const days = selectedOption.itinerary

  // Switching trip options resets the day/category the previous one had
  // selected — the new option has a different number of days and, since
  // "Otros"/"Seguro" costs can be zero on some options, possibly different
  // categories.
  useEffect(() => {
    setSelectedDayIndex(0)
    setSelectedCategory(null)
  }, [selectedOptionIndex])

  // Clicking "Por día" always lands the scroll on the day-nav row (.day-layout),
  // even if that tab was already selected — e.g. after scrolling deep into the
  // expense list. A counter (not `view` itself) is the effect's dependency so a
  // no-op click (already on "day") still re-triggers it, which a `view`-keyed
  // effect wouldn't catch since the value wouldn't actually change. Switching
  // *from* "Por rubro" also lands here: DayByDayView is a different component
  // than CategoryBreakdownView, so it remounts fresh and its own "skip scroll on
  // first render" guard would otherwise swallow this. Not fired on the initial
  // mount right after picking a trip — handleSelectOption's window.scrollTo(0, 0)
  // is the last word there, since dayTabClickCount starts at 0.
  const [dayTabClickCount, setDayTabClickCount] = useState(0)
  useEffect(() => {
    if (dayTabClickCount === 0) return
    document.querySelector('.day-layout')?.scrollIntoView({ behavior: 'auto', block: 'start' })
  }, [dayTabClickCount])

  function handleSelectOption(index: number) {
    setSelectedOptionIndex(index)
    setHasStartedPlanning(true)
    window.scrollTo(0, 0)
  }

  function handleChangeTrip() {
    setHasStartedPlanning(false)
    setSelectedCategory(null)
  }

  function handleChangeView(nextView: ViewMode) {
    setView(nextView)
    if (nextView === 'day') {
      setSelectedCategory(null)
      setDayTabClickCount(count => count + 1)
    }
  }

  return (
    <div className={`app-shell ${hasStartedPlanning ? 'planner-open' : 'selection-screen'}`}>
      <AppHeader
        menuOpen={menuOpen}
        onToggleMenu={() => setMenuOpen(!menuOpen)}
        onCloseMenu={() => setMenuOpen(false)}
        theme={theme}
        onToggleTheme={toggleTheme}
        onGoHome={handleChangeTrip}
      />

      <main>
        {hasStartedPlanning && <PlannerHeading onBack={handleChangeTrip} />}

        {!hasStartedPlanning && (
          <TripSelectionScreen
            options={generatedOptions}
            selectedOptionIndex={selectedOptionIndex}
            onSelectOption={handleSelectOption}
          />
        )}

        {/* Always rendered (even on the selection screen, where CSS hides it) so the
            CSS flex `order` rules that lay out the planner keep a stable DOM to work with. */}
        <TripSummaryBar route={selectedOption.route} perPersonCop={selectedOption.perPerson} />

        <section id="itinerario" className="content-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Paso 2 de 2</p>
              <h2>¿Cómo quieres verlo?</h2>
            </div>
            <span className="hint">Toca una tarjeta para ver el detalle</span>
          </div>

          <div className="view-toggle" role="tablist">
            <button className={view === 'day' ? 'selected' : ''} onClick={() => handleChangeView('day')}>
              <CalendarDays /> Por día
            </button>
            <button className={view === 'category' ? 'selected' : ''} onClick={() => handleChangeView('category')}>
              <Wallet /> Por rubro
            </button>
          </div>

          {view === 'day' ? (
            <DayByDayView days={days} selectedDayIndex={selectedDayIndex} onSelectDay={setSelectedDayIndex} />
          ) : (
            <CategoryBreakdownView days={days} selectedCategory={selectedCategory} onSelectCategory={setSelectedCategory} />
          )}
        </section>
      </main>

      <AppFooter />
    </div>
  )
}
