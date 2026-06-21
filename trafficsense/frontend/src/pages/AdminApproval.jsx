import { useEffect, useState } from 'react'
import { get, put } from '../utils/api'

function pretty(value) {
  return value ? value.replace(/_/g, ' ') : 'Not specified'
}

function estimateImpact(event) {
  if (!event) return null
  const priorityBoost = event.priority === 'High' ? 20 : event.priority === 'Medium' ? 10 : 0
  const closureBoost = event.requires_road_closure ? 25 : 0
  const base = event.event_cause === 'vip_movement' || event.event_cause === 'procession' ? 45 : 30
  const score = Math.min(95, base + priorityBoost + closureBoost)

  return {
    score,
    delay: score > 75 ? '45-70 min' : score > 55 ? '25-45 min' : '15-25 min',
    manpower: score > 75 ? '10-14' : score > 55 ? '6-10' : '3-6',
    reasoning: [
      `${event.priority || 'Medium'} priority raises pre-deployment need.`,
      `${pretty(event.event_cause)} events affect nearby junction throughput.`,
      event.requires_road_closure ? 'Road closure adds diversion and barricade load.' : 'No closure keeps impact localized.',
    ],
  }
}

export default function AdminApproval() {
  const [pending, setPending] = useState([])
  const [selected, setSelected] = useState(null)
  const [adminId, setAdminId] = useState('admin_1')
  const [rejectionReason, setRejectionReason] = useState('')
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function load() {
    try {
      setPending(await get('/planned/pending'))
    } catch (loadError) {
      console.error(loadError)
    }
  }

  useEffect(() => { load() }, [])

  async function decide(action) {
    if (!selected) return
    setProcessing(true)
    setError(null)
    setResult(null)
    try {
      const response = await put(`/planned/${selected.id}/approve`, {
        admin_id: adminId,
        action,
        rejection_reason: rejectionReason || null,
      })
      setResult({ action, ...response })
      await load()
      if (action === 'approve') setSelected(null)
    } catch (decisionError) {
      setError(decisionError.message)
    } finally {
      setProcessing(false)
    }
  }

  const forecast = estimateImpact(selected)

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">Administration</p>
          <h1>Approve planned events</h1>
          <p>Review submissions and trigger the ML deployment plan for approved events.</p>
        </div>
        <span className="badge">{pending.length} pending</span>
      </div>

      <div className="grid admin-grid">
        <section className="card card-pad">
          <h2 className="section-title">Pending review</h2>
          <div className="list">
            {pending.length === 0 && <div className="empty">No planned event requests are pending.</div>}
            {pending.map(event => (
              <article
                className={`list-item ${selected?.id === event.id ? 'active' : ''}`}
                key={event.id}
                onClick={() => { setSelected(event); setResult(null); setError(null); setRejectionReason('') }}
              >
                <div className="title-sm">{event.event_name}</div>
                <div className="meta">{pretty(event.event_cause)} · {event.priority}</div>
                <div className="meta">{event.address}</div>
              </article>
            ))}
          </div>
        </section>

        <section className="card card-pad">
          {!selected && !result && <div className="empty">Select a request to review its location, timing, and priority.</div>}

          {selected && (
            <>
              <p className="eyebrow">Review request</p>
              <h1 style={{ fontSize: 26 }}>{selected.event_name}</h1>
              <p>{selected.address}</p>

              <div className="metric-grid">
                <div className="metric"><strong>{selected.priority}</strong><span>Priority</span></div>
                <div className="metric"><strong>{pretty(selected.event_cause)}</strong><span>Type</span></div>
                <div className="metric"><strong>{selected.ml_manpower || '-'}</strong><span>Current plan</span></div>
              </div>

              {forecast && (
                <div className="impact-panel">
                  <div>
                    <p className="eyebrow">Before approval forecast</p>
                    <h2>{forecast.score}% impact score</h2>
                  </div>
                  <div className="metric-grid">
                    <div className="metric"><strong>{forecast.delay}</strong><span>Expected delay</span></div>
                    <div className="metric"><strong>{forecast.manpower}</strong><span>Officer range</span></div>
                    <div className="metric"><strong>2-4</strong><span>Diversion points</span></div>
                  </div>
                  <div className="insight-list">
                    {forecast.reasoning.map(reason => <div key={reason}>{reason}</div>)}
                  </div>
                </div>
              )}

              <div className="form-grid" style={{ marginTop: 18 }}>
                <div className="field">
                  <label>Admin ID</label>
                  <input className="control" value={adminId} onChange={event => setAdminId(event.target.value)} />
                </div>
                <div className="field">
                  <label>Rejection reason</label>
                  <input className="control" value={rejectionReason} onChange={event => setRejectionReason(event.target.value)} placeholder="Only needed when rejecting" />
                </div>
              </div>

              {error && <div className="alert error">{error}</div>}
              <div className="actions">
                <button className="btn success" disabled={processing} onClick={() => decide('approve')}>Approve and generate plan</button>
                <button className="btn danger" disabled={processing} onClick={() => decide('reject')}>Reject request</button>
              </div>
            </>
          )}

          {result?.action === 'approve' && result.decision && (
            <div className="alert success">
              Deployment plan generated: {result.decision.manpower} officers, {Math.round((result.decision.risk_score || 0) * 100)}% risk score.
            </div>
          )}
          {result?.action === 'reject' && <div className="alert success">Request rejected.</div>}
        </section>
      </div>
    </>
  )
}
