import { useEffect, useState } from 'react'
import { artifactUrl, getTaskStatus, retryTask, Task } from '../api/client'

interface Props { taskId: string; onTask: (task: Task) => void }

const labels: Record<Task['status'], string> = { uploaded: '已上传', processing: '分析中', ready: '可提问', answering: '回答中', completed: '已完成', failed: '失败', cancelled: '已取消' }

export default function TaskStatus({ taskId, onTask }: Props) {
  const [task, setTask] = useState<Task | null>(null)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)
  async function retry() {
    setRetrying(true); setError('')
    try { const next=await retryTask(taskId); setTask(next); onTask(next) }
    catch (err) { setError(err instanceof Error ? err.message : '重新运行失败') }
    finally { setRetrying(false) }
  }
  useEffect(() => {
    let active = true
    async function poll() {
      try { const next = await getTaskStatus(taskId); if (active) { setTask(next); onTask(next) } }
      catch (err) { if (active) setError(err instanceof Error ? err.message : '状态获取失败') }
    }
    poll()
    const timer = window.setInterval(poll, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [taskId, onTask])
  const progress = task?.progress ?? 0
  return <section className="status-panel panel">
    <div className="status-heading"><div><div className="section-kicker">TASK MONITOR</div><h2>任务状态</h2></div><span className={`status-dot ${task?.status || 'uploaded'}`} /> </div>
    <div className="task-id">{taskId}</div>
    <div className="status-row"><strong>{task ? labels[task.status] : '读取中'}</strong><span>{progress}%</span></div>
    <div className="progress-track"><div className={`progress-fill ${task?.status === 'failed' ? 'failed' : ''}`} style={{ width: `${progress}%` }} /></div>
    <div className="progress-labels"><span>上传</span><span>处理中</span><span>完成</span></div>
    <p className="muted">当前阶段：{task?.stage || '读取中'} · 阶段进度：{task?.pipeline_progress ?? progress}%</p>
    {task?.quality && <p className={`quality-badge ${task.quality}`}>数据质量：{task.quality}</p>}
    {task?.quality_report_path && <p className="muted">质量报告已生成</p>}
    {task?.artifacts && <div className="muted artifacts">{Object.entries(task.artifacts).filter(([key, value]) => value && !value.startsWith('disabled') && ['ball_csv','player_csv','analysis_json','quality_report','event_analysis','rally_analysis','important_events','analysis_video','latest_result'].includes(key)).map(([key]) => <a key={key} href={artifactUrl(taskId, key)} target="_blank" rel="noreferrer">{key}</a>)}</div>}
    {task?.quality_warnings?.map(w => <p className="error-text" key={w}>{w}</p>)}
    {task?.error && <p className="error-text">{task.error}。请检查模型路径和标定配置后重试。</p>}
    {task?.previous_error && <p className="muted">上次错误：{task.previous_error}</p>}
    {task?.retry_count !== undefined && <p className="muted">重试次数：{task.retry_count}</p>}
    {task?.retryable && <button type="button" disabled={retrying} onClick={retry}>{retrying ? '重新运行中…' : '重新运行'}</button>}
    {error && <p className="error-text">{error}</p>}
  </section>
}
