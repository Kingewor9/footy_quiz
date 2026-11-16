import { Home, Trophy, ShieldCheck, RadioTower, Compass } from 'lucide-react'
import { haptic } from '../telegram'

export type Tab = 'home' | 'leaderboard' | 'discover' | 'channels' | 'admin'

interface TabConfig {
  key: Tab
  label: string
  icon: typeof Home
}

const TABS: TabConfig[] = [
  { key: 'home', label: 'Home', icon: Home },
  { key: 'leaderboard', label: 'Leagues', icon: Trophy },
  { key: 'discover', label: 'Discover', icon: Compass },
  { key: 'channels', label: 'Channels', icon: RadioTower },
  { key: 'admin', label: 'Admin', icon: ShieldCheck },
]

export default function NavBar({
  tab,
  onChange,
  isAdmin,
}: {
  tab: Tab
  onChange: (t: Tab) => void
  isAdmin: boolean
}) {
  const visibleTabs = isAdmin ? TABS : TABS.filter((t) => t.key !== 'admin')

  return (
    <nav className="nav floating-navbar" aria-label="Main Navigation">
      {visibleTabs.map((t) => {
        const Icon = t.icon
        const isActive = tab === t.key
        return (
          <button
            key={t.key}
            className={`nav-tab-btn ${isActive ? 'on' : ''}`}
            onClick={() => {
              haptic('tap')
              onChange(t.key)
            }}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon size={20} className="nav-tab-icon" strokeWidth={isActive ? 2.4 : 2} />
            <span className="nav-tab-label">{t.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
