import duckRomantic from '../assets/ducks/duck-romantic.png'

export function AppFooter() {
  return (
    <footer>
      <span>Europa 2027 · Planifica con calma</span>
      <span><img className="footer-duck" src={duckRomantic} alt="" aria-hidden="true" /> Hecho para viajar mejor</span>
    </footer>
  )
}
