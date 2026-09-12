export type TaskStatus = 'uploaded' | 'processing' | 'ready' | 'answering' | 'completed' | 'failed' | 'cancelled'

export interface UploadResponse {
  task_id: string
  filename: string
  path: string
  status: TaskStatus
  stage?: string
  pipeline_progress?: number
  artifacts?: Record<string, string>
}

export interface Task {
  task_id: string
  status: TaskStatus
  progress: number
  filename?: string
  path?: string
  question?: string
  analysis_dir: string
  result_path?: string | null
  error?: string | null
  answer?: string | null
  stage?: string | null
  pipeline_progress?: number
  artifacts?: Record<string, string>
  quality_report_path?: string | null
  quality?: 'good' | 'warning' | 'poor' | null
  quality_warnings?: string[]
  stages?: Record<string, { status: string; progress: number; error?: string | null }>
  retryable?: boolean
  interrupted?: boolean
  answer_history?: string[]
  latest_result_path?: string | null
  retry_count?: number
  previous_error?: string | null
}

export interface Evidence {
  metric: string
  value: string | number
  unit: string
  source: string
  description: string
  reliability?: number
}

export interface AgentResult {
  question: string
  routing?: { evidence?: Evidence[]; classification?: Record<string, unknown> }
  report: string
  reflection?: { pass: boolean; issues: string[] }
  output_validation?: { warnings: string[] }
}

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    let detail = response.statusText
    try { detail = (await response.json()).detail || detail } catch { /* keep HTTP status */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export async function uploadVideo(file: File): Promise<UploadResponse> {
  const body = new FormData()
  body.append('file', file)
  return request<UploadResponse>('/api/upload', { method: 'POST', body })
}

export async function getTaskStatus(taskId: string): Promise<Task> {
  return request<Task>(`/api/status/${encodeURIComponent(taskId)}`)
}

export async function analyzeQuestion(taskId: string, question: string): Promise<Task> {
  return request<Task>('/api/analyze', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, question }),
  })
}

export async function getResult(taskId: string): Promise<AgentResult> {
  return request<AgentResult>(`/api/results/${encodeURIComponent(taskId)}`)
}

export function artifactUrl(taskId: string, name: string): string {
  return `${API_URL}/api/artifacts/${encodeURIComponent(taskId)}/${encodeURIComponent(name)}`
}

export async function retryTask(taskId: string): Promise<Task> {
  return request<Task>(`/api/retry/${encodeURIComponent(taskId)}`, { method: 'POST' })
}

export { API_URL }
