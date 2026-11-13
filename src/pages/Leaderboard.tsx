import { useEffect, useState } from 'react'
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

function Move({ r }: { r: BoardRow }) {
  if (r.move === 'up') return <div className="move up">▲ {r.delta}</div>
  if (r.move === 'down') return <div className="move down">▼ {r.delta}</div>
  return <div className="move">–</div>
}

export default function Leaderboard({ myId }: { myId: number }) {
  const [board, setBoard] = useState<Board | null>(null)
  const [err, setErr] = useState('')
  const left = useCountdown(board?.resets_at)

  useEffect(() => {
    api.leaderboard().then(setBoard).catch((e) => setErr(e.message))
  }, [])

  return (
    <div className="page">
      <h1>Leaderboard</h1>
      <p className="sub">{left ? `Resets in ${left}` : 'Today'}. Ties are settled by total time.</p>
      {err && <div className="notice err">{err}</div>}
      {board && board.rows.length === 0 && <div className="empty">Nobody has played yet today. Be the first on the board.</div>}
      {board?.rows.map((r) => (
        <div className={`lb ${r.user_id === myId ? 'me' : ''}`} key={r.user_id}>
          <div className={`rank ${r.rank <= 3 ? 'top' : ''}`}>{r.rank}</div>
          <Avatar name={r.name} url={r.photo_url} />
          <div className="grow">
            <div className="name">{r.name}{r.user_id === myId && ' (you)'}</div>
            <div className="small muted">{r.username ? `@${r.username}` : fmtTime(r.time_ms)}</div>
          </div>
          <div className="pts">
            <b>{r.points}</b>
            <span className="small muted">pts</span>
          </div>
          <Move r={r} />
        </div>
      ))}
    </div>
  )
}
