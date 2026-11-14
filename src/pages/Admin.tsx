import { useState } from 'react'
import Analytics from './admin/Analytics'
import SendQuiz from './admin/SendQuiz'
import WinnerAnnouncement from './admin/WinnerAnnouncement'

export default function Admin() {
  const [view, setView] = useState<'send' | 'winners' | 'analytics'>('send')
  return (
    <div className="page">
      <h1>Admin</h1>
      <p className="sub">Manage quizzes, publish winner cards, and view player analytics.</p>
      <div className="seg" style={{ marginBottom: 14 }}>
        <button className={view === 'send' ? 'on' : ''} onClick={() => setView('send')}>Quizzes & Drafts</button>
        <button className={view === 'winners' ? 'on' : ''} onClick={() => setView('winners')}>Winner Card</button>
        <button className={view === 'analytics' ? 'on' : ''} onClick={() => setView('analytics')}>Analytics</button>
      </div>
      {view === 'send' ? <SendQuiz /> : view === 'winners' ? <WinnerAnnouncement /> : <Analytics />}
    </div>
  )
}
