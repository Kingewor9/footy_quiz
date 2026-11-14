import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api'
import type { AdminQuiz, QuestionPayload } from '../../types'

type QType = 'poll' | 'text' | 'image'
interface Draft {
  key: number
  type: QType
  text: string
  image_url: string
  answer_mode: 'options' | 'text'
  options: string[]
  correct: number
  accepted: string
  points: number
}

let keySeq = 0
const blank = (): Draft => ({ key: ++keySeq, type: 'poll', text: '', image_url: '', answer_mode: 'options', options: ['', '', '', ''], correct: 0, accepted: '', points: 10 })
const TYPES: [QType, string][] = [['poll', 'Poll'], ['text', 'Text answer'], ['image', 'Image']]

function toPayload(d: Draft): QuestionPayload {
  const mode = d.type === 'poll' ? 'options' : d.type === 'text' ? 'text' : d.answer_mode
  return {
    type: d.type,
    text: d.text.trim(),
    image_url: d.type === 'image' ? d.image_url.trim() : undefined,
    answer_mode: mode,
    options: mode === 'options' ? d.options.map((o) => o.trim()) : [],
    correct_index: mode === 'options' ? d.correct : undefined,
    accepted: mode === 'text' ? d.accepted.split(',').map((a) => a.trim()).filter(Boolean) : [],
    points: d.points,
  }
}

function QuestionEditor({ n, d, onChange, onRemove, canRemove }: { n: number; d: Draft; onChange: (d: Draft) => void; onRemove: () => void; canRemove: boolean }) {
  const set = (p: Partial<Draft>) => onChange({ ...d, ...p })
  const mode = d.type === 'poll' ? 'options' : d.type === 'text' ? 'text' : d.answer_mode
  return (
    <div className="qcard stack">
      <div className="row between">
        <b>Question {n}</b>
        {canRemove && <button className="link" onClick={onRemove}>Remove</button>}
      </div>
      <div className="seg" role="tablist">
        {TYPES.map(([t, label]) => (
          <button key={t} className={d.type === t ? 'on' : ''} onClick={() => set({ type: t })}>{label}</button>
        ))}
      </div>
      {d.type === 'image' && (
        <div className="field">
          <label>Image link</label>
          <input className="input" inputMode="url" placeholder="https://…/photo.jpg" value={d.image_url} onChange={(e) => set({ image_url: e.target.value })} />
        </div>
      )}
      <div className="field">
        <label>Question</label>
        <input className="input" placeholder="Who won the 2014 Golden Boot?" value={d.text} onChange={(e) => set({ text: e.target.value })} />
      </div>
      {d.type === 'image' && (
        <div className="seg">
          <button className={mode === 'options' ? 'on' : ''} onClick={() => set({ answer_mode: 'options' })}>Options</button>
          <button className={mode === 'text' ? 'on' : ''} onClick={() => set({ answer_mode: 'text' })}>Typed answer</button>
        </div>
      )}
      {mode === 'options' ? (
        <div className="field stack">
          <label>Options (tap the circle to mark the correct one)</label>
          {d.options.map((o, i) => (
            <div className="opt-edit" key={i}>
              <button className={`radio ${d.correct === i ? 'on' : ''}`} onClick={() => set({ correct: i })} aria-label={`Mark option ${i + 1} correct`}>✓</button>
              <input className="input" placeholder={`Option ${i + 1}`} value={o} onChange={(e) => set({ options: d.options.map((x, j) => (j === i ? e.target.value : x)) })} />
            </div>
          ))}
          <div className="row">
            {d.options.length < 6 && <button className="link" onClick={() => set({ options: [...d.options, ''] })}>Add option</button>}
            {d.options.length > 2 && (
              <button className="link" onClick={() => set({ options: d.options.slice(0, -1), correct: Math.min(d.correct, d.options.length - 2) })}>Remove last</button>
            )}
          </div>
        </div>
      ) : (
        <div className="field">
          <label>Accepted answers (separate alternatives with commas)</label>
          <input className="input" placeholder="James Rodriguez, Rodriguez" value={d.accepted} onChange={(e) => set({ accepted: e.target.value })} />
        </div>
      )}
      <div className="field">
        <label>Points for a correct answer</label>
        <input className="input" type="number" min={1} max={1000} value={d.points} onChange={(e) => set({ points: Number(e.target.value) })} />
      </div>
    </div>
  )
}

export default function SendQuiz() {
  const [title, setTitle] = useState('')
  const [maxSeconds, setMaxSeconds] = useState(60)
  const [expiresHours, setExpiresHours] = useState(24)
  const [mode, setMode] = useState<'live' | 'draft'>('live')
  const [qs, setQs] = useState<Draft[]>([blank()])
  const [busy, setBusy] = useState(false)
  const [publishingId, setPublishingId] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [recent, setRecent] = useState<AdminQuiz[]>([])

  const loadRecent = useCallback(() => {
    api.admin.quizzes().then(setRecent).catch(() => undefined)
  }, [])
  useEffect(loadRecent, [loadRecent])

  const handlePublish = async (id: string) => {
    setPublishingId(id)
    setMsg(null)
    try {
      const res = await api.admin.publish(id)
      if (res.notified) {
        setMsg({ ok: true, text: 'Quiz is live and announced on the channel!' })
      } else {
        setMsg({ ok: false, text: `Quiz is live, but channel post failed: ${res.error}` })
      }
      loadRecent()
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    } finally {
      setPublishingId(null)
    }
  }

  const submit = async () => {
    setMsg(null)
    if (!title.trim()) return setMsg({ ok: false, text: 'Give the quiz a title.' })
    if (!Number.isInteger(maxSeconds) || maxSeconds < 1 || maxSeconds > 3600) return setMsg({ ok: false, text: 'Set a time limit from 1 to 3600 whole seconds.' })
    if (!Number.isInteger(expiresHours) || expiresHours < 1 || expiresHours > 720) return setMsg({ ok: false, text: 'Set an expiration between 1 and 720 hours.' })
    setBusy(true)
    try {
      const r = await api.admin.create({
        title: title.trim(),
        max_seconds: maxSeconds,
        expires_hours: expiresHours,
        status: mode,
        questions: qs.map(toPayload),
      })
      if (r.status === 'draft') setMsg({ ok: true, text: 'Quiz saved as draft. You can post it anytime below.' })
      else if (r.notified) setMsg({ ok: true, text: 'Quiz is live and posted in the channel.' })
      else setMsg({ ok: false, text: `Quiz is live, but the channel post failed: ${r.error}` })
      setTitle('')
      setMaxSeconds(60)
      setExpiresHours(24)
      setQs([blank()])
      loadRecent()
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    }
    setBusy(false)
  }

  return (
    <>
      {msg && <div className={`notice ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</div>}
      <div className="qcard stack">
        <div className="field">
          <label>Quiz title</label>
          <input className="input" placeholder="Matchday trivia" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="quiz-time-limit">Time limit in seconds (1–3600)</label>
          <input id="quiz-time-limit" className="input" type="number" min={1} max={3600} step={1} required value={maxSeconds} onChange={(e) => setMaxSeconds(Number(e.target.value))} />
        </div>
        <div className="field">
          <label htmlFor="quiz-expires-hours">Expiration in hours (e.g. 24)</label>
          <input id="quiz-expires-hours" className="input" type="number" min={1} max={720} step={1} required value={expiresHours} onChange={(e) => setExpiresHours(Number(e.target.value))} />
        </div>
        <div className="seg">
          <button className={mode === 'live' ? 'on' : ''} onClick={() => setMode('live')}>Send now</button>
          <button className={mode === 'draft' ? 'on' : ''} onClick={() => setMode('draft')}>Save as draft</button>
        </div>
      </div>

      {qs.map((d, i) => (
        <QuestionEditor key={d.key} n={i + 1} d={d} canRemove={qs.length > 1} onChange={(nd) => setQs(qs.map((x) => (x.key === d.key ? nd : x)))} onRemove={() => setQs(qs.filter((x) => x.key !== d.key))} />
      ))}
      {qs.length < 30 && <button className="btn ghost block" style={{ marginBottom: 12 }} onClick={() => setQs([...qs, blank()])}>Add question</button>}
      <button className="btn block" disabled={busy} onClick={submit}>{busy ? 'Working…' : mode === 'live' ? 'Send quiz now' : 'Save as draft'}</button>

      {recent.length > 0 && (
        <>
          <h2 style={{ marginTop: 28 }}>Recent quizzes & drafts</h2>
          {recent.map((q) => (
            <div className="card row" key={q.id}>
              <div className="grow">
                <div className="row" style={{ alignItems: 'center', gap: 8 }}>
                  <span className="name">{q.title}</span>
                  {q.status === 'draft' && (
                    <span className="chip" style={{ background: 'rgba(234, 179, 8, 0.15)', color: '#facc15', fontSize: '0.72rem', padding: '2px 8px' }}>
                      Draft
                    </span>
                  )}
                  {q.status === 'live' && (
                    <span className="chip green" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
                      Live
                    </span>
                  )}
                </div>
                <div className="small muted" style={{ marginTop: 2 }}>
                  {q.status === 'draft'
                    ? 'Draft · not published yet'
                    : q.status === 'scheduled'
                      ? 'Previously scheduled · ready to post manually'
                      : `${q.players} player${q.players !== 1 ? 's' : ''}`}
                  {' · '}{q.max_seconds}s limit{' · '}{q.expires_hours ?? 24}h expiry
                </div>
                {q.notify_error && <div className="small" style={{ color: 'var(--red)', marginTop: 2 }}>Not posted: {q.notify_error}</div>}
              </div>
              {q.status === 'draft' || q.status === 'scheduled' ? (
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <button
                    className="btn small"
                    disabled={publishingId === q.id}
                    onClick={() => handlePublish(q.id)}
                    style={{ minWidth: 80, padding: '6px 12px' }}
                  >
                    {publishingId === q.id ? 'Posting…' : 'Post now'}
                  </button>
                  <button className="link" onClick={() => api.admin.cancel(q.id).then(loadRecent)}>
                    Delete
                  </button>
                </div>
              ) : (
                <span className="small muted">Active</span>
              )}
            </div>
          ))}
        </>
      )}
    </>
  )
}
