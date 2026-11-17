import { useState } from 'react'
import { Eye, Image, Link2, Send } from 'lucide-react'
import { api } from '../../api'
import type { BroadcastMessagePayload, BroadcastOutcome } from '../../types'

function isHttpUrl(value: string) {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export default function BroadcastMessage() {
  const [text, setText] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [buttonText, setButtonText] = useState('')
  const [buttonUrl, setButtonUrl] = useState('')
  const [busy, setBusy] = useState<'preview' | 'broadcast' | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const maxLength = imageUrl.trim() ? 1024 : 4096
  const hasButton = Boolean(buttonText.trim() && buttonUrl.trim())
  const valid = Boolean(
    text.trim()
    && text.length <= maxLength
    && (!imageUrl.trim() || isHttpUrl(imageUrl.trim()))
    && (Boolean(buttonText.trim()) === Boolean(buttonUrl.trim()))
    && (!buttonUrl.trim() || isHttpUrl(buttonUrl.trim())),
  )

  const payload: BroadcastMessagePayload = {
    text: text.trim(),
    ...(imageUrl.trim() ? { image_url: imageUrl.trim() } : {}),
    ...(hasButton ? { button_text: buttonText.trim(), button_url: buttonUrl.trim() } : {}),
  }

  const sendPreview = async () => {
    setBusy('preview')
    setMessage(null)
    try {
      await api.admin.previewBroadcast(payload)
      setMessage({ ok: true, text: 'Preview sent to your Telegram private chat.' })
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  const sendBroadcast = async () => {
    setBusy('broadcast')
    setMessage(null)
    try {
      const result: BroadcastOutcome = await api.admin.broadcast(payload)
      setConfirming(false)
      const summary = `${result.sent} of ${result.attempted} messages sent; ${result.failed} failed.`
      const details = result.errors.map((error) => `User ${error.user_id}: ${error.error}`).join(' ')
      setMessage({
        ok: result.failed === 0,
        text: result.failed === 0 ? summary : `${summary}${details ? ` Details: ${details}` : ''}`,
      })
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="broadcast-panel">
      {message && <div className={`notice ${message.ok ? 'ok' : 'err'}`}>{message.text}</div>}

      <div className="card stack">
        <div>
          <label className="broadcast-label" htmlFor="broadcast-message">Message</label>
          <textarea
            id="broadcast-message"
            className="input broadcast-textarea"
            rows={5}
            maxLength={maxLength}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Write an update for your players…"
          />
          <div className="broadcast-hint">
            <span>Sent as plain text in Telegram.</span>
            <span>{text.length}/{maxLength}</span>
          </div>
        </div>

        <div>
          <label className="broadcast-label" htmlFor="broadcast-image"><Image size={15} /> Image URL <span className="muted">(optional)</span></label>
          <input
            id="broadcast-image"
            className="input"
            type="url"
            value={imageUrl}
            onChange={(event) => setImageUrl(event.target.value)}
            placeholder="https://example.com/image.jpg"
          />
          <div className="broadcast-hint"><span>Use a public image URL. Telegram photo captions allow up to 1,024 characters.</span></div>
        </div>

        <div className="broadcast-link-fields">
          <div>
            <label className="broadcast-label" htmlFor="broadcast-button-url"><Link2 size={15} /> Button link <span className="muted">(optional)</span></label>
            <input
              id="broadcast-button-url"
              className="input"
              type="url"
              value={buttonUrl}
              onChange={(event) => setButtonUrl(event.target.value)}
              placeholder="https://example.com"
            />
          </div>
          <div>
            <label className="broadcast-label" htmlFor="broadcast-button-text">Button text <span className="muted">(optional)</span></label>
            <input
              id="broadcast-button-text"
              className="input"
              value={buttonText}
              maxLength={64}
              onChange={(event) => setButtonText(event.target.value)}
              placeholder="e.g. Play now"
            />
          </div>
        </div>
        <p className="broadcast-inline-note">Add both link fields to include an inline Telegram button.</p>

        {confirming && (
          <div className="broadcast-confirm">
            <b>Send this message to all registered app users?</b>
            <span className="small muted">This can’t be undone. Users who have not opened a chat with the bot may not receive it.</span>
            <div className="row">
              <button className="btn ghost grow" disabled={busy !== null} onClick={() => setConfirming(false)}>Cancel</button>
              <button className="btn grow" disabled={!valid || busy !== null} onClick={sendBroadcast}>
                <Send size={15} /> {busy === 'broadcast' ? 'Sending…' : 'Confirm broadcast'}
              </button>
            </div>
          </div>
        )}

        {!confirming && (
          <div className="broadcast-actions">
            <button className="btn ghost" disabled={!valid || busy !== null} onClick={sendPreview}>
              <Eye size={16} /> {busy === 'preview' ? 'Sending preview…' : 'Send preview to me'}
            </button>
            <button className="btn" disabled={!valid || busy !== null} onClick={() => { setMessage(null); setConfirming(true) }}>
              <Send size={16} /> Broadcast to all
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
