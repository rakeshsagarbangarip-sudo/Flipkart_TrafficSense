import { useEffect, useState } from 'react'
import { get, post } from '../utils/api'

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
  const [locationStatus, setLocationStatus] = useState(null)
  const [error, setError] = useState(null)

  const set = key => event => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm(current => ({ ...current, [key]: value }))
  }

  useEffect(() => {
    if (!form.latitude || !form.longitude) {
      setLocationStatus(null)
      return
    }

    const latitude = Number(form.latitude)
    const longitude = Number(form.longitude)
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      setLocationStatus({ type: 'error', message: 'Enter valid latitude and longitude.' })
      return
    }

    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setLocationStatus({ type: 'loading', message: 'Matching coordinates with planned dataset...' })
      try {
        const params = new URLSearchParams({
          event_type: 'planned',
          latitude: String(latitude),
          longitude: String(longitude),
        })
        const response = await get(`/location/lookup?${params.toString()}`, { signal: controller.signal })
        const match = response.matched
        setForm(current => {
          if (current.latitude !== form.latitude || current.longitude !== form.longitude) {
            return current
          }
          return {
            ...current,
            corridor: match.corridor || 'unknown',
            zone: match.zone || 'unknown',
            junction: match.junction || 'unknown',
            police_station: match.police_station || 'unknown',
          }
        })
        setLocationStatus({
          type: 'success',
          message: `Matched nearest dataset point ${response.distance_km} km away.`,
        })
      } catch (lookupError) {
        if (lookupError.name === 'AbortError') return
        setForm(current => ({
          ...current,
          corridor: '',
          zone: '',
          junction: '',
          police_station: '',
        }))
        setLocationStatus({
          type: 'error',
          message: lookupError.message.includes('outside')
            ? 'Coordinates are outside the planned dataset range.'
            : lookupError.message,
        })
      }
    }, 450)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [form.latitude, form.longitude])

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
            <input className="control" value={form.corridor} readOnly placeholder="Auto-filled from dataset" />
          </Field>
          <Field label="Zone">
            <input className="control" value={form.zone} readOnly placeholder="Auto-filled from dataset" />
          </Field>
          <Field label="Nearest junction">
            <input className="control" value={form.junction} readOnly placeholder="Auto-filled from dataset" />
          </Field>
          <Field label="Police station">
            <input className="control" value={form.police_station} readOnly placeholder="Auto-filled from dataset" />
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

        {locationStatus && <div className={`alert ${locationStatus.type === 'error' ? 'error' : 'info'}`}>{locationStatus.message}</div>}
        {error && <div className="alert error">{error}</div>}
        <div className="actions">
          <button className="btn" disabled={loading}>{loading ? 'Submitting...' : 'Submit for admin approval'}</button>
        </div>
      </form>
    </>
  )
}
