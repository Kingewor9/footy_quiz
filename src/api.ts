import { initData } from './telegram'
import type { AdminQuiz, Analytics, Board, Channel, CreateOutcome, DiscoverChannels, Me, QuizPayload, QuizResult, QuizSummary, StartedQuiz, WinnerCardData, WinnerCardDay } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Only used by `npm run dev` outside Telegram (backend needs DEV_MODE=1).
const DEV_USER = JSON.stringify({ id: 1001, first_name: 'Dev', last_name: 'User', username: 'devuser' })

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (initData) headers.Authorization = `tma ${initData}`
  else if (import.meta.env.DEV) headers['X-Dev-User'] = DEV_USER
  const res = await fetch(`/api${path}`, { ...init, headers })
  if (!res.ok) {
    let detail = 'Something went wrong. Try again.'
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') detail = j.detail
      else if (Array.isArray(j.detail)) detail = j.detail.map((d: { msg?: string }) => (d.msg ?? '').replace(/^Value error, /, '')).join(' ')
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body?: unknown) => req<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  me: () => req<Me>('/me'),
  quizzes: () => req<QuizSummary[]>('/quizzes'),
  start: (id: string) => post<StartedQuiz>(`/quizzes/${id}/start`),
  submit: (id: string, answers: Record<string, string>) => post<QuizResult>(`/quizzes/${id}/submit`, { answers }),
  result: (id: string) => req<QuizResult>(`/quizzes/${id}/result`),
  boost: (id: string) => post<QuizResult>(`/quizzes/${id}/boost`),
  leaderboard: () => req<Board>('/leaderboard'),
  channels: () => req<Channel[]>('/channels'),
  discoverChannels: () => req<DiscoverChannels>('/discover/channels'),
  channelLeaderboard: (id: string) => req<Board>(`/channels/${encodeURIComponent(id)}/leaderboard`),
  connectableChannel: (username: string) => req<Pick<Channel, 'id' | 'title' | 'username'> & { bot_username?: string }>(`/admin/channels/lookup?username=${encodeURIComponent(username)}`),
  admin: {
    channels: () => req<Channel[]>('/admin/channels'),
    connectChannel: (username: string) => post<Pick<Channel, 'id' | 'title' | 'username'> & { already_connected: boolean; migrated_quizzes?: number }>('/admin/channels', { username }),
    quizzes: (channelId?: string) => req<AdminQuiz[]>(`/admin/quizzes${channelId ? `?channel_id=${encodeURIComponent(channelId)}` : ''}`),
    create: (body: QuizPayload) => post<CreateOutcome>('/admin/quizzes', body),
    publish: (id: string) => post<CreateOutcome>(`/admin/quizzes/${id}/publish`),
    cancel: (id: string) => req<{ ok: boolean }>(`/admin/quizzes/${id}`, { method: 'DELETE' }),
    analytics: () => req<Analytics>('/admin/analytics'),
    winnerDays: (channelId?: string) => req<WinnerCardDay[]>(`/admin/winner-card/days${channelId ? `?channel_id=${encodeURIComponent(channelId)}` : ''}`),
    winnerCard: (day?: string, channelId?: string) => {
      const params = new URLSearchParams()
      if (day) params.set('day', day)
      if (channelId) params.set('channel_id', channelId)
      return req<WinnerCardData>(`/admin/winner-card${params.size ? `?${params}` : ''}`)
    },
    saveWinnerDraft: (day: string, caption?: string, channelId?: string) => post<{ ok: boolean; day: string; status: string }>('/admin/winner-card/save-draft', { day, caption, channel_id: channelId }),
    postWinnerCard: (day: string, caption?: string, channelId?: string) => post<{ ok: boolean; day: string; status: string; sent_at?: string }>('/admin/winner-card/post', { day, caption, channel_id: channelId }),
  },
}

export const fmtTime = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000))
  return s >= 60 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`
}
