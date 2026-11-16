import { useMemo, useState } from 'react'
import { Compass, Search } from 'lucide-react'
import DiscoverChannelCard from '../components/DiscoverChannelCard'
import useDiscoverChannels from '../hooks/useDiscoverChannels'

export default function Discover() {
  const [query, setQuery] = useState('')
  const { data, error } = useDiscoverChannels()
  const channels = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    if (!normalized) return data?.channels ?? []
    return (data?.channels ?? []).filter((channel) =>
      `${channel.title} ${channel.username ?? ''}`.toLocaleLowerCase().includes(normalized),
    )
  }, [data, query])

  return (
    <div className="page discover-page">
      <header className="discover-heading">
        <span className="eyebrow"><Compass size={13} /> OPEN LEAGUES</span>
        <h1>Discover channels</h1>
        <p className="sub">Find today’s live quiz leagues and join the channels playing them.</p>
      </header>

      <label className="discover-search">
        <Search size={18} aria-hidden="true" />
        <input
          type="search"
          aria-label="Search public channel leagues"
          placeholder="Search channels"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>

      {error && <div className="notice err">{error} We’ll try again shortly.</div>}
      {!data && !error && <div className="card home-leagues-empty"><div className="spinner-ring sm" /><span className="small muted">Finding today’s active leagues…</span></div>}
      {data && channels.length === 0 && (
        <div className="empty empty-state-box">
          <Compass size={30} className="muted" />
          <p>{query ? 'No channels match that search.' : 'No public quizzes are live today yet.'}</p>
          <span className="small muted">{query ? 'Try another channel name or username.' : 'Channels appear here as soon as they post a quiz.'}</span>
        </div>
      )}
      {channels.map((channel) => <DiscoverChannelCard key={channel.id} channel={channel} />)}
      <div className="channel-powered">Updated daily at midnight</div>
    </div>
  )
}
