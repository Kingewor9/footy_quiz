import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import NavBar, { Tab } from './components/NavBar'
import Admin from './pages/Admin'
import Home from './pages/Home'
import Leaderboard from './pages/Leaderboard'
import Play from './pages/Play'
import { initTelegram, startParam } from './telegram'
import type { Me } from './types'

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState<Tab>('home')
  // A channel post opens the app with ?startapp=<quizId>, which jumps straight into that quiz.
  const [playId, setPlayId] = useState<string | null>(startParam ?? null)

  const loadMe = useCallback(() => {
    api.me().then(setMe).catch((e) => setErr(e.message))
  }, [])

  useEffect(() => {
    initTelegram()
    loadMe()
  }, [loadMe])

  if (err) return <div className="center"><h1>Can't open the app</h1><p className="muted">{err}</p></div>
  if (!me) return <div className="center muted">Loading…</div>

  if (playId)
    return (
      <Play
        quizId={playId}
        onExit={() => { setPlayId(null); setTab('home'); loadMe() }}
        onLeaderboard={() => { setPlayId(null); setTab('leaderboard'); loadMe() }}
      />
    )

  return (
    <>
      {tab === 'home' && <Home me={me} onPlay={setPlayId} onLeaderboard={() => setTab('leaderboard')} />}
      {tab === 'leaderboard' && <Leaderboard myId={me.user.id} />}
      {tab === 'admin' && me.is_admin && <Admin />}
      <NavBar tab={tab} onChange={(t) => { setTab(t); if (t === 'home') loadMe() }} isAdmin={me.is_admin} />
    </>
  )
}
