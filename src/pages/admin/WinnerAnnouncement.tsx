import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, FileEdit, Send, Trophy } from 'lucide-react'
import { api, fmtTime } from '../../api'
import type { WinnerCardData, WinnerCardDay } from '../../types'

export default function WinnerAnnouncement() {
  const [days, setDays] = useState<WinnerCardDay[]>([])
  const [selectedDay, setSelectedDay] = useState<string>('')
  const [data, setData] = useState<WinnerCardData | null>(null)
  const [caption, setCaption] = useState('')
  const [loading, setLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState<'draft' | 'post' | null>(null)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const loadDays = useCallback(async () => {
    try {
      const list = await api.admin.winnerDays()
      setDays(list)
      if (list.length > 0 && !selectedDay) {
        setSelectedDay(list[0].day)
      }
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    }
  }, [selectedDay])

  useEffect(() => {
    loadDays()
  }, [loadDays])

  const loadCard = useCallback(async (dayKey: string) => {
    if (!dayKey) return
    setLoading(true)
    setMsg(null)
    try {
      const res = await api.admin.winnerCard(dayKey)
      setData(res)
      setCaption(res.caption || '')
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedDay) {
      loadCard(selectedDay)
    }
  }, [selectedDay, loadCard])

  const handleSaveDraft = async () => {
    if (!selectedDay) return
    setActionBusy('draft')
    setMsg(null)
    try {
      await api.admin.saveWinnerDraft(selectedDay, caption)
      setMsg({ ok: true, text: 'Winner announcement saved as draft.' })
      loadCard(selectedDay)
      loadDays()
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    } finally {
      setActionBusy(null)
    }
  }

  const handlePostNow = async () => {
    if (!selectedDay) return
    setActionBusy('post')
    setMsg(null)
    try {
      await api.admin.postWinnerCard(selectedDay, caption)
      setMsg({ ok: true, text: 'Winner card and announcement posted to Telegram channel successfully!' })
      loadCard(selectedDay)
      loadDays()
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message })
    } finally {
      setActionBusy(null)
    }
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      {msg && <div className={`notice ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</div>}

      <div className="card stack">
        <div className="row between" style={{ alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Trophy size={18} style={{ color: 'var(--gold, #facc15)' }} />
              <span>Select Concluded Day</span>
            </div>
            <div className="small muted" style={{ marginTop: 2 }}>
              Choose a finished 24h leaderboard period to generate its winner card.
            </div>
          </div>
          {days.length > 0 && (
            <select
              className="input"
              value={selectedDay}
              onChange={(e) => setSelectedDay(e.target.value)}
              style={{ width: 'auto', minWidth: 160 }}
            >
              {days.map((d, i) => (
                <option key={d.day} value={d.day}>
                  {i === 0 ? `Yesterday (${d.label})` : d.label} {d.status === 'sent' ? '✓' : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        {days.length > 0 && (
          <div className="seg" style={{ marginTop: 8 }}>
            {days.slice(0, 4).map((d, i) => (
              <button
                key={d.day}
                className={selectedDay === d.day ? 'on' : ''}
                onClick={() => setSelectedDay(d.day)}
                style={{ fontSize: '0.8rem', padding: '6px 8px' }}
              >
                {i === 0 ? 'Yesterday' : d.day.slice(5)}
                {d.status === 'sent' ? ' (Sent)' : d.status === 'draft' ? ' (Draft)' : ''}
              </button>
            ))}
          </div>
        )}
      </div>

      {days.length === 0 && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 24 }}>
          <div className="small muted">No concluded leaderboard days are available yet.</div>
        </div>
      )}

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: 32 }}>
          <div className="spinner-ring" />
          <div className="small muted" style={{ marginTop: 12 }}>Generating winner card & standings…</div>
        </div>
      )}

      {!loading && data && !data.has_data && (
        <div className="card" style={{ textAlign: 'center', padding: 32 }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>No quiz plays recorded</div>
          <div className="small muted" style={{ marginTop: 6 }}>
            {data.message || `No players completed a quiz on ${data.day_label}.`}
          </div>
        </div>
      )}

      {!loading && data && data.has_data && data.winner && (
        <>
          <div className="card stack">
            <div className="row between" style={{ alignItems: 'center' }}>
              <div>
                <b style={{ fontSize: '1.05rem' }}>{data.day_label}</b>
                <div className="small muted">
                  {data.players} player{data.players !== 1 ? 's' : ''} participated
                </div>
              </div>
              <div>
                {data.status === 'sent' ? (
                  <span className="chip green" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <CheckCircle2 size={13} /> Posted to channel
                  </span>
                ) : data.status === 'draft' ? (
                  <span className="chip" style={{ background: 'rgba(234, 179, 8, 0.15)', color: '#facc15' }}>
                    Draft saved
                  </span>
                ) : (
                  <span className="chip muted">Ready to post</span>
                )}
              </div>
            </div>

            {/* Top 3 Podium summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8, marginTop: 8 }}>
              <div className="qcard" style={{ padding: 10, background: 'rgba(234, 179, 8, 0.08)', borderColor: 'rgba(234, 179, 8, 0.25)' }}>
                <div className="small" style={{ color: '#facc15', fontWeight: 700 }}>🥇 1st Place (Winner)</div>
                <div style={{ fontWeight: 600, fontSize: '0.95rem', marginTop: 2 }}>{data.winner.name}</div>
                <div className="small muted">{data.winner.points} pts · {fmtTime(data.winner.time_ms)}</div>
              </div>

              {data.second && (
                <div className="qcard" style={{ padding: 10 }}>
                  <div className="small muted" style={{ fontWeight: 700 }}>🥈 2nd Place</div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', marginTop: 2 }}>{data.second.name}</div>
                  <div className="small muted">{data.second.points} pts · {fmtTime(data.second.time_ms)}</div>
                </div>
              )}

              {data.third && (
                <div className="qcard" style={{ padding: 10 }}>
                  <div className="small muted" style={{ fontWeight: 700 }}>🥉 3rd Place</div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', marginTop: 2 }}>{data.third.name}</div>
                  <div className="small muted">{data.third.points} pts · {fmtTime(data.third.time_ms)}</div>
                </div>
              )}
            </div>
          </div>

          {/* Winner Card Preview */}
          {data.card_image && (
            <div className="card stack">
              <b>Winner Card Preview</b>
              <div style={{ textAlign: 'center', marginTop: 4 }}>
                <img
                  src={data.card_image}
                  alt={`Winner Card for ${data.day_label}`}
                  style={{
                    maxWidth: '100%',
                    maxHeight: 460,
                    borderRadius: 12,
                    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                />
              </div>
            </div>
          )}

          {/* Caption text editor */}
          <div className="card stack">
            <label htmlFor="caption-editor">
              <b>Channel Caption</b>
              <span className="small muted" style={{ marginLeft: 6 }}>
                (Attached to photo post)
              </span>
            </label>
            <textarea
              id="caption-editor"
              className="input"
              rows={4}
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Post caption…"
              style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.4 }}
            />

            <div className="row" style={{ gap: 10, marginTop: 10 }}>
              <button
                className="btn ghost grow"
                disabled={actionBusy !== null || data.status === 'sent'}
                onClick={handleSaveDraft}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
              >
                <FileEdit size={16} />
                <span>{actionBusy === 'draft' ? 'Saving…' : 'Save to draft'}</span>
              </button>
              <button
                className="btn grow"
                disabled={actionBusy !== null || data.status === 'sent'}
                onClick={handlePostNow}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
              >
                <Send size={16} />
                <span>{data.status === 'sent' ? 'Already posted' : actionBusy === 'post' ? 'Posting to Telegram…' : 'Post now'}</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

