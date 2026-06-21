// src/App.jsx
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import PlannedPortal from './pages/PlannedPortal'
import LiveIncident from './pages/LiveIncident'
import AdminApproval from './pages/AdminApproval'
import FeedbackPage from './pages/FeedbackPage'

const NAV = [
  { to: '/', label: 'Live Dashboard' },
  { to: '/planned', label: 'Planned Event' },
  { to: '/incident', label: 'Report Incident' },
  { to: '/admin', label: 'Admin Approval' },
  { to: '/feedback', label: 'Feedback' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark">TS</span>
            <span>
              TrafficSense
              <small>Flipkart Hackathon Prototype</small>
            </span>
          </div>
          <nav className="nav">
          {NAV.map(n => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className="nav-link">
              {n.label}
            </NavLink>
          ))}
          </nav>
        </header>
        <main className="page">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/planned" element={<PlannedPortal />} />
            <Route path="/incident" element={<LiveIncident />} />
            <Route path="/admin" element={<AdminApproval />} />
            <Route path="/feedback" element={<FeedbackPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
