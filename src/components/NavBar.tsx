export type Tab = 'home' | 'leaderboard' | 'admin'

const ICONS: Record<Tab, JSX.Element> = {
  home: <path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  leaderboard: <path d="M4 20V11h4v9zm6 0V4h4v16zm6 0v-6h4v6z" />,
  admin: <path d="M12 3 4 6v6c0 4.5 3.2 7.6 8 9 4.8-1.4 8-4.5 8-9V6zm-1 12-3-3 1.4-1.4L11 12.2l3.6-3.6L16 10z" />,
}
const LABELS: Record<Tab, string> = { home: 'Home', leaderboard: 'Leaderboard', admin: 'Admin' }

export default function NavBar({ tab, onChange, isAdmin }: { tab: Tab; onChange: (t: Tab) => void; isAdmin: boolean }) {
  const tabs: Tab[] = isAdmin ? ['home', 'leaderboard', 'admin'] : ['home', 'leaderboard']
  return (
    <nav className="nav" aria-label="Main">
      {tabs.map((t) => (
        <button key={t} className={tab === t ? 'on' : ''} onClick={() => onChange(t)} aria-current={tab === t ? 'page' : undefined}>
          <svg viewBox="0 0 24 24" fill="currentColor">{ICONS[t]}</svg>
          {LABELS[t]}
        </button>
      ))}
    </nav>
  )
}
