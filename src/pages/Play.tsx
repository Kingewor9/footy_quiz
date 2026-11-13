import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Clock,
  Award,
  ArrowRight,
  Sparkles,
  HelpCircle,
  X,
  AlertCircle,
  CheckCircle2
} from 'lucide-react'
import { api, ApiError, fmtTime } from '../api'
import ScoreCard from '../components/ScoreCard'
import { haptic } from '../telegram'
import type { QuizResult, StartedQuiz } from '../types'

export default function Play({
  quizId,
  onExit,
  onLeaderboard,
}: {
  quizId: string
  onExit: () => void
  onLeaderboard: () => void
}) {
  const [quiz, setQuiz] = useState<StartedQuiz | null>(null)
  const [result, setResult] = useState<QuizResult | null>(null)
  const [err, setErr] = useState('')
  const [i, setI] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const t0 = useRef(0)
  const answersRef = useRef(answers)
  const submittedRef = useRef(false)
  answersRef.current = answers

  useEffect(() => {
    let live = true
    api
      .start(quizId)
      .then((q) => {
        if (!live) return
        t0.current = Date.now() - q.elapsed_ms
        setQuiz(q)
        setElapsed(q.elapsed_ms)
      })
      .catch(async (e: ApiError) => {
        if (e.status === 409) {
          try {
            const r = await api.result(quizId)
            if (live) setResult(r)
            return
          } catch (e2) {
            e = e2 as ApiError
          }
        }
        if (live) setErr(e.message)
      })
    return () => {
      live = false
    }
  }, [quizId])

  useEffect(() => {
    if (!quiz || result) return
    const t = setInterval(() => setElapsed(Date.now() - t0.current), 500)
    return () => clearInterval(t)
  }, [quiz, result])

  const finish = useCallback(
    async (final: Record<string, string>) => {
      if (submittedRef.current) return
      submittedRef.current = true
      setBusy(true)
      try {
        const r = await api.submit(quizId, final)
        haptic('success')
        setResult(r)
      } catch (e) {
        setErr((e as Error).message)
        setBusy(false)
        submittedRef.current = false
      }
    },
    [quizId]
  )

  useEffect(() => {
    if (quiz && !result && elapsed >= quiz.max_seconds * 1000) {
      void finish(answersRef.current)
    }
  }, [elapsed, finish, quiz, result])

  if (err)
    return (
      <div className="page play">
        <div className="card notice-card-error">
          <AlertCircle size={28} className="notice-icon" />
          <div className="notice-content">
            <b>Something went wrong</b>
            <p>{err}</p>
          </div>
          <button className="btn block" onClick={onExit} style={{ marginTop: 14 }}>
            Back home
          </button>
        </div>
      </div>
    )

  if (result)
    return (
      <div className="page play">
        <ScoreCard r={result} onHome={onExit} onLeaderboard={onLeaderboard} />
      </div>
    )

  if (!quiz)
    return (
      <div className="center loading-state">
        <div className="spinner-ring" />
        <p className="muted" style={{ marginTop: 16 }}>Loading quiz pitch…</p>
      </div>
    )

  const q = quiz.questions[i]
  const value = answers[q.id] ?? ''
  const last = i === quiz.questions.length - 1
  const next = () => (last ? finish(answers) : setI(i + 1))
  const remainingMs = Math.max(0, quiz.max_seconds * 1000 - elapsed)
  const remainingSeconds = Math.ceil(remainingMs / 1000)
  const timerPercent = (remainingMs / (quiz.max_seconds * 1000)) * 100
  const isUrgent = remainingSeconds <= 10
  const timeExpired = remainingMs === 0

  return (
    <div className="page play">
      {/* Play HUD Header */}
      <div className="play-hud-header">
        <button className="icon-btn-round" onClick={onExit} title="Exit Quiz" aria-label="Exit Quiz">
          <X size={18} />
        </button>

        <div className="play-hud-pill">
          <HelpCircle size={14} className="hud-pill-icon" />
          <span>Question {i + 1} of {quiz.questions.length}</span>
        </div>

        <div className="play-hud-points">
          <Award size={14} />
          <span>+{q.points} pts</span>
        </div>
      </div>

      {/* Question Progress Bar */}
      <div className="progress play-progress">
        <i
          style={{
            width: `${((i + 1) / quiz.questions.length) * 100}%`,
          }}
        />
      </div>

      {/* Match Timer HUD */}
      <div className={`quiz-timer-card ${isUrgent ? 'urgent' : ''}`} role="timer" aria-label={`${remainingSeconds} seconds remaining`}>
        <div className="timer-left-meta">
          {isUrgent ? <AlertCircle size={16} className="urgent-pulse-icon" /> : <Clock size={16} />}
          <span>TIME REMAINING</span>
        </div>
        <strong className="timer-countdown">{fmtTime(remainingMs)}</strong>
      </div>
      <div className="timer-progress" aria-hidden="true">
        <i
          style={{
            width: `${timerPercent}%`,
          }}
        />
      </div>

      {/* Main Question Card */}
      <div className="card question-card">
        {q.image_url && (
          <div className="q-img-wrap">
            <img className="q-img" src={q.image_url} alt="Question clue" />
          </div>
        )}

        <h2 className="q-text">{q.text}</h2>

        {q.answer_mode === 'options' ? (
          <div className="options-stack">
            {q.options.map((o, idx) => {
              const isSelected = value === String(idx)
              return (
                <button
                  key={idx}
                  disabled={busy || timeExpired}
                  className={`opt-premium ${isSelected ? 'sel' : ''}`}
                  onClick={() => {
                    haptic('tap')
                    setAnswers({ ...answers, [q.id]: String(idx) })
                  }}
                >
                  <span className="opt-letter">{String.fromCharCode(65 + idx)}</span>
                  <span className="opt-label grow">{o}</span>
                  {isSelected && <CheckCircle2 size={18} className="opt-selected-check" />}
                </button>
              )
            })}
          </div>
        ) : (
          <div className="text-answer-box">
            <input
              className="input input-text-answer"
              placeholder="Type your answer here…"
              value={value}
              autoFocus
              disabled={busy || timeExpired}
              onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && value.trim() && next()}
            />
          </div>
        )}
      </div>

      {/* Bottom Action Button */}
      <button
        className="btn block btn-action-next"
        disabled={busy || timeExpired || !value.trim()}
        onClick={next}
      >
        {busy ? (
          <span className="btn-loading-content">Submitting…</span>
        ) : last ? (
          <span className="btn-inner-content">
            <Sparkles size={18} />
            <span>Finish quiz</span>
          </span>
        ) : (
          <span className="btn-inner-content">
            <span>Next question</span>
            <ArrowRight size={18} />
          </span>
        )}
      </button>
    </div>
  )
}
