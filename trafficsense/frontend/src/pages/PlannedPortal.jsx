import { useState } from 'react'
import { post } from '../utils/api'

const initialForm = {
  event_cause: 'public_event',
  event_name: '',
  organizer_name: '',
  expected_crowd_size: '',
  address: '',
  latitude: '',
  longitude: '',
  corridor: '',
  zone: '',
  junction: '',
  start_datetime: '',
  end_datetime: '',
  requires_road_closure: false,
  priority: 'Medium',
  description: '',
  police_station: '',
  submitted_by: '',
}

function Field({ label, children, span }) {
  return (
    <div className={`field ${span ? 'span-2' : ''}`}>
      <label>{label}</label>
      {children}
    </div>
  )
}

export default function PlannedPortal() {
  const [form, setForm] = useState(initialForm)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = key => event => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm(current => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    if (!form.event_name || !form.address || !form.latitude || !form.longitude || !form.start_datetime || !form.end_datetime || !form.submitted_by) {
      setError('Please fill event name, address, coordinates, timing, and officer ID.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await post('/planned/submit', {
        ...form,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        expected_crowd_size: form.expected_crowd_size ? Number(form.expected_crowd_size) : null,
        start_datetime: new Date(form.start_datetime).toISOString(),
        end_datetime: new Date(form.end_datetime).toISOString(),
      })
      setResult(response)
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setLoading(false)
    }
  }

  if (result) {
    return (
      <section className="card card-pad" style={{ maxWidth: 620, margin: '48px auto' }}>
        <p className="eyebrow">Submitted</p>
        <h1>Event sent for approval</h1>
        <p>The admin panel can now approve this request and generate the deployment plan.</p>
        <div className="alert success">Event ID: {result.id}</div>
        <div className="actions">
          <button className="btn" onClick={() => { setResult(null); setForm(initialForm) }}>Submit another event</button>
        </div>
      </section>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">Planned operations</p>
          <h1>Submit a planned event</h1>
          <p>Use this for rallies, construction, VIP movement, public events, or other advance traffic plans.</p>
        </div>
        <span className="badge">Approval required</span>
      </div>

      <form className="card card-pad" onSubmit={submit}>
        <div className="form-grid">
          <Field label="Event type">
            <select className="control" value={form.event_cause} onChange={set('event_cause')}>
              <option value="public_event">Public event</option>
              <option value="procession">Procession or rally</option>
              <option value="vip_movement">VIP movement</option>
              <option value="construction">Construction</option>
              <option value="protest">Protest</option>
            </select>
          </Field>
          <Field label="Event name">
            <input className="control" value={form.event_name} onChange={set('event_name')} placeholder="Republic Day parade" />
          </Field>
          <Field label="Organizer">
            <input className="control" value={form.organizer_name} onChange={set('organizer_name')} placeholder="BBMP / Karnataka Police" />
          </Field>
          <Field label="Expected crowd">
            <input className="control" type="number" value={form.expected_crowd_size} onChange={set('expected_crowd_size')} placeholder="5000" />
          </Field>
          <Field label="Address" span>
            <input className="control" value={form.address} onChange={set('address')} placeholder="Street, area, Bengaluru" />
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
          <Field label="Nearest junction">
            <input className="control" value={form.junction} onChange={set('junction')} placeholder="Silk Board junction" />
          </Field>
          <Field label="Police station">
            <input className="control" value={form.police_station} onChange={set('police_station')} placeholder="Nearest police station" />
          </Field>
          <Field label="Start time">
            <input className="control" type="datetime-local" value={form.start_datetime} onChange={set('start_datetime')} />
          </Field>
          <Field label="End time">
            <input className="control" type="datetime-local" value={form.end_datetime} onChange={set('end_datetime')} />
          </Field>
          <Field label="Priority">
            <select className="control" value={form.priority} onChange={set('priority')}>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
            </select>
          </Field>
          <Field label="Road closure">
            <label className="checkbox-row">
              <input type="checkbox" checked={form.requires_road_closure} onChange={set('requires_road_closure')} />
              Required
            </label>
          </Field>
          <Field label="Description" span>
            <textarea className="control" value={form.description} onChange={set('description')} placeholder="Deployment notes or expected bottlenecks" />
          </Field>
          <Field label="Submitting officer" span>
            <input className="control" value={form.submitted_by} onChange={set('submitted_by')} placeholder="Officer ID or name" />
          </Field>
        </div>

        {error && <div className="alert error">{error}</div>}
        <div className="actions">
          <button className="btn" disabled={loading}>{loading ? 'Submitting...' : 'Submit for admin approval'}</button>
        </div>
      </form>
    </>
  )
}
