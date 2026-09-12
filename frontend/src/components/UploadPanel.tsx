import { useRef, useState } from 'react'
import { uploadVideo, UploadResponse } from '../api/client'

interface Props { onUploaded: (upload: UploadResponse) => void; disabled?: boolean }

export default function UploadPanel({ onUploaded, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function chooseFile(file?: File) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.mp4')) { setError('目前只支持 MP4 视频'); return }
    setBusy(true); setError('')
    try { onUploaded(await uploadVideo(file)) }
    catch (err) { setError(err instanceof Error ? err.message : '上传失败') }
    finally { setBusy(false) }
  }

  return <section className="upload-panel panel">
    <div className="section-kicker">DATA INTAKE</div>
    <h2>导入比赛视频</h2>
    <p className="muted">上传 MP4，关联已有轨迹数据并开始问答分析。</p>
    <button className="dropzone" disabled={disabled || busy} onClick={() => inputRef.current?.click()}>
      <span className="upload-icon" aria-hidden="true">↑</span>
      <span>{busy ? '正在上传…' : '选择 MP4 视频'}</span>
      <small>支持 41.MP4 等比赛录像</small>
    </button>
    <input ref={inputRef} hidden type="file" accept="video/mp4,.mp4" onChange={e => chooseFile(e.target.files?.[0])} />
    {error && <p className="error-text">{error}</p>}
  </section>
}
