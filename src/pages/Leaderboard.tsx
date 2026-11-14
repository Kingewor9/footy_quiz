import { useEffect, useState } from 'react'
import {
  Trophy,
  Crown,
  Clock,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Minus
} from 'lucide-react'
import Avatar from '../components/Avatar'
import ChannelMark from '../components/ChannelMark'
import { api, fmtTime } from '../api'
import type { Board, BoardRow, Channel } from '../types'

function useCountdown(target?: string) {
  const [left, setLeft] = useState('')
  useEffect(() => {
    if (!target) return
    const tick = () => {
      const s = Math.max(0, Math.floor((new Date(target).getTime() - Date.now()) / 1000))
      const p = (n: number) => String(n).padStart(2, '0')
      setLeft(`${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`)
    }
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [target])
  return left
}

function MoveIndicator({ r }: { r: BoardRow }) {
  if (r.move === 'up') {
    return (
      <div className="move-pill up" title={`Moved up ${r.delta} places`}>
        <TrendingUp size={13} />
        <span>{r.delta}</span>
      </div>
    )
  }
  if (r.move === 'down') {
    return (
      <div className="move-pill down" title={`Moved down ${r.delta} places`}>
        <TrendingDown size={13} />
        <span>{r.delta}</span>
      </div>
    )
  }
  return (
    <div className="move-pill flat">
      <Minus size={13} />
    </div>
  )
}

export default function Leaderboard({ myId, initialChannelId }: { myId: number; initialChannelId?: string | null }) {
  const [board, setBoard] = useState<Board | null>(null)
  const [channels, setChannels] = useState<Channel[] | null>(null)
  const [activeChannel, setActiveChannel] = useState<string | null>(initialChannelId ?? null)
  const [err, setErr] = useState('')
  const left = useCountdown(board?.resets_at)

  useEffect(() => {
    api.channels().then((items) => {
      setChannels(items)
      if (initialChannelId && items.some((c) => c.id === initialChannelId)) setActiveChannel(initialChannelId)
    }).catch((e) => setErr(e.message))
  }, [initialChannelId])

  useEffect(() => {
    if (!activeChannel) {
      setBoard(null)
      return
    }
    api.channelLeaderboard(activeChannel).then(setBoard).catch((e) => setErr(e.message))
  }, [activeChannel])

  const top3 = board?.rows.slice(0, 3) || []

  return (
    <div className="page leaderboard-page">
      <div className="lb-header">
        <div>
          {activeChannel && <button className="link channel-back" onClick={() => { setActiveChannel(null); setBoard(null) }}>‹ All channels</button>}
          <h1>{activeChannel ? `${board?.channel?.title || channels?.find((c) => c.id === activeChannel)?.title || 'Channel'} Leaderboard` : 'Your leaderboards'}</h1>
          <p className="sub">{activeChannel ? 'Ties are settled by total match completion time.' : 'Choose a channel to see its daily standings.'}</p>
        </div>
        {activeChannel && left && (
          <div className="reset-countdown-pill">
            <Clock size={13} />
            <span>Resets in <b>{left}</b></span>
          </div>
        )}
      </div>

      {err && <div className="notice err">{err}</div>}

      {!activeChannel && channels === null && <div className="empty"><div className="spinner-ring sm" />Loading your channel leagues…</div>}
      {!activeChannel && channels?.length === 0 && (
        <div className="empty empty-state-box">
          <Trophy size={30} className="muted" />
          <p>No channel leaderboard yet</p>
          <span className="small muted">Play a quiz from a channel and your league will appear here.</span>
        </div>
      )}
      {!activeChannel && channels?.map((channel) => (
        <button className="channel-leaderboard-row card" key={channel.id} onClick={() => { setErr(''); setActiveChannel(channel.id) }}>
          <ChannelMark channel={channel} />
          <span className="grow">
            <b>{channel.title}</b>
            <small>{channel.rank ? `Your rank #${channel.rank} · ${channel.players} players` : `${channel.players} players today`}</small>
          </span>
          <span className="channel-board-points"><b>{channel.points ?? 0}</b><small>pts</small></span>
          <ChevronRight size={19} className="muted" />
        </button>
      ))}

      {activeChannel && !board && !err && <div className="empty"><div className="spinner-ring sm" />Loading standings…</div>}

      {/* Top 3 Podium (shown when at least 2 players are on the board) */}
      {activeChannel && top3.length >= 2 && (
        <div className="podium-card card">
          <div className="podium-header">
            <Crown size={15} className="podium-crown-icon" />
            <span>Today's Leaders</span>
          </div>

          <div className="podium-display">
            {/* 2nd Place */}
            {top3[1] && (
              <div className="podium-col rank-2">
                <div className="podium-avatar-wrap">
                  <Avatar name={top3[1].name} url={top3[1].photo_url} size={44} />
                  <span className="podium-rank-badge rank-2-badge">2</span>
                </div>
                <span className="podium-name">{top3[1].name.split(' ')[0]}</span>
                <b className="podium-pts">{top3[1].points} <small>pts</small></b>
              </div>
            )}

            {/* 1st Place */}
            {top3[0] && (
              <div className="podium-col rank-1">
                <div className="podium-avatar-wrap">
                  <div className="podium-winner-crown">
                    <Crown size={18} />
                  </div>
                  <Avatar name={top3[0].name} url={top3[0].photo_url} size={54} />
                  <span className="podium-rank-badge rank-1-badge">1</span>
                </div>
                <span className="podium-name">{top3[0].name.split(' ')[0]}</span>
                <b className="podium-pts">{top3[0].points} <small>pts</small></b>
              </div>
            )}

            {/* 3rd Place */}
            {top3[2] && (
              <div className="podium-col rank-3">
                <div className="podium-avatar-wrap">
                  <Avatar name={top3[2].name} url={top3[2].photo_url} size={42} />
                  <span className="podium-rank-badge rank-3-badge">3</span>
                </div>
                <span className="podium-name">{top3[2].name.split(' ')[0]}</span>
                <b className="podium-pts">{top3[2].points} <small>pts</small></b>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty State */}
      {activeChannel && board && board.rows.length === 0 && (
        <div className="empty empty-state-box">
          <Trophy size={32} className="muted" style={{ marginBottom: 10 }} />
          <p>Nobody has played yet today.</p>
          <span className="small muted">Take a quiz now to claim the #1 spot on the table!</span>
        </div>
      )}

      {/* Players List */}
      {activeChannel && <div className="lb-list">
        {board?.rows.map((r) => {
          const isMe = r.user_id === myId
          const isTop3 = r.rank <= 3
          return (
            <div className={`lb-item ${isMe ? 'is-me' : ''}`} key={r.user_id}>
              <div className={`lb-rank-num ${isTop3 ? `top top-${r.rank}` : ''}`}>
                {r.rank}
              </div>

              <Avatar name={r.name} url={r.photo_url} size={42} />

              <div className="lb-info grow">
                <div className="lb-name">
                  <span>{r.name}</span>
                  {isMe && <span className="you-pill">You</span>}
                </div>
                <div className="lb-meta">
                  {r.username ? `@${r.username}` : ''}
                  {r.username && r.time_ms ? ' · ' : ''}
                  {r.time_ms ? fmtTime(r.time_ms) : ''}
                </div>
              </div>

              <div className="lb-score">
                <b>{r.points}</b>
                <span className="lb-pts-label">pts</span>
              </div>

              <MoveIndicator r={r} />
            </div>
          )
        })}
      </div>}
      <div className="channel-powered">Powered By Footy Quiz</div>
    </div>
  )
}
