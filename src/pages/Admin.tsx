import { useState } from 'react'
import Analytics from './admin/Analytics'
import SendQuiz from './admin/SendQuiz'

export default function Admin() {
  const [view, setView] = useState<'send' | 'analytics'>('send')
  return (
    <div className="page">
      <h1>Admin</h1>
      <p className="sub">Create quizzes and see how players are doing.</p>
      <div className="seg" style={{ marginBottom: 14 }}>
        <button className={view === 'send' ? 'on' : ''} onClick={() => setView('send')}>Send quiz</button>
        <button className={view === 'analytics' ? 'on' : ''} onClick={() => setView('analytics')}>Analytics</button>
      </div>
      {view === 'send' ? <SendQuiz /> : <Analytics />}
    </div>
  )
}
