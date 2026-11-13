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
  ArrowRight,
  Zap,
  PlaySquare,
  AlertCircle
} from 'lucide-react'
import { api, fmtTime } from '../api'
import { showRewardedAd } from '../adsgram'
import { haptic } from '../telegram'
import type { QuizResult } from '../types'

export default function ScoreCard({
  r,
  onLeaderboard,
  onHome,
  onResultUpdate,
}: {
  r: QuizResult
  onLeaderboard: () => void
  onHome: () => void
  onResultUpdate?: (updated: QuizResult) => void
}) {
  const [result, setResult] = useState<QuizResult>(r)
  const [copied, setCopied] = useState(false)
  const [filter, setFilter] = useState<'all' | 'correct' | 'wrong'>('all')
  const [boosting, setBoosting] = useState(false)
  const [boostErr, setBoostErr] = useState('')
  const [boostJustActivated, setBoostJustActivated] = useState(false)

  // Fire celebratory confetti on initial mount
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

  const pct = Math.round((result.points / Math.max(1, result.max_points)) * 100)

  const getTier = () => {
    if (result.boosted) {
      return {
        title: 'Supercharged Performance!',
        subtitle: '2x Booster active — points doubled on the leaderboard!',
        chip: '⚡ 2X POWER BOOST',
      }
    }
    if (pct >= 100) return { title: 'Man of the Match', subtitle: 'Flawless performance on the pitch!', chip: '🏆 PERFECT RUN' }
    if (pct >= 80) return { title: 'Champions Tier', subtitle: 'World-class football intellect!', chip: '⭐ TOP SCORER' }
    if (pct >= 60) return { title: 'Top Flight Class', subtitle: 'Sharp instincts and solid knowledge!', chip: '⚽ PRO LEAGUE' }
    if (pct >= 40) return { title: 'Solid Match', subtitle: 'Good football awareness!', chip: '🎯 ON TARGET' }
    return { title: 'Full-Time Whistle', subtitle: 'Warm up for the next fixture!', chip: '⏱️ MATCH COMPLETE' }
  }

  const tier = getTier()

  // Handle 2x booster click (watch rewarded ad then double score)
  const handleBoost = async () => {
    if (boosting || result.boosted) return
    setBoostErr('')
    setBoosting(true)
    haptic('tap')

    try {
      // 1. Show Adsgram rewarded ad; user must watch to the end
      await showRewardedAd()

      // 2. Call backend to double score and update leaderboard atomically
      const updated = await api.boost(result.quiz_id)

      haptic('success')
      setResult(updated)
      if (onResultUpdate) onResultUpdate(updated)
      setBoostJustActivated(true)

      // 3. Fire high-energy golden confetti celebration for 2x boost!
      try {
        confetti({
          particleCount: 100,
          spread: 80,
          origin: { y: 0.55 },
          colors: ['#f59e0b', '#fbbf24', '#7b8cff', '#5a6cf0', '#ffffff'],
        })
      } catch {
        // ignore
      }
    } catch (err) {
      const msg = (err as Error)?.message || 'Ad was closed early. Watch full ad to double your points.'
      setBoostErr(msg)
      haptic('error')
    } finally {
      setBoosting(false)
    }
  }

  const handleShare = async () => {
    const boostTag = result.boosted ? ' (⚡ 2X BOOSTED!)' : ''
    const text = `⚽ Footy Quiz: ${result.title}\n🎯 Score: ${result.points}/${result.max_points} pts${boostTag} (${result.correct_count}/${result.total} correct)\n⏱️ Time: ${fmtTime(result.time_ms)}${result.rank ? `\n🏆 Rank: #${result.rank} of ${result.players}` : ''}\nCan you beat my score?`
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

  const filteredResults = result.results.filter((q) => {
    if (filter === 'correct') return q.correct
    if (filter === 'wrong') return !q.correct
    return true
  })

  return (
    <div className="score-popup-wrapper">
      {/* Hero Celebratory Score Card */}
      <div className={`card score-hero-card ${result.boosted ? 'is-boosted-card' : ''}`}>
        <div className="score-hero-glow" aria-hidden />

        <div className={`score-hero-badge-pill ${result.boosted ? 'boosted-pill' : ''}`}>
          {result.boosted ? (
            <Zap size={14} className="sparkle-icon" fill="currentColor" />
          ) : (
            <Sparkles size={14} className="sparkle-icon" />
          )}
          <span>{tier.chip}</span>
        </div>

        <h2 className="score-hero-title">{tier.title}</h2>
        <p className="score-hero-sub">{tier.subtitle}</p>

        {/* Stadium Scoreboard */}
        <div className={`score-board ${result.boosted ? 'boosted' : ''}`}>
          {result.boosted && (
            <div className="score-boost-indicator">
              <Zap size={12} fill="currentColor" />
              <span>2X MULTIPLIER APPLIED</span>
            </div>
          )}
          <div className="score-digits">
            <span className={`score-val ${boostJustActivated ? 'pop-boost' : ''}`}>
              {result.points}
            </span>
            <span className="score-max">/{result.max_points}</span>
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
            <b>{result.correct_count} <small>/ {result.total}</small></b>
          </div>

          <div className="score-metric-box">
            <div className="metric-header">
              <Clock size={15} className="metric-icon accent" />
              <span>Time</span>
            </div>
            <b>{fmtTime(result.time_ms)}</b>
          </div>

          {result.rank && (
            <div className="score-metric-box wide">
              <div className="metric-header">
                <Trophy size={15} className="metric-icon gold" />
                <span>Today's Standing</span>
              </div>
              <div className="metric-rank-val">
                Rank <b>#{result.rank}</b> <span className="muted">of {result.players} players</span>
              </div>
            </div>
          )}
        </div>

        {/* Booster Error Notice if skipped/closed early */}
        {boostErr && (
          <div className="booster-notice-error">
            <AlertCircle size={15} />
            <span>{boostErr}</span>
          </div>
        )}

        {/* Booster Success Banner */}
        {boostJustActivated && (
          <div className="booster-notice-success">
            <Zap size={15} fill="currentColor" />
            <span>Points doubled to {result.points} pts! Updated on Leaderboard.</span>
          </div>
        )}

        {/* 2X BOOSTER BUTTON - placed slightly above the share results button */}
        <button
          className={`score-booster-btn ${result.boosted ? 'active' : ''} ${boosting ? 'loading' : ''}`}
          onClick={handleBoost}
          disabled={boosting || !!result.boosted}
          title={result.boosted ? 'Booster already claimed for this quiz' : 'Watch an ad to double your score'}
        >
          <div className="booster-btn-inner">
            <div className="booster-icon-wrap">
              {boosting ? (
                <div className="spinner-ring sm" />
              ) : result.boosted ? (
                <CheckCircle2 size={19} className="booster-check-icon" />
              ) : (
                <Zap size={19} className="booster-zap-icon" fill="currentColor" />
              )}
            </div>

            <div className="booster-text-col grow">
              <span className="booster-title">
                {boosting
                  ? 'Watching rewarded ad…'
                  : result.boosted
                    ? '2X Booster Activated'
                    : 'Double Your Points'}
              </span>
              <span className="booster-sub">
                {result.boosted
                  ? 'Points doubled and saved to leaderboard'
                  : 'Watch a short ad to get 2x points'}
              </span>
            </div>

            {!result.boosted && !boosting && (
              <div className="booster-badge-tag">
                <PlaySquare size={12} />
                <span>2X</span>
              </div>
            )}
          </div>
        </button>

        {/* Share Button - just slightly below the booster button */}
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
              All ({result.results.length})
            </button>
            <button
              className={`review-tab ${filter === 'correct' ? 'active' : ''}`}
              onClick={() => setFilter('correct')}
            >
              ✓ {result.correct_count}
            </button>
            <button
              className={`review-tab ${filter === 'wrong' ? 'active' : ''}`}
              onClick={() => setFilter('wrong')}
            >
              ✕ {result.total - result.correct_count}
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
