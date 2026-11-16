import { useEffect, useState } from 'react'
import { api } from '../api'
import type { DiscoverChannels } from '../types'

export default function useDiscoverChannels() {
  const [data, setData] = useState<DiscoverChannels | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>

    const load = () => {
      api.discoverChannels().then((result) => {
        if (!active) return
        setData(result)
        setError('')
        const untilReset = new Date(result.resets_at).getTime() - Date.now() + 1000
        timer = setTimeout(load, Math.max(untilReset, 1000))
      }).catch((e: Error) => {
        if (!active) return
        setError(e.message)
        timer = setTimeout(load, 60_000)
      })
    }

    load()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [])

  return { data, error }
}
