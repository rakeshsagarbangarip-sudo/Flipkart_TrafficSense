import { useEffect, useRef, useState } from 'react'
import { connectLive, get } from '../utils/api'

const SEVERITY_LABELS = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

function severityClass(value = 'low') {
  return `severity-dot severity-${value}`
}

function pretty(value) {
  return value ? value.replace(/_/g, ' ') : 'Not specified'
}

function StatCard({ label, value, note }) {
  return (
    <section className="card stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {note && <div className="meta">{note}</div>}
    </section>
  )
}

function EventRow({ event, kind }) {
  const severity = event.ml_severity || 'low'

  return (
    <article className="list-item">
      <div className="row">
        <div className="row" style={{ justifyContent: 'flex-start' }}>
          <span className={severityClass(severity)} />
          <div>
            <div className="title-sm">
              {kind === 'planned' && event.event_name ? event.event_name : pretty(event.event_cause)}
            </div>
            <div className="meta">{event.address || 'Address pending'}</div>
          </div>
        </div>
        <span className="badge">{SEVERITY_LABELS[severity] || severity}</span>
      </div>
      {kind === 'unplanned' && (
        <div className="meta">
          {Math.round(event.ml_duration_min || 0)} min response window · {event.ml_manpower_needed || 0} officers
        </div>
      )}
      {kind === 'planned' && <div className="meta">{event.ml_manpower || 0} officers recommended</div>}
    </article>
  )
}

function OperationsMap({ incidents, plans }) {
  return (
    <section className="map-hero">
      <div className="map-copy">
        <p className="eyebrow">Bengaluru operating picture</p>
        <h2>Where impact is expected</h2>
        <p>Active incidents and approved planned events appear together so officers can see clashes before deployment.</p>
      </div>
      <div className="city-map">
        <div className="map-road road-a" />
        <div className="map-road road-b" />
        <div className="map-road road-c" />
        {incidents.length === 0 && plans.length === 0 && (
          <div className="map-empty">No live events loaded</div>
        )}
        {[...incidents, ...plans].map((event, index) => (
          <div
            className={`map-marker ${event.ml_severity || 'low'} ${index >= incidents.length ? 'planned' : ''}`}
            key={event.id}
            style={event.position || { left: `${34 + (index * 13) % 42}%`, top: `${34 + (index * 17) % 38}%` }}
            title={event.event_name || pretty(event.event_cause)}
          >
            <span />
          </div>
        ))}
      </div>
    </section>
  )
}

function ImpactSummary({ incidents, plans }) {
  const hasEvents = incidents.length > 0 || plans.length > 0
  const highestSeverity = !hasEvents
    ? 'No data'
    : incidents.some(event => event.ml_severity === 'critical')
      ? 'Critical'
      : incidents.some(event => event.ml_severity === 'high') || plans.some(event => event.ml_severity === 'high')
        ? 'High'
        : 'Medium'

  const officers = incidents.reduce((sum, event) => sum + (event.ml_manpower_needed || 0), 0)
    + plans.reduce((sum, event) => sum + (event.ml_manpower || 0), 0)

  return (
    <section className="card card-pad">
      <h2 className="section-title">Impact forecast</h2>
      <div className="metric-grid">
        <div className="metric"><strong>{highestSeverity}</strong><span>Overall risk</span></div>
        <div className="metric"><strong>{officers}</strong><span>Officers suggested</span></div>
        <div className="metric"><strong>{hasEvents ? '2-5 km' : '-'}</strong><span>Affected radius</span></div>
      </div>
      {hasEvents ? (
        <div className="insight-list">
          <div>Peak impact likely during commute windows when events overlap with incidents.</div>
          <div>Prioritize junction control before barricade expansion.</div>
          <div>Keep planned and unplanned records separate for retraining.</div>
        </div>
      ) : (
        <div className="empty">Submit or approve events to generate impact insights.</div>
      )}
    </section>
  )
}

export default function Dashboard() {
  const [unplanned, setUnplanned] = useState([])
  const [planned, setPlanned] = useState([])
  const [feed, setFeed] = useState([])
  const wsRef = useRef(null)

  async function load() {
    try {
      const [activeIncidents, plannedEvents] = await Promise.all([
        get('/unplanned/active'),
        get('/planned/all'),
      ])
      setUnplanned(activeIncidents)
      setPlanned(plannedEvents.filter(event => event.status === 'approved' || event.status === 'active'))
    } catch (error) {
      console.error(error)
    }
  }

  useEffect(() => {
    load()
    wsRef.current = connectLive(message => {
      setFeed(current => [{ ...message, ts: new Date().toLocaleTimeString() }, ...current].slice(0, 20))
      if (['unplanned_reported', 'unplanned_resolved', 'planned_approved'].includes(message.type)) load()
    })

    const interval = setInterval(load, 30000)
    return () => {
      wsRef.current?.close()
      clearInterval(interval)
    }
  }, [])

  const visibleIncidents = unplanned
  const visiblePlans = planned
  const criticalCount = visibleIncidents.filter(event => event.ml_severity === 'critical').length
  const highCount = visibleIncidents.filter(event => event.ml_severity === 'high').length

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">Operations overview</p>
          <h1>Live traffic control room</h1>
          <p>Track active incidents, approved event plans, and live updates from the TrafficSense engine.</p>
        </div>
        <span className="live-pill"><span className="live-dot" />Live feed connected</span>
      </div>

      <div className="grid stats-grid">
        <StatCard label="Active incidents" value={visibleIncidents.length} />
        <StatCard label="Critical / high" value={`${criticalCount} / ${highCount}`} />
        <StatCard label="Approved plans" value={visiblePlans.length} />
        <StatCard label="Live updates" value={feed.length} note="Since this page loaded" />
      </div>

      <OperationsMap incidents={visibleIncidents} plans={visiblePlans} />

      <ImpactSummary incidents={visibleIncidents} plans={visiblePlans} />

      <div className="grid dashboard-grid" style={{ marginTop: 18 }}>
        <section className="card card-pad">
          <h2 className="section-title">Active incidents</h2>
          <div className="list">
            {visibleIncidents.length === 0 && <div className="empty">No active incidents loaded.</div>}
            {visibleIncidents.map(event => <EventRow key={event.id} event={event} kind="unplanned" />)}
          </div>
        </section>

        <section className="card card-pad">
          <h2 className="section-title">Approved planned events</h2>
          <div className="list">
            {visiblePlans.length === 0 && <div className="empty">No approved planned events loaded.</div>}
            {visiblePlans.map(event => <EventRow key={event.id} event={event} kind="planned" />)}
          </div>
        </section>

        <section className="card card-pad">
          <h2 className="section-title">Realtime activity</h2>
          <div className="list">
            {feed.length === 0 && <div className="empty">New submissions and approvals will appear here.</div>}
            {feed.map((message, index) => (
              <article className="list-item" key={`${message.type}-${index}`}>
                <div className="title-sm">{pretty(message.type)}</div>
                <div className="meta">{message.address || pretty(message.cause)}</div>
                <div className="meta">{message.ts}</div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </>
  )
}
