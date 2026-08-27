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
}

/**
 * Top navigation bar: the PatiTours logo (swapped for a light-ink variant in
 * dark mode — see `scripts/generate_brand_assets.py`), the light/dark toggle,
 * and the mobile-collapsible nav links.
 */
export function AppHeader({ menuOpen, onToggleMenu, onCloseMenu, theme, onToggleTheme }: AppHeaderProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <img className="brand-logo" src={theme === 'dark' ? patitoursLogoDark : patitoursLogoLight} alt="PatiTours" />
        <small>EUROPA 2027 · NUESTRO VIAJE</small>
      </div>
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
