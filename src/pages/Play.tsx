import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, fmtTime } from '../api'
import ScoreCard from '../components/ScoreCard'
import { haptic } from '../telegram'
import type { QuizResult, StartedQuiz } from '../types'

export default function Play({ quizId, onExit, onLeaderboard }: { quizId: string; onExit: () => void; onLeaderboard: () => void }) {
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

  const finish = useCallback(async (final: Record<string, string>) => {
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
  }, [quizId])

  useEffect(() => {
    if (quiz && !result && elapsed >= quiz.max_seconds * 1000) {
      void finish(answersRef.current)
    }
  }, [elapsed, finish, quiz, result])

  if (err)
    return (
      <div className="page play">
        <div className="notice err">{err}</div>
        <button className="btn block" onClick={onExit}>Back home</button>
      </div>
    )
  if (result)
    return (
      <div className="page play">
        <ScoreCard r={result} onHome={onExit} onLeaderboard={onLeaderboard} />
      </div>
    )
  if (!quiz) return <div className="center muted">Loading quiz…</div>

  const q = quiz.questions[i]
  const value = answers[q.id] ?? ''
  const last = i === quiz.questions.length - 1
  const next = () => (last ? finish(answers) : setI(i + 1))
  const remainingMs = Math.max(0, quiz.max_seconds * 1000 - elapsed)
  const remainingSeconds = Math.ceil(remainingMs / 1000)
  const timerPercent = (remainingMs / (quiz.max_seconds * 1000)) * 100
  const timeExpired = remainingMs === 0

  return (
    <div className="page play">
      <div className="row between small muted" style={{ marginBottom: 8 }}>
        <span>Question {i + 1} of {quiz.questions.length}</span>
        <span>{q.points} pts</span>
      </div>
      <div className="progress"><i style={{ width: `${((i + 1) / quiz.questions.length) * 100}%` }} /></div>

      <div className={`quiz-timer ${remainingSeconds <= 10 ? 'urgent' : ''}`} role="timer" aria-label={`${remainingSeconds} seconds remaining`}>
        <span>TIME LEFT</span>
        <strong>{fmtTime(remainingMs)}</strong>
      </div>
      <div className="timer-progress" aria-hidden="true">
        <i style={{ width: `${timerPercent}%` }} />
      </div>

      <div style={{ marginTop: 18 }}>
        {q.image_url && <img className="q-img" src={q.image_url} alt="" />}
        <div className="q-text">{q.text}</div>

        {q.answer_mode === 'options' ? (
          q.options.map((o, idx) => (
            <button key={idx} disabled={busy || timeExpired} className={`opt ${value === String(idx) ? 'sel' : ''}`} onClick={() => { haptic('tap'); setAnswers({ ...answers, [q.id]: String(idx) }) }}>
              <i>{String.fromCharCode(65 + idx)}</i>
              {o}
            </button>
          ))
        ) : (
          <input
            className="input"
            placeholder="Type your answer"
            value={value}
            autoFocus
            disabled={busy || timeExpired}
            onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && value.trim() && next()}
          />
        )}
      </div>

      <button className="btn block" style={{ marginTop: 14 }} disabled={busy || timeExpired || !value.trim()} onClick={next}>
        {busy ? 'Submitting…' : last ? 'Finish quiz' : 'Next question'}
      </button>
    </div>
  )
}
