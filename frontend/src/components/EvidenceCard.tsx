import { Evidence } from '../api/client'

export default function EvidenceCard({ evidence }: { evidence: Evidence }) {
  const reliability = evidence.reliability === undefined ? '—' : evidence.reliability >= .75 ? 'high' : evidence.reliability >= .4 ? 'medium' : 'low'
  return <article className="evidence-card">
    <div className="evidence-top"><span className="evidence-tag">证据</span><span className={`reliability ${reliability}`}>{reliability}</span></div>
    <strong>{evidence.metric}</strong>
    <div className="evidence-value">{String(evidence.value)} <small>{evidence.unit}</small></div>
    <div className="evidence-source">来源 · {evidence.source}</div>
    {evidence.description && <p>{evidence.description}</p>}
  </article>
}
