import { Menu, X } from 'lucide-react'

interface AppHeaderProps {
  menuOpen: boolean
  onToggleMenu: () => void
  onCloseMenu: () => void
}

/** Top navigation bar: brand mark and the mobile-collapsible nav links. */
export function AppHeader({ menuOpen, onToggleMenu, onCloseMenu }: AppHeaderProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">✈</span>
        <div>
          <strong>EUROPA <span>2027</span></strong>
          <small>MI VIAJE · COTIZACIÓN</small>
        </div>
      </div>
      <div className="header-actions">
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
