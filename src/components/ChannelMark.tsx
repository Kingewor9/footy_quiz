import { useState } from 'react'
import type { Channel } from '../types'

export default function ChannelMark({ channel }: { channel: Pick<Channel, 'id' | 'title' | 'logo_url'> }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className="channel-monogram channel-mark" aria-label={`${channel.title} logo`}>
      {channel.logo_url && !failed && <img className="channel-mark-image" src={channel.logo_url} alt="" onError={() => setFailed(true)} />}
      {(!channel.logo_url || failed) && channel.title.slice(0, 1).toUpperCase()}
    </span>
  )
}
