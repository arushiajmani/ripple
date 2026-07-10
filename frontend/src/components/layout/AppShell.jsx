import { Link } from 'react-router-dom'
import './layout.css'

export function AppShell({ children }) {
  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <Link to="/" className="app-shell__brand">
          <span className="app-shell__logo" aria-hidden="true">
            ◉
          </span>
          Ripple
        </Link>
      </header>
      <main className="app-shell__main">{children}</main>
    </div>
  )
}
