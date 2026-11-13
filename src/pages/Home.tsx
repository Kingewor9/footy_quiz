import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Me, QuizSummary } from '../types'

export default function Home({ me, onPlay, onLeaderboard }: { me: Me; onPlay: (id: string) => void; onLeaderboard: () => void }) {
  const [quizzes, setQuizzes] = useState<QuizSummary[] | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.quizzes().then(setQuizzes).catch((e) => setErr(e.message))
  }, [])

  const first = me.user.name.split(' ')[0]
  return (
    <div className="page">
      <h1>Hi, {first} 👋</h1>
      <p className="sub">Answer fast and answer right to climb today's table.</p>

      <div className="card">
        <div className="row between">
          <b>Today</b>
          <button className="link" onClick={onLeaderboard}>Leaderboard</button>
        </div>
        <div className="stats">
          <div className="stat">
            <b>{me.today.points}</b>
            <span>points</span>
          </div>
          <div className="stat">
            <b>{me.today.rank ? `#${me.today.rank}` : '–'}</b>
            <span>{me.today.rank ? `of ${me.today.players} players` : 'play a quiz to get ranked'}</span>
          </div>
        </div>
      </div>

      <h2>Live quizzes</h2>
      {err && <div className="notice err">{err}</div>}
      {quizzes === null && !err && <div className="empty">Loading…</div>}
      {quizzes?.length === 0 && <div className="empty">No quiz is live right now. The next one will be posted in the channel.</div>}
      {quizzes?.map((q) => (
        <div className="card row" key={q.id}>
          <div className="grow">
            <div className="name">{q.title}</div>
            <div className="small muted">
              {q.question_count} question{q.question_count !== 1 && 's'}, up to {q.total_points} points · {q.max_seconds}s
            </div>
          </div>
          {q.played ? (
            <button className="btn ghost sm" onClick={() => onPlay(q.id)}>
              {q.score} pts
            </button>
          ) : (
            <button className="btn sm" onClick={() => onPlay(q.id)}>Play</button>
          )}
        </div>
      ))}
    </div>
  )
}
