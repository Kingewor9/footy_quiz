import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, ChevronRight, Radio, Search, ShieldCheck } from 'lucide-react'
import { api } from '../api'
import type { Channel } from '../types'
import ChannelMark from '../components/ChannelMark'

export default function Channels({ onManage }: { onManage: (channel: Channel) => void }) {
  const [channels, setChannels] = useState<Channel[]>([])
  const [username, setUsername] = useState('')
  const [found, setFound] = useState<(Pick<Channel, 'id' | 'title' | 'username'> & { bot_username?: string }) | null>(null)
  const [busy, setBusy] = useState<'search' | 'connect' | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const loadChannels = useCallback(() => {
    api.admin.channels().then(setChannels).catch((e) => setMessage({ ok: false, text: e.message }))
  }, [])

  useEffect(loadChannels, [loadChannels])

  const search = async () => {
    setBusy('search')
    setMessage(null)
    setFound(null)
    try {
      setFound(await api.connectableChannel(username.trim()))
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  const connect = async () => {
    if (!found) return
    setBusy('connect')
    setMessage(null)
    try {
      const result = await api.admin.connectChannel(username.trim())
      const text = result.migrated_quizzes
        ? `${result.already_connected ? 'Channel verified.' : 'Channel connected.'} ${result.migrated_quizzes} existing quiz${result.migrated_quizzes === 1 ? '' : 'zes'} moved into its league.`
        : result.already_connected
          ? 'This channel is already connected to your account.'
          : 'Channel verified and connected.'
      setMessage({ ok: true, text })
      setFound(null)
      setUsername('')
      loadChannels()
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="page channels-page">
      <header className="channels-heading">
        <span className="eyebrow"><Radio size={13} /> CREATOR NETWORK</span>
        <h1>Your channels</h1>
        <p className="sub">Give your community its own daily quiz league.</p>
      </header>

      {message && <div className={`notice ${message.ok ? 'ok' : 'err'}`}>{message.text}</div>}

      <section className="card channel-connect-card">
        <div className="channel-section-title">
          <div className="channel-icon"><Search size={18} /></div>
          <div><b>Connect a channel</b><div className="small muted">Search by its public Telegram username.</div></div>
        </div>
        <div className="channel-search-row">
          <input
            className="input"
            aria-label="Public channel username"
            placeholder="@yourchannel"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') search() }}
          />
          <button className="btn channel-search-button" disabled={busy !== null || !username.trim()} onClick={search}>
            {busy === 'search' ? 'Searching…' : 'Find'}
          </button>
        </div>
        <p className="channel-permission-note">
          Before connecting, add <b>{found?.bot_username ? `@${found.bot_username}` : 'the quiz bot'}</b> as a channel administrator with permission to post messages. You must also be a channel admin.
        </p>

        {found && (
          <div className="channel-found-card">
            <ChannelMark channel={found} />
            <div className="grow">
              <b>{found.title}</b>
              <div className="small muted">@{found.username}</div>
            </div>
            <a className="link" href={`https://t.me/${found.username}`} target="_blank" rel="noreferrer">Open <ArrowRight size={14} /></a>
            <button className="btn sm" disabled={busy !== null} onClick={connect}>
              <ShieldCheck size={15} /> {busy === 'connect' ? 'Verifying…' : 'Verify & connect'}
            </button>
          </div>
        )}
      </section>

      <div className="section-header-row channels-list-heading">
        <div><h2>Connected channels</h2><span className="small muted">Quizzes, drafts and winner cards live inside each channel.</span></div>
        <span className="count-bubble">{channels.length}</span>
      </div>

      {channels.length === 0 ? (
        <div className="empty empty-state-box">
          <Radio size={30} className="muted" />
          <p>No channels connected yet</p>
          <span className="small muted">Connect a public channel to create its first quiz league.</span>
        </div>
      ) : channels.map((channel) => (
        <button className="channel-row card" key={channel.id} onClick={() => onManage(channel)}>
          <ChannelMark channel={channel} />
          <div className="grow channel-row-copy">
            <b>{channel.title}</b>
            <span className="small muted">@{channel.username}</span>
          </div>
          <span className="channel-manage-label">Manage</span>
          <ChevronRight size={18} className="muted" />
        </button>
      ))}

      <div className="channel-powered">Powered By Footy Quiz</div>
    </div>
  )
}
