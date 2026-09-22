import type { Theme } from '../hooks/useTheme'
import { ThemeToggle } from './ThemeToggle'
import patitoursIcon from '../assets/brand/patitours-icon.webp'
import patitoursIconDark from '../assets/brand/patitours-icon-dark.webp'
import patitoursWordmark from '../assets/brand/patitours-wordmark.webp'
import patitoursWordmarkDark from '../assets/brand/patitours-wordmark-dark.webp'

interface AppHeaderProps {
  theme: Theme
  onToggleTheme: () => void
  onGoHome: () => void
}

/**
 * Top bar: the PatiTours logo and the light/dark toggle. Clicking the logo
 * returns to the trip-selection screen, like a normal site home link.
 * There used to also be "Itinerario"/"Resumen de gastos" nav links here
 * once a trip was picked, but they only duplicated the "Por día"/"Por
 * categoría" tabs already inside the planner — removed rather than kept
 * as a second way to do the same thing.
 */
export function AppHeader({ theme, onToggleTheme, onGoHome }: AppHeaderProps) {
  return (
    <header className="topbar">
      {/* The header bar is always a dark navy/espresso surface (light and dark
          theme alike — see .topbar in styles.css), so on screen the logo
          always wears its dark-background (cream-ink) variant regardless of
          `theme`. Print forces the header back to white (styles.css's
          `@media print`, to save ink) — the cream-ink logo would go
          near-invisible there, so a second, light-background (navy-ink)
          pair sits alongside it, hidden on screen and swapped in only for
          print (see the `.brand-*-print`/`.brand-*-screen` rule). */}
      <button className="brand" onClick={onGoHome} aria-label="Ir al inicio">
        <img className="brand-icon brand-icon-screen" src={patitoursIconDark} alt="" />
        <img className="brand-wordmark brand-wordmark-screen" src={patitoursWordmarkDark} alt="PatiTours" />
        <img className="brand-icon brand-icon-print" src={patitoursIcon} alt="" />
        <img className="brand-wordmark brand-wordmark-print" src={patitoursWordmark} alt="PatiTours" />
      </button>
      <div className="header-actions">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  )
}
