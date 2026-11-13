export interface Player {
  id: number
  name: string
  username?: string | null
  photo_url?: string | null
}
export interface Me {
  user: Player
  is_admin: boolean
  today: { rank: number | null; points: number; players: number }
}
export interface QuizSummary {
  id: string
  title: string
  question_count: number
  total_points: number
  max_seconds: number
  expires_hours?: number
  posted_at: string
  played: boolean
  score: number | null
}
export interface Question {
  id: string
  type: 'poll' | 'text' | 'image'
  text: string
  image_url?: string | null
  answer_mode: 'options' | 'text'
  options: string[]
  points: number
}
export interface StartedQuiz {
  id: string
  title: string
  questions: Question[]
  max_seconds: number
  elapsed_ms: number
}
export interface QuestionResult {
  id: string
  text: string
  correct: boolean
  points: number
  max: number
  your_answer: string
  correct_answer: string
}
export interface QuizResult {
  quiz_id: string
  title: string
  points: number
  max_points: number
  correct_count: number
  total: number
  time_ms: number
  results: QuestionResult[]
  rank: number | null
  players: number
  boosted?: boolean
}
export interface BoardRow {
  rank: number
  user_id: number
  name: string
  username?: string | null
  photo_url?: string | null
  points: number
  time_ms: number
  move: 'up' | 'down' | 'same' | 'new'
  delta: number
}
export interface Board {
  day: string
  is_today: boolean
  resets_at: string
  rows: BoardRow[]
  me: BoardRow | null
  players: number
}
export interface AdminQuiz {
  id: string
  title: string
  status: 'scheduled' | 'live' | 'publishing'
  question_count: number
  max_seconds: number
  expires_hours?: number
  scheduled_at: string | null
  posted_at: string | null
  players: number
  notify_error: string | null
}
export interface Analytics {
  total_players: number
  players_today: number
  plays_today: number
  quizzes_live: number
  daily: { day: string; players: number; plays: number }[]
  quizzes: { id: string; title: string; started: number; players: number; avg_score_pct: number; avg_time_ms: number; completion_pct: number }[]
}
export interface QuestionPayload {
  type: 'poll' | 'text' | 'image'
  text: string
  image_url?: string
  answer_mode: 'options' | 'text'
  options: string[]
  correct_index?: number
  accepted: string[]
  points: number
}
export interface CreateOutcome {
  id: string
  status: 'live' | 'scheduled'
  notified: boolean
  error: string | null
  scheduled_at?: string
}
export interface QuizPayload {
  title: string
  scheduled_at: string | null
  max_seconds: number
  expires_hours?: number
  questions: QuestionPayload[]
}
