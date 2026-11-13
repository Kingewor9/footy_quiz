import { useEffect, useState } from 'react'
import {
  Trophy,
  Flame,
  Clock,
  Award,
  HelpCircle,
  Play as PlayIcon,
  CheckCircle2,
  ChevronRight,
  Zap
} from 'lucide-react'
import Avatar from '../components/Avatar'
import { api } from '../api'
import type { Me, QuizSummary } from '../types'

export default function Home({
  me,
  onPlay,
  onLeaderboard,
}: {
  me: Me
  onPlay: (id: string) => void
  onLeaderboard: () => void
}) {
  const [quizzes, setQuizzes] = useState<QuizSummary[] | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.quizzes().then(setQuizzes).catch((e) => setErr(e.message))
  }, [])

  const first = me.user.name.split(' ')[0]

  return (
    <div className="page home-page">
      {/* User Greeting Hero */}
      <div className="home-hero">
        <div className="row between">
          <div className="row" style={{ gap: 12 }}>
            <Avatar name={me.user.name} url={me.user.photo_url} size={48} />
            <div>
              <h1 className="home-greeting">Hi, {first} 👋</h1>
              <p className="home-sub">Climb the leaderboard with every kickoff.</p>
            </div>
          </div>
          <div className="matchday-pill">
            <span className="live-dot" />
            <Flame size={13} className="flame-icon" />
            <span>MATCHDAY</span>
          </div>
        </div>
      </div>

      {/* Today's Standing Card */}
      <div className="card home-standing-card">
        <div className="row between standing-header">
          <div className="row" style={{ gap: 8 }}>
            <Trophy size={17} className="accent-icon" />
            <b>Today's Record</b>
          </div>
          <button className="link standing-link-btn" onClick={onLeaderboard}>
            <span>Leaderboard</span>
            <ChevronRight size={15} />
          </button>
        </div>

        <div className="stats home-stats-grid">
          <div className="stat home-stat-box">
            <div className="stat-meta">
              <Zap size={15} className="stat-icon-zap" />
              <span>Points Earned</span>
            </div>
            <b>{me.today.points}</b>
          </div>

          <div className="stat home-stat-box">
            <div className="stat-meta">
              <Trophy size={15} className="stat-icon-trophy" />
              <span>Current Rank</span>
            </div>
            <b>{me.today.rank ? `#${me.today.rank}` : '–'}</b>
            <span className="stat-subtext">
              {me.today.rank ? `of ${me.today.players} players` : 'play a quiz to rank'}
            </span>
          </div>
        </div>
      </div>

      {/* Live Quizzes Section */}
      <div className="section-header-row">
        <div className="row" style={{ gap: 8 }}>
          <h2 style={{ margin: 0 }}>Live Quizzes</h2>
          <span className="count-bubble">{quizzes?.length ?? 0}</span>
        </div>
      </div>

      {err && <div className="notice err">{err}</div>}
      {quizzes === null && !err && (
        <div className="empty loading-state-inline">
          <div className="spinner-ring sm" />
          <span>Scouting live matches…</span>
        </div>
      )}
      {quizzes?.length === 0 && (
        <div className="empty empty-state-box">
          <Clock size={28} className="muted" style={{ marginBottom: 8 }} />
          <p>No quiz is live right now.</p>
          <span className="small muted">The next fixture will be announced in the channel.</span>
        </div>
      )}

      {quizzes?.map((q) => (
        <div className="card quiz-fixture-card" key={q.id}>
          <div className="fixture-main-col grow">
            <div className="fixture-badge-row">
              <span className="fixture-meta-tag">
                <HelpCircle size={12} />
                {q.question_count} {q.question_count === 1 ? 'question' : 'questions'}
              </span>
              <span className="fixture-meta-tag">
                <Clock size={12} />
                {q.max_seconds}s
              </span>
              <span className="fixture-meta-tag gold">
                <Award size={12} />
                Up to {q.total_points} pts
              </span>
            </div>

            <div className="fixture-title">{q.title}</div>
          </div>

          <div className="fixture-action-col">
            {q.played ? (
              <button className="btn ghost sm fixture-btn-played" onClick={() => onPlay(q.id)}>
                <CheckCircle2 size={14} />
                <span>{q.score} pts</span>
              </button>
            ) : (
              <button className="btn sm fixture-btn-play" onClick={() => onPlay(q.id)}>
                <PlayIcon size={14} fill="currentColor" />
                <span>Play</span>
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
