import ReactMarkdown from 'react-markdown'
import { AgentResult } from '../api/client'
import EvidenceCard from './EvidenceCard'

export default function ReportViewer({ result }: { result: AgentResult | null }) {
  if (!result) return <section className="report-empty"><span className="empty-mark">◌</span><h2>等待第一份分析报告</h2><p>上传视频后，向 Agent 提问，报告和证据会显示在这里。</p></section>
  const evidence = result.routing?.evidence || []
  return <div className="results-stack">
    <section className="report-panel panel"><div className="section-kicker">AGENT REPORT</div><h2>分析报告</h2><div className="markdown"><ReactMarkdown>{result.report}</ReactMarkdown></div></section>
    <section className="evidence-panel panel"><div className="evidence-heading"><div><div className="section-kicker">TRACEABLE DATA</div><h2>证据链</h2></div><span>{evidence.length} 条字段</span></div><div className="evidence-grid">{evidence.map((item, i) => <EvidenceCard key={`${item.metric}-${i}`} evidence={item} />)}</div></section>
  </div>
}
