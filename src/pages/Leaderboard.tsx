import { useEffect, useState } from 'react'
import {
  Trophy,
  Crown,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus
} from 'lucide-react'
import Avatar from '../components/Avatar'
import { api, fmtTime } from '../api'
import type { Board, BoardRow } from '../types'

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

export default function Leaderboard({ myId }: { myId: number }) {
  const [board, setBoard] = useState<Board | null>(null)
  const [err, setErr] = useState('')
  const left = useCountdown(board?.resets_at)

  useEffect(() => {
    api.leaderboard().then(setBoard).catch((e) => setErr(e.message))
  }, [])

  const top3 = board?.rows.slice(0, 3) || []

  return (
    <div className="page leaderboard-page">
      {/* Page Title & Countdown Badge */}
      <div className="lb-header">
        <div>
          <h1>Leaderboard</h1>
          <p className="sub">Ties are settled by total match completion time.</p>
        </div>

        {left && (
          <div className="reset-countdown-pill">
            <Clock size={13} />
            <span>Resets in <b>{left}</b></span>
          </div>
        )}
      </div>

      {err && <div className="notice err">{err}</div>}

      {/* Top 3 Podium (shown when at least 2 players are on the board) */}
      {top3.length >= 2 && (
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
      {board && board.rows.length === 0 && (
        <div className="empty empty-state-box">
          <Trophy size={32} className="muted" style={{ marginBottom: 10 }} />
          <p>Nobody has played yet today.</p>
          <span className="small muted">Take a quiz now to claim the #1 spot on the table!</span>
        </div>
      )}

      {/* Players List */}
      <div className="lb-list">
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
      </div>
    </div>
  )
}
