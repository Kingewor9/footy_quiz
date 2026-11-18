import { useCallback, useEffect, useState } from 'react'
import { Download, HelpCircle, Radio, Timer } from 'lucide-react'
import { api } from '../../api'
import type { ImportQuizSummary } from '../../types'

export default function ImportedQuizzes({ channelId, channelName }: { channelId: string; channelName: string }) {
  const [quizzes, setQuizzes] = useState<ImportQuizSummary[] | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(() => {
    api.admin.channelImportQuizzes(channelId)
      .then(setQuizzes)
      .catch((error: Error) => setMessage({ ok: false, text: error.message }))
  }, [channelId])

  useEffect(load, [load])

  const importQuiz = async (quiz: ImportQuizSummary) => {
    setBusyId(quiz.id)
    setMessage(null)
    try {
      const result = await api.admin.importQuizToChannel(channelId, quiz.id)
      setMessage(result.notified
        ? { ok: true, text: `${quiz.title} is live and announced in ${channelName}.` }
        : { ok: false, text: `${quiz.title} is live, but the channel post failed: ${result.error ?? 'Telegram could not deliver the post.'}` })
    } catch (error) {
      setMessage({ ok: false, text: (error as Error).message })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="imported-quizzes">
      {message && <div className={`notice ${message.ok ? 'ok' : 'err'}`}>{message.text}</div>}
      <div className="imported-quizzes-intro card">
        <div className="channel-icon"><Radio size={18} /></div>
        <div>
          <b>Ready-made quizzes for your league</b>
          <p className="small muted">Importing posts a fresh copy to {channelName}. Plays and points count toward this channel’s daily leaderboard.</p>
        </div>
      </div>

      {quizzes === null && !message && <div className="empty"><div className="spinner-ring sm" />Loading shared quizzes…</div>}
      {quizzes?.length === 0 && (
        <div className="empty empty-state-box">
          <Download size={28} className="muted" />
          <p>No imported quizzes available yet</p>
          <span className="small muted">The game admin can add quizzes to the shared import library.</span>
        </div>
      )}
      {quizzes?.map((quiz) => (
        <div className="card imported-quiz-row" key={quiz.id}>
          <div className="imported-quiz-copy">
            <b>{quiz.title}</b>
            <div className="imported-quiz-meta">
              <span><HelpCircle size={13} /> {quiz.question_count} {quiz.question_count === 1 ? 'question' : 'questions'}</span>
              <span><Timer size={13} /> {quiz.max_seconds}s each</span>
            </div>
          </div>
          <button className="btn sm" disabled={busyId !== null} onClick={() => importQuiz(quiz)}>
            <Download size={14} /> {busyId === quiz.id ? 'Posting…' : 'Import & post'}
          </button>
        </div>
      ))}
    </div>
  )
}
