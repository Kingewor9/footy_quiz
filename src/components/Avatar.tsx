import { useState } from 'react'

const COLORS = ['#5a6cf0', '#e0557d', '#2fa56b', '#d98a1f', '#8a56d9', '#2b9bb8']

export default function Avatar({ name, url, size = 44 }: { name: string; url?: string | null; size?: number }) {
  const [broken, setBroken] = useState(false)
  const style = { width: size, height: size, fontSize: size * 0.4 }
  if (url && !broken) return <img className="avatar" style={style} src={url} alt="" onError={() => setBroken(true)} />
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?'
  const color = COLORS[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % COLORS.length]
  return (
    <div className="avatar" style={{ ...style, background: color }} aria-hidden>
      {initials}
    </div>
  )
}
