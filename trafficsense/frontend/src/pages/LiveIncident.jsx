import { useState } from 'react'
import { post, put } from '../utils/api'

const initialForm = {
  event_cause: 'vehicle_breakdown',
  address: '',
  latitude: '',
  longitude: '',
  corridor: '',
  zone: '',
  junction: '',
  veh_type: 'unknown',
  requires_road_closure: false,
  priority: 'High',
  description: '',
  police_station: '',
  reported_by: '',
}

function Field({ label, children, span }) {
  return (
    <div className={`field ${span ? 'span-2' : ''}`}>
      <label>{label}</label>
      {children}
    </div>
  )
}

export default function LiveIncident() {
  const [form, setForm] = useState(initialForm)
  const [decision, setDecision] = useState(null)
  const [eventId, setEventId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [resolved, setResolved] = useState(false)
  const [error, setError] = useState(null)

  const set = key => event => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm(current => ({ ...current, [key]: value }))
  }

  async function report(event) {
    event.preventDefault()
    if (!form.address || !form.latitude || !form.longitude || !form.reported_by) {
      setError('Please enter address, coordinates, and reporting officer ID.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await post('/unplanned/report', {
        ...form,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
      })
      setDecision(response.decision)
      setEventId(response.id)
    } catch (reportError) {
      setError(reportError.message)
    } finally {
      setLoading(false)
    }
  }

  async function resolveIncident() {
    if (!eventId) return
    try {
      await put(`/unplanned/${eventId}/resolve`, { officer_id: form.reported_by })
      setResolved(true)
    } catch (resolveError) {
      setError(resolveError.message)
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">Realtime response</p>
          <h1>Report live incident</h1>
          <p>Log an on-ground incident and get an immediate severity, duration, manpower, and action estimate.</p>
        </div>
        <span className="badge">Instant decision</span>
      </div>

      <div className="grid two-col">
        <form className="card card-pad" onSubmit={report}>
          <h2 className="section-title">Incident details</h2>
          <div className="form-grid">
            <Field label="Incident type">
              <select className="control" value={form.event_cause} onChange={set('event_cause')}>
                <option value="vehicle_breakdown">Vehicle breakdown</option>
                <option value="accident">Accident</option>
                <option value="pot_holes">Pothole</option>
                <option value="water_logging">Waterlogging</option>
                <option value="tree_fall">Tree fall</option>
                <option value="others">Others</option>
              </select>
            </Field>
            <Field label="Vehicle type">
              <select className="control" value={form.veh_type} onChange={set('veh_type')}>
                <option value="unknown">Not applicable</option>
                <option value="lcv">Light commercial</option>
                <option value="heavy_vehicle">Heavy vehicle</option>
                <option value="others">Others</option>
              </select>
            </Field>
            <Field label="Address" span>
              <input className="control" value={form.address} onChange={set('address')} placeholder="Exact street address" />
            </Field>
            <Field label="Latitude">
              <input className="control" type="number" step="any" value={form.latitude} onChange={set('latitude')} placeholder="12.9716" />
            </Field>
            <Field label="Longitude">
              <input className="control" type="number" step="any" value={form.longitude} onChange={set('longitude')} placeholder="77.5946" />
            </Field>
            <Field label="Corridor">
              <input className="control" value={form.corridor} onChange={set('corridor')} placeholder="ORR East 1" />
            </Field>
            <Field label="Zone">
              <input className="control" value={form.zone} onChange={set('zone')} placeholder="Whitefield" />
            </Field>
            <Field label="Junction">
              <input className="control" value={form.junction} onChange={set('junction')} placeholder="Nearest junction" />
            </Field>
            <Field label="Police station">
              <input className="control" value={form.police_station} onChange={set('police_station')} placeholder="Nearest police station" />
            </Field>
            <Field label="Priority">
              <select className="control" value={form.priority} onChange={set('priority')}>
                <option value="High">High</option>
                <option value="Low">Low</option>
              </select>
            </Field>
            <Field label="Road closure">
              <label className="checkbox-row">
                <input type="checkbox" checked={form.requires_road_closure} onChange={set('requires_road_closure')} />
                Required
              </label>
            </Field>
            <Field label="Description" span>
              <textarea className="control" value={form.description} onChange={set('description')} placeholder="What happened and what is blocked?" />
            </Field>
            <Field label="Reporting officer" span>
              <input className="control" value={form.reported_by} onChange={set('reported_by')} placeholder="Officer ID or badge number" />
            </Field>
          </div>

          {error && <div className="alert error">{error}</div>}
          <div className="actions">
            {!decision && <button className="btn danger" disabled={loading}>{loading ? 'Reporting...' : 'Report incident'}</button>}
            {decision && !resolved && <button className="btn success" type="button" onClick={resolveIncident}>Mark as resolved</button>}
          </div>
          {resolved && <div className="alert success">Incident resolved. It is now ready for feedback.</div>}
        </form>

        <section className="card card-pad">
          <h2 className="section-title">Decision panel</h2>
          {!decision && (
            <>
              <div className="map-panel"><span className="map-pin" /></div>
              <p className="muted">The ML decision will appear here after the report is submitted.</p>
            </>
          )}
          {decision && (
            <>
              <div className="metric-grid">
                <div className="metric">
                  <strong>{decision.severity}</strong>
                  <span>Severity</span>
                </div>
                <div className="metric">
                  <strong>{Math.round(decision.duration_min)}m</strong>
                  <span>Duration</span>
                </div>
                <div className="metric">
                  <strong>{decision.manpower}</strong>
                  <span>Officers</span>
                </div>
              </div>
              <div className="alert success">Incident ID: {eventId}</div>
              <div className="metric" style={{ marginTop: 14 }}>
                <p className="eyebrow">Recommended action</p>
                <p style={{ marginBottom: 0 }}>{decision.action}</p>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  )
}
