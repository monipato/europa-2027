import { useEffect, useState } from 'react'
import { generatedOptions } from './data/generated/itinerary.generated'
import type { Category, ViewMode } from './types'
import { useTheme } from './hooks/useTheme'
import { AppHeader } from './components/AppHeader'
import { PlannerHeading, type PrintMode } from './components/PlannerHeading'
import { TripSelectionScreen } from './components/TripSelectionScreen'
import { TripSummaryBar } from './components/TripSummaryBar'
import { DayByDayView } from './components/DayByDayView'
import { CategoryBreakdownView } from './components/CategoryBreakdownView'
import { PrintView } from './components/PrintView'
import { ChatWidget } from './components/ChatWidget'
import { buildContextualMessage } from './utils/chatContext'

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
  const [fullPrintMode, setFullPrintMode] = useState<'all-days' | 'by-category' | null>(null)
  const { theme, toggleTheme } = useTheme()

  const selectedOption = generatedOptions[selectedOptionIndex ?? 0]
  const days = selectedOption.itinerary

  const chatContextMessage = buildContextualMessage({
    hasStartedPlanning,
    option: selectedOption,
    view,
    selectedDay: hasStartedPlanning ? (days[selectedDayIndex] ?? null) : null,
    selectedCategory,
  })

  // Switching trip options resets the day/category the previous one had
  // selected — the new option has a different number of days and, since
  // "Otros"/"Seguro" costs can be zero on some options, possibly different
  // categories.
  useEffect(() => {
    setSelectedDayIndex(0)
    setSelectedCategory(null)
  }, [selectedOptionIndex])

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
    }
  }

  // The browser's print/"save as PDF" dialog suggests `document.title` as
  // the file name — left at the page's own generic <title> (set once in
  // index.html), every export would be named after the site instead of the
  // trip. Swaps it to the selected option's own name for the duration of
  // the print job and restores it on `afterprint` (fires whether the user
  // actually printed or hit cancel).
  function printAsOption() {
    const previousTitle = document.title
    document.title = selectedOption.name
    function restoreTitle() {
      document.title = previousTitle
      window.removeEventListener('afterprint', restoreTitle)
    }
    window.addEventListener('afterprint', restoreTitle)
    window.print()
  }

  // "Vista actual" just prints whatever's on screen (styles.css's plain
  // `@media print` block already strips the app chrome from it). "Todos los
  // días"/"Todo por rubro" instead render <PrintView> — a full listing that
  // isn't otherwise in the DOM — then print once it's mounted; `afterprint`
  // fires whether the user actually printed or hit cancel, so it's the
  // right moment to unmount it again either way.
  function handlePrint(mode: PrintMode) {
    if (mode === 'current') {
      printAsOption()
      return
    }
    setFullPrintMode(mode)
  }

  useEffect(() => {
    if (!fullPrintMode) return
    const raf = requestAnimationFrame(() => printAsOption())
    function handleAfterPrint() {
      setFullPrintMode(null)
    }
    window.addEventListener('afterprint', handleAfterPrint)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('afterprint', handleAfterPrint)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullPrintMode])

  return (
    <div
      className={`app-shell ${hasStartedPlanning ? 'planner-open' : 'selection-screen'} ${
        fullPrintMode ? `print-${fullPrintMode}` : ''
      }`}
    >
      <AppHeader theme={theme} onToggleTheme={toggleTheme} onGoHome={handleChangeTrip} />

      <main>
        {hasStartedPlanning && (
          <PlannerHeading onBack={handleChangeTrip} view={view} onChangeView={handleChangeView} onPrint={handlePrint} />
        )}

        {!hasStartedPlanning && (
          <TripSelectionScreen
            options={generatedOptions}
            selectedOptionIndex={selectedOptionIndex}
            onSelectOption={handleSelectOption}
          />
        )}

        {/* Always rendered (even on the selection screen, where CSS hides it) so the
            CSS flex `order` rules that lay out the planner keep a stable DOM to work with. */}
        <TripSummaryBar name={selectedOption.name} peopleCount={selectedOption.peopleCount} perPersonCop={selectedOption.perPerson} perPersonByType={selectedOption.perPersonByType} />

        <section className="content-section">
          {view === 'day' ? (
            <DayByDayView days={days} selectedDayIndex={selectedDayIndex} onSelectDay={setSelectedDayIndex} />
          ) : (
            <CategoryBreakdownView days={days} selectedCategory={selectedCategory} onSelectCategory={setSelectedCategory} />
          )}
        </section>

        {fullPrintMode && <PrintView mode={fullPrintMode} option={selectedOption} />}
      </main>

      <ChatWidget contextMessage={chatContextMessage} />
    </div>
  )
}
