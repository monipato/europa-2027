import { Menu, X } from 'lucide-react'
import type { Theme } from '../hooks/useTheme'
import { ThemeToggle } from './ThemeToggle'
import patitoursLogoLight from '../assets/brand/patitours-logo.png'
import patitoursLogoDark from '../assets/brand/patitours-logo-dark.png'

interface AppHeaderProps {
  menuOpen: boolean
  onToggleMenu: () => void
  onCloseMenu: () => void
  theme: Theme
  onToggleTheme: () => void
  onGoHome: () => void
  /** Whether a trip is picked yet — the nav links jump to the itinerary
   * section, which doesn't exist (visually — it's `display:none`) until
   * then, so there's nothing for them to do on the selection screen. */
  hasStartedPlanning: boolean
  onGoToDayView: () => void
  onGoToCategoryView: () => void
}

/**
 * Top navigation bar: the PatiTours logo (swapped for a light-ink variant in
 * dark mode — see `scripts/generate_brand_assets.py`), the light/dark toggle,
 * and the mobile-collapsible nav links. Clicking the logo returns to the
 * trip-selection screen, like a normal site home link.
 */
export function AppHeader({ menuOpen, onToggleMenu, onCloseMenu, theme, onToggleTheme, onGoHome, hasStartedPlanning, onGoToDayView, onGoToCategoryView }: AppHeaderProps) {
  return (
    <header className="topbar">
      <button className="brand" onClick={onGoHome} aria-label="Ir al inicio">
        <img className="brand-logo" src={theme === 'dark' ? patitoursLogoDark : patitoursLogoLight} alt="PatiTours" />
        <small>NUESTRO VIAJE</small>
      </button>
      <div className="header-actions">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        {hasStartedPlanning && (
          <button className="menu-button" aria-label="Abrir menú" onClick={onToggleMenu}>
            {menuOpen ? <X /> : <Menu />}
          </button>
        )}
      </div>
      {hasStartedPlanning && (
        <nav className={menuOpen ? 'open' : ''}>
          <button onClick={() => { onGoToDayView(); onCloseMenu() }}>Itinerario</button>
          <button onClick={() => { onGoToCategoryView(); onCloseMenu() }}>Resumen de gastos</button>
        </nav>
      )}
    </header>
  )
}
