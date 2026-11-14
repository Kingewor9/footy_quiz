import { useState } from 'react'
import { ArrowLeft, BarChart3, RadioTower, Send, Trophy } from 'lucide-react'
import Analytics from './admin/Analytics'
import SendQuiz from './admin/SendQuiz'
import WinnerAnnouncement from './admin/WinnerAnnouncement'

export default function Admin({
  channelId,
  channelName,
  isPlatformAdmin,
  onBack,
}: {
  channelId?: string
  channelName?: string
  isPlatformAdmin: boolean
  onBack?: () => void
}) {
  const [view, setView] = useState<'send' | 'winners' | 'analytics'>('send')
  if (!channelId) {
    return (
      <div className="page">
        <div className="row" style={{ gap: 10, marginBottom: 8 }}><BarChart3 size={20} /><h1 style={{ margin: 0 }}>Game analytics</h1></div>
        <p className="sub">Platform-wide activity across connected channel leagues.</p>
        {isPlatformAdmin ? <Analytics /> : <div className="notice err">Analytics are available to the game administrator only.</div>}
      </div>
    )
  }
  return (
    <div className="page channel-admin-page">
      <button className="link channel-back" onClick={onBack}><ArrowLeft size={16} /> All channels</button>
      <div className="channel-admin-title">
        <div className="channel-icon"><RadioTower size={19} /></div>
        <div><h1>{channelName || 'Channel'}</h1><p className="sub">Channel league control room</p></div>
      </div>
      <div className="seg channel-admin-tabs" style={{ marginBottom: 16 }}>
        <button className={view === 'send' ? 'on' : ''} onClick={() => setView('send')}><Send size={14} /> Quizzes</button>
        <button className={view === 'winners' ? 'on' : ''} onClick={() => setView('winners')}><Trophy size={14} /> Winner card</button>
        {isPlatformAdmin && <button className={view === 'analytics' ? 'on' : ''} onClick={() => setView('analytics')}><BarChart3 size={14} /> Analytics</button>}
      </div>
      {view === 'send' ? <SendQuiz channelId={channelId} /> : view === 'winners' ? <WinnerAnnouncement channelId={channelId} /> : isPlatformAdmin ? <Analytics /> : null}
      <div className="channel-powered">Powered By Footy Quiz</div>
    </div>
  )
}
