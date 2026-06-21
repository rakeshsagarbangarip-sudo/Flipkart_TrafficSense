import { useEffect, useState } from 'react'
import { get, post } from '../utils/api'

function pretty(value) {
  return value ? value.replace(/_/g, ' ') : 'Not specified'
}

export default function FeedbackPage() {
  const [tab, setTab] = useState('unplanned')
  const [events, setEvents] = useState([])
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({})
  const [officerId, setOfficerId] = useState('')
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function load() {
    try {
      const data = tab === 'unplanned' ? await get('/unplanned/all') : await get('/planned/all')
      setEvents(data.filter(event => (
        tab === 'unplanned'
          ? event.status === 'resolved' && !event.feedback_submitted
          : event.status === 'approved' && !event.feedback_submitted
      )))
      setSelected(null)
      setForm({})
      setDone(false)
    } catch (loadError) {
      console.error(loadError)
    }
  }

  useEffect(() => { load() }, [tab])

  const set = key => event => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm(current => ({ ...current, [key]: value }))
  }

  async function submit(event) {
    event.preventDefault()
    if (!selected) return
    if (!officerId) {
      setError('Please enter officer ID.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      if (tab === 'unplanned') {
        await post(`/unplanned/${selected.id}/feedback`, {
          officer_id: officerId,
          actual_duration_min: Number(form.actual_duration_min || 0),
          actual_manpower_used: Number(form.actual_manpower_used || 0),
          actual_barricades: Number(form.actual_barricades || 0),
          needed_more_manpower: !!form.needed_more_manpower,
          needed_more_barricades: !!form.needed_more_barricades,
          prediction_accurate: !!form.prediction_accurate,
          feedback_notes: form.feedback_notes || '',
        })
      } else {
        await post(`/planned/${selected.id}/feedback`, {
          officer_id: officerId,
          actual_manpower_used: Number(form.actual_manpower_used || 0),
          actual_barricades: Number(form.actual_barricades || 0),
          prediction_accurate: !!form.prediction_accurate,
          feedback_notes: form.feedback_notes || '',
        })
      }
      setDone(true)
      await load()
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">Model feedback</p>
          <h1>Submit field feedback</h1>
          <p>Capture actual duration, manpower, barricades, and prediction quality after operations are complete.</p>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <button className={`btn ${tab === 'unplanned' ? '' : 'secondary'}`} onClick={() => setTab('unplanned')}>Incidents</button>
          <button className={`btn ${tab === 'planned' ? '' : 'secondary'}`} onClick={() => setTab('planned')}>Planned events</button>
        </div>
      </div>

      <section className="learning-strip">
        {['Forecast impact', 'Recommend resources', 'Deploy on ground', 'Record actuals', 'Improve next model'].map((step, index) => (
          <div className="learning-step" key={step}>
            <strong>{index + 1}</strong>
            <span>{step}</span>
          </div>
        ))}
      </section>

      <div className="grid feedback-grid">
        <section className="card card-pad">
          <h2 className="section-title">Awaiting feedback</h2>
          <div className="list">
            {events.length === 0 && <div className="empty">No {tab} records are waiting for feedback.</div>}
            {events.map(event => (
              <article
                className={`list-item ${selected?.id === event.id ? 'active' : ''}`}
                key={event.id}
                onClick={() => { setSelected(event); setDone(false); setError(null); setForm({}) }}
              >
                <div className="title-sm">{event.event_name || pretty(event.event_cause)}</div>
                <div className="meta">{event.address}</div>
                <div className="meta">
                  {tab === 'unplanned'
                    ? `${event.ml_severity || 'low'} · ${Math.round(event.ml_duration_min || 0)} min`
                    : `${event.ml_severity || 'pending'} · ${event.ml_manpower || 0} officers`}
                </div>
              </article>
            ))}
          </div>
        </section>

        <form className="card card-pad" onSubmit={submit}>
          {!selected && !done && <div className="empty">Select an event to open the feedback form.</div>}

          {selected && !done && (
            <>
              <p className="eyebrow">{tab === 'planned' ? 'Planned event' : 'Live incident'}</p>
              <h1 style={{ fontSize: 26 }}>{selected.event_name || pretty(selected.event_cause)}</h1>
              <p>{selected.address}</p>

              <div className="form-grid">
                <div className="field">
                  <label>Actual manpower used</label>
                  <input className="control" type="number" value={form.actual_manpower_used || ''} onChange={set('actual_manpower_used')} />
                </div>
                <div className="field">
                  <label>Actual barricades</label>
                  <input className="control" type="number" value={form.actual_barricades || ''} onChange={set('actual_barricades')} />
                </div>
                {tab === 'unplanned' && (
                  <div className="field">
                    <label>Actual duration</label>
                    <input className="control" type="number" value={form.actual_duration_min || ''} onChange={set('actual_duration_min')} placeholder="Minutes" />
                  </div>
                )}
                <div className="field">
                  <label>Officer ID</label>
                  <input className="control" value={officerId} onChange={event => setOfficerId(event.target.value)} />
                </div>
                <div className="field span-2">
                  <label>Outcome checks</label>
                  <div className="actions" style={{ marginTop: 0 }}>
                    {tab === 'unplanned' && (
                      <>
                        <label className="checkbox-row"><input type="checkbox" checked={!!form.needed_more_manpower} onChange={set('needed_more_manpower')} />Needed more manpower</label>
                        <label className="checkbox-row"><input type="checkbox" checked={!!form.needed_more_barricades} onChange={set('needed_more_barricades')} />Needed more barricades</label>
                      </>
                    )}
                    <label className="checkbox-row"><input type="checkbox" checked={!!form.prediction_accurate} onChange={set('prediction_accurate')} />Prediction was accurate</label>
                  </div>
                </div>
                <div className="field span-2">
                  <label>Notes</label>
                  <textarea className="control" value={form.feedback_notes || ''} onChange={set('feedback_notes')} placeholder="What worked, what changed on ground, or what the next model should learn" />
                </div>
              </div>

              {error && <div className="alert error">{error}</div>}
              <div className="actions">
                <button className="btn" disabled={loading}>{loading ? 'Submitting...' : 'Submit feedback'}</button>
              </div>
            </>
          )}

          {done && <div className="alert success">Feedback recorded and ready for export during retraining.</div>}
        </form>
      </div>
    </>
  )
}
