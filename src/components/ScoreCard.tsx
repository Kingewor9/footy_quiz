import { fmtTime } from '../api'
import type { QuizResult } from '../types'

export default function ScoreCard({ r, onLeaderboard, onHome }: { r: QuizResult; onLeaderboard: () => void; onHome: () => void }) {
  return (
    <>
      <div className="card score">
        <div className="muted">{r.title}</div>
        <div className="big">
          {r.points}
          <span className="muted" style={{ fontSize: 24 }}> / {r.max_points}</span>
        </div>
        <p className="muted" style={{ margin: '8px 0 0' }}>
          {r.correct_count} of {r.total} correct in {fmtTime(r.time_ms)}
        </p>
        {r.rank && (
          <p style={{ margin: '14px 0 0' }}>
            <span className="chip">You are #{r.rank} of {r.players} today</span>
          </p>
        )}
      </div>

      <div className="card">
        <b>Your answers</b>
        {r.results.map((q) => (
          <div className="review" key={q.id}>
            <div className={`tick ${q.correct ? 'ok' : 'no'}`}>{q.correct ? '✓' : '✕'}</div>
            <div className="grow">
              <div>{q.text}</div>
              {!q.correct && (
                <div className="small muted">
                  {q.your_answer ? `You answered: ${q.your_answer}. ` : 'No answer. '}Correct: {q.correct_answer}
                </div>
              )}
            </div>
            <div className="small muted">{q.points}/{q.max}</div>
          </div>
        ))}
      </div>

      <div className="row">
        <button className="btn ghost grow" onClick={onHome}>Back home</button>
        <button className="btn grow" onClick={onLeaderboard}>Leaderboard</button>
      </div>
    </>
  )
}
