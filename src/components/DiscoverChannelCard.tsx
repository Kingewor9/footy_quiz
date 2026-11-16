import { ArrowUpRight, Radio } from 'lucide-react'
import type { DiscoverChannel } from '../types'
import ChannelMark from './ChannelMark'

export default function DiscoverChannelCard({ channel }: { channel: DiscoverChannel }) {
  const content = (
    <>
      <ChannelMark channel={channel} />
      <span className="grow discover-channel-copy">
        <b>{channel.title}</b>
        <small>{channel.username ? `@${channel.username}` : 'Public channel'}</small>
      </span>
      <span className="discover-quiz-count"><Radio size={13} /> {channel.quizzes_today} {channel.quizzes_today === 1 ? 'quiz' : 'quizzes'} today</span>
      {channel.username && <ArrowUpRight size={17} className="discover-open-icon" aria-hidden="true" />}
    </>
  )

  if (!channel.username) {
    return <div className="card discover-channel-row">{content}</div>
  }

  return (
    <a
      className="card discover-channel-row"
      href={`https://t.me/${channel.username}`}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open ${channel.title} on Telegram`}
    >
      {content}
    </a>
  )
}
