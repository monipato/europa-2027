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
}

/**
 * Top navigation bar: the PatiTours logo (swapped for a light-ink variant in
 * dark mode — see `scripts/generate_brand_assets.py`), the light/dark toggle,
 * and the mobile-collapsible nav links. Clicking the logo returns to the
 * trip-selection screen, like a normal site home link.
 */
export function AppHeader({ menuOpen, onToggleMenu, onCloseMenu, theme, onToggleTheme, onGoHome }: AppHeaderProps) {
  return (
    <header className="topbar">
      <button className="brand" onClick={onGoHome} aria-label="Ir al inicio">
        <img className="brand-logo" src={theme === 'dark' ? patitoursLogoDark : patitoursLogoLight} alt="PatiTours" />
        <small>EUROPA 2027<br />NUESTRO VIAJE</small>
      </button>
      <div className="header-actions">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <button className="menu-button" aria-label="Abrir menú" onClick={onToggleMenu}>
          {menuOpen ? <X /> : <Menu />}
        </button>
      </div>
      <nav className={menuOpen ? 'open' : ''}>
        <a href="#itinerario" onClick={onCloseMenu}>Itinerario</a>
        <a href="#resumen" onClick={onCloseMenu}>Resumen de gastos</a>
      </nav>
    </header>
  )
}
