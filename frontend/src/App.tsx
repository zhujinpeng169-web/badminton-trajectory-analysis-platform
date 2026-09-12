import { useCallback, useState } from 'react'
import { AgentResult, getResult, Task, UploadResponse } from './api/client'
import UploadPanel from './components/UploadPanel'
import TaskStatus from './components/TaskStatus'
import ChatPanel from './components/ChatPanel'
import ReportViewer from './components/ReportViewer'

export default function App() {
  const [upload, setUpload] = useState<UploadResponse | null>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [result, setResult] = useState<AgentResult | null>(null)
  const onTask = useCallback(async (next: Task) => { setTask(next); if ((next.status === 'ready' || next.status === 'completed') && next.result_path && !result) { try { setResult(await getResult(next.task_id)) } catch { /* status remains visible */ } } }, [result])
  function uploaded(next: UploadResponse) { setUpload(next); setTask(null); setResult(null) }
  function submitted(next: Task) { setTask(next); setResult(null) }
  return <div className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">TL</span><span>TRAJECTORY <b>LAB</b></span></div><div className="header-status"><span className="online-dot" /> LOCAL AGENT <span className="divider" /> QWEN3-VL</div></header>
    <main className="workspace">
      <aside className="sidebar"><div className="intro"><p className="eyebrow">BADMINTON / ANALYTICS</p><h1>把比赛轨迹<br /><em>问清楚。</em></h1><p>从检测结果到可核对的比赛洞察。</p></div><UploadPanel onUploaded={uploaded} /><div className="sidebar-note">数据来自本地 TrackNet 轨迹与事件 JSON<br />不上传到云端</div></aside>
      <section className="main-column"><div className="main-head"><div><p className="eyebrow">ANALYSIS WORKSPACE</p><h2>比赛分析台</h2></div>{upload && <div className="file-chip"><span className="file-dot" />{upload.filename}<span>·</span>{upload.task_id.slice(0, 8)}</div>}</div>{upload && <TaskStatus taskId={upload.task_id} onTask={onTask} />}<ChatPanel taskId={upload?.task_id || null} task={task} onSubmitted={submitted} /><ReportViewer result={result} /></section>
    </main>
  </div>
}
