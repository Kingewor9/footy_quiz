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
  const [when, setWhen] = useState<'now' | 'later'>('now')
  const [at, setAt] = useState('')
  const [qs, setQs] = useState<Draft[]>([blank()])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [recent, setRecent] = useState<AdminQuiz[]>([])

  const loadRecent = useCallback(() => {
    api.admin.quizzes().then(setRecent).catch(() => undefined)
  }, [])
  useEffect(loadRecent, [loadRecent])

  const submit = async () => {
    setMsg(null)
    if (!title.trim()) return setMsg({ ok: false, text: 'Give the quiz a title.' })
    if (when === 'later' && (!at || new Date(at).getTime() <= Date.now())) return setMsg({ ok: false, text: 'Pick a future date and time.' })
    setBusy(true)
    try {
      const r = await api.admin.create({
        title: title.trim(),
        scheduled_at: when === 'later' ? new Date(at).toISOString() : null,
        questions: qs.map(toPayload),
      })
      if (r.status === 'scheduled') setMsg({ ok: true, text: `Scheduled for ${new Date(r.scheduled_at!).toLocaleString()}.` })
      else if (r.notified) setMsg({ ok: true, text: 'Quiz is live and posted in the channel.' })
      else setMsg({ ok: false, text: `Quiz is live, but the channel post failed: ${r.error}` })
      setTitle('')
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
        <div className="seg">
          <button className={when === 'now' ? 'on' : ''} onClick={() => setWhen('now')}>Send now</button>
          <button className={when === 'later' ? 'on' : ''} onClick={() => setWhen('later')}>Schedule</button>
        </div>
        {when === 'later' && <input className="input" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />}
      </div>

      {qs.map((d, i) => (
        <QuestionEditor key={d.key} n={i + 1} d={d} canRemove={qs.length > 1} onChange={(nd) => setQs(qs.map((x) => (x.key === d.key ? nd : x)))} onRemove={() => setQs(qs.filter((x) => x.key !== d.key))} />
      ))}
      {qs.length < 30 && <button className="btn ghost block" style={{ marginBottom: 12 }} onClick={() => setQs([...qs, blank()])}>Add question</button>}
      <button className="btn block" disabled={busy} onClick={submit}>{busy ? 'Working…' : when === 'now' ? 'Send quiz' : 'Schedule quiz'}</button>

      {recent.length > 0 && (
        <>
          <h2>Recent quizzes</h2>
          {recent.map((q) => (
            <div className="card row" key={q.id}>
              <div className="grow">
                <div className="name">{q.title}</div>
                <div className="small muted">
                  {q.status === 'scheduled' ? `Scheduled ${new Date(q.scheduled_at!).toLocaleString()}` : `${q.players} player${q.players !== 1 ? 's' : ''}`}
                </div>
                {q.notify_error && <div className="small" style={{ color: 'var(--red)' }}>Not posted: {q.notify_error}</div>}
              </div>
              {q.status === 'scheduled' ? (
                <button className="link" onClick={() => api.admin.cancel(q.id).then(loadRecent)}>Cancel</button>
              ) : (
                <span className="chip green">Live</span>
              )}
            </div>
          ))}
        </>
      )}
    </>
  )
}
