import { useState } from 'react'
import { ArrowLeft, BarChart3, RadioTower, Send, Trophy, Megaphone } from 'lucide-react'
import Analytics from './admin/Analytics'
import BroadcastMessage from './admin/BroadcastMessage'
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
  const [platformView, setPlatformView] = useState<'analytics' | 'broadcast'>('analytics')
  if (!channelId) {
    return (
      <div className="page platform-admin-page">
        <div className="row" style={{ gap: 10, marginBottom: 8 }}>
          {platformView === 'analytics' ? <BarChart3 size={20} /> : <Megaphone size={20} />}
          <h1 style={{ margin: 0 }}>{platformView === 'analytics' ? 'Game analytics' : 'Broadcast message'}</h1>
        </div>
        <p className="sub">{platformView === 'analytics' ? 'Platform-wide activity across connected channel leagues.' : 'Send an update directly to registered Footy Quiz players.'}</p>
        {isPlatformAdmin ? (
          <>
            <div className="seg channel-admin-tabs platform-admin-tabs">
              <button className={platformView === 'analytics' ? 'on' : ''} onClick={() => setPlatformView('analytics')}><BarChart3 size={14} /> Analytics</button>
              <button className={platformView === 'broadcast' ? 'on' : ''} onClick={() => setPlatformView('broadcast')}><Megaphone size={14} /> Broadcast</button>
            </div>
            {platformView === 'analytics' ? <Analytics /> : <BroadcastMessage />}
          </>
        ) : <div className="notice err">Admin tools are available to the game administrator only.</div>}
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
