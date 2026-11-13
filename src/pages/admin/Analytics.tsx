import { useEffect, useState } from 'react'
import { api, fmtTime } from '../../api'
import type { Analytics as A } from '../../types'

export default function Analytics() {
  const [a, setA] = useState<A | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    api.admin.analytics().then(setA).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="notice err">{err}</div>
  if (!a) return <div className="empty">Loading…</div>
  const max = Math.max(1, ...a.daily.map((d) => d.players))
  return (
    <>
      <div className="stats">
        <div className="stat"><b>{a.total_players}</b><span>all-time players</span></div>
        <div className="stat"><b>{a.players_today}</b><span>players today</span></div>
        <div className="stat"><b>{a.plays_today}</b><span>quiz plays today</span></div>
        <div className="stat"><b>{a.quizzes_live}</b><span>quizzes sent</span></div>
      </div>

      <div className="card">
        <b>Players, last 7 days</b>
        <div className="bars" style={{ marginTop: 14 }}>
          {a.daily.map((d) => (
            <div key={d.day} title={`${d.players} players, ${d.plays} plays`}>
              <i style={{ height: `${(d.players / max) * 80}%` }} />
              {d.players}
              <br />
              {d.day.slice(8)}
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ overflowX: 'auto' }}>
        <b>Recent quizzes</b>
        {a.quizzes.length === 0 ? (
          <div className="empty">No quizzes sent yet.</div>
        ) : (
          <table className="table" style={{ marginTop: 8 }}>
            <thead><tr><th>Quiz</th><th>Players</th><th>Avg score</th><th>Avg time</th><th>Finished</th></tr></thead>
            <tbody>
              {a.quizzes.map((q) => (
                <tr key={q.id}>
                  <td>{q.title}</td>
                  <td>{q.players}</td>
                  <td>{q.avg_score_pct}%</td>
                  <td>{fmtTime(q.avg_time_ms)}</td>
                  <td>{q.completion_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
