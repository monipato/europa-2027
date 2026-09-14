import type { Theme } from '../hooks/useTheme'
import { ThemeToggle } from './ThemeToggle'
import patitoursIconDark from '../assets/brand/patitours-icon-dark.png'
import patitoursWordmarkDark from '../assets/brand/patitours-wordmark-dark.png'

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
          theme alike — see .topbar in styles.css), so the logo always wears
          its dark-background (cream-ink) variant regardless of `theme`. */}
      <button className="brand" onClick={onGoHome} aria-label="Ir al inicio">
        <img className="brand-icon" src={patitoursIconDark} alt="" />
        <img className="brand-wordmark" src={patitoursWordmarkDark} alt="PatiTours" />
      </button>
      <div className="header-actions">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  )
}
