import { FormEvent, useState } from 'react'
import { analyzeQuestion, Task } from '../api/client'

interface Props { taskId: string | null; task?: Task | null; onSubmitted: (task: Task) => void }
const suggestions = ['分析运动员A', '第二回合有哪些关键事件', '能否判断谁获胜']

export default function ChatPanel({ taskId, task, onSubmitted }: Props) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault(); if (!taskId || !question.trim()) return
    setBusy(true); setError('')
    try { onSubmitted(await analyzeQuestion(taskId, question.trim())); setQuestion('') }
    catch (err) { setError(err instanceof Error ? err.message : '提交失败') }
    finally { setBusy(false) }
  }
  const locked = !taskId || (task?.status !== 'ready' && task?.status !== 'completed')
  return <section className="chat-panel panel">
    <div className="section-kicker">ASK THE AGENT</div><h2>比赛问答</h2>
    <p className="muted">所有回答都会标注数据来源，不对轨迹无法证明的动作或胜负作推断。</p>
    <div className="suggestions">{suggestions.map(s => <button key={s} disabled={locked} onClick={() => setQuestion(s)}>{s}</button>)}</div>
    <form onSubmit={submit} className="question-form">
      <textarea value={question} onChange={e => setQuestion(e.target.value)} disabled={locked} placeholder={locked ? '请等待视频分析完成后提问…' : '输入你的问题，例如：分析运动员A第二回合移动问题'} rows={3} />
      <button className="send-button" disabled={locked || busy || !question.trim()}>{busy ? '提交中…' : '发送问题  ↗'}</button>
    </form>
    {error && <p className="error-text">{error}</p>}
  </section>
}
