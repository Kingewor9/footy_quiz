import { useEffect, useState } from 'react'
import confetti from 'canvas-confetti'
import {
  Trophy,
  Award,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Target,
  Share2,
  Check,
  RotateCcw,
  ArrowRight
} from 'lucide-react'
import { fmtTime } from '../api'
import type { QuizResult } from '../types'

export default function ScoreCard({
  r,
  onLeaderboard,
  onHome,
}: {
  r: QuizResult
  onLeaderboard: () => void
  onHome: () => void
}) {
  const [copied, setCopied] = useState(false)
  const [filter, setFilter] = useState<'all' | 'correct' | 'wrong'>('all')

  useEffect(() => {
    try {
      confetti({
        particleCount: 70,
        spread: 60,
        origin: { y: 0.6 },
        colors: ['#5a6cf0', '#1fb85a', '#f59e0b', '#7b8cff'],
      })
    } catch {
      // gracefully skip if canvas is unsupported
    }
  }, [])

  const pct = Math.round((r.points / Math.max(1, r.max_points)) * 100)

  const getTier = () => {
    if (pct === 100) return { title: 'Man of the Match', subtitle: 'Flawless performance on the pitch!', chip: '🏆 PERFECT RUN' }
    if (pct >= 80) return { title: 'Champions Tier', subtitle: 'World-class football intellect!', chip: '⭐ TOP SCORER' }
    if (pct >= 60) return { title: 'Top Flight Class', subtitle: 'Sharp instincts and solid knowledge!', chip: '⚽ PRO LEAGUE' }
    if (pct >= 40) return { title: 'Solid Match', subtitle: 'Good football awareness!', chip: '🎯 ON TARGET' }
    return { title: 'Full-Time Whistle', subtitle: 'Warm up for the next fixture!', chip: '⏱️ MATCH COMPLETE' }
  }

  const tier = getTier()

  const handleShare = async () => {
    const text = `⚽ Footy Quiz: ${r.title}\n🎯 Score: ${r.points}/${r.max_points} pts (${r.correct_count}/${r.total} correct)\n⏱️ Time: ${fmtTime(r.time_ms)}${r.rank ? `\n🏆 Rank: #${r.rank} of ${r.players}` : ''}\nCan you beat my score?`
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2400)
      }
    } catch {
      // fallback
    }
  }

  const filteredResults = r.results.filter((q) => {
    if (filter === 'correct') return q.correct
    if (filter === 'wrong') return !q.correct
    return true
  })

  return (
    <div className="score-popup-wrapper">
      {/* Hero Celebratory Score Card */}
      <div className="card score-hero-card">
        <div className="score-hero-glow" aria-hidden />

        <div className="score-hero-badge-pill">
          <Sparkles size={14} className="sparkle-icon" />
          <span>{tier.chip}</span>
        </div>

        <h2 className="score-hero-title">{tier.title}</h2>
        <p className="score-hero-sub">{tier.subtitle}</p>

        {/* Stadium Scoreboard */}
        <div className="score-board">
          <div className="score-digits">
            <span className="score-val">{r.points}</span>
            <span className="score-max">/{r.max_points}</span>
          </div>
          <div className="score-pill-tag">
            <Award size={13} />
            <span>{pct}% Accuracy</span>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="score-metrics-grid">
          <div className="score-metric-box">
            <div className="metric-header">
              <Target size={15} className="metric-icon green" />
              <span>Correct</span>
            </div>
            <b>{r.correct_count} <small>/ {r.total}</small></b>
          </div>

          <div className="score-metric-box">
            <div className="metric-header">
              <Clock size={15} className="metric-icon accent" />
              <span>Time</span>
            </div>
            <b>{fmtTime(r.time_ms)}</b>
          </div>

          {r.rank && (
            <div className="score-metric-box wide">
              <div className="metric-header">
                <Trophy size={15} className="metric-icon gold" />
                <span>Today's Standing</span>
              </div>
              <div className="metric-rank-val">
                Rank <b>#{r.rank}</b> <span className="muted">of {r.players} players</span>
              </div>
            </div>
          )}
        </div>

        {/* Share Button */}
        <button className="score-share-btn" onClick={handleShare}>
          {copied ? <Check size={16} /> : <Share2 size={16} />}
          <span>{copied ? 'Result copied to clipboard!' : 'Share result with friends'}</span>
        </button>
      </div>

      {/* Answer Review Section */}
      <div className="card review-section-card">
        <div className="row between review-section-header">
          <div className="row" style={{ gap: 8 }}>
            <Award size={18} className="muted" />
            <b style={{ fontSize: 16 }}>Match Review</b>
          </div>
          <div className="review-filter-tabs">
            <button
              className={`review-tab ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All ({r.results.length})
            </button>
            <button
              className={`review-tab ${filter === 'correct' ? 'active' : ''}`}
              onClick={() => setFilter('correct')}
            >
              ✓ {r.correct_count}
            </button>
            <button
              className={`review-tab ${filter === 'wrong' ? 'active' : ''}`}
              onClick={() => setFilter('wrong')}
            >
              ✕ {r.total - r.correct_count}
            </button>
          </div>
        </div>

        <div className="review-list">
          {filteredResults.length === 0 ? (
            <div className="empty small">No questions in this filter.</div>
          ) : (
            filteredResults.map((q, idx) => (
              <div className={`review-item ${q.correct ? 'is-correct' : 'is-wrong'}`} key={q.id || idx}>
                <div className="review-icon-wrap">
                  {q.correct ? (
                    <CheckCircle2 size={22} className="review-icon ok" />
                  ) : (
                    <XCircle size={22} className="review-icon no" />
                  )}
                </div>

                <div className="review-content grow">
                  <div className="review-q-text">{q.text}</div>
                  {q.correct ? (
                    <div className="review-answer-tag ok">
                      <span>Answer:</span> {q.your_answer || q.correct_answer}
                    </div>
                  ) : (
                    <div className="review-answer-diff">
                      <div className="review-answer-tag no">
                        <span>Your pick:</span> {q.your_answer || '(No answer)'}
                      </div>
                      <div className="review-answer-tag ok">
                        <span>Correct:</span> {q.correct_answer}
                      </div>
                    </div>
                  )}
                </div>

                <div className="review-pts-badge">
                  <b>+{q.points}</b>
                  <small>/{q.max}</small>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Navigation Actions */}
      <div className="score-actions-footer">
        <button className="btn ghost grow score-nav-btn" onClick={onHome}>
          <RotateCcw size={18} />
          <span>Back home</span>
        </button>
        <button className="btn grow score-nav-btn primary" onClick={onLeaderboard}>
          <Trophy size={18} />
          <span>Leaderboard</span>
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
