// src/utils/api.js
const BASE = '/api'

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const get  = (path) => api(path)
export const post = (path, body) => api(path, { method: 'POST', body })
export const put  = (path, body) => api(path, { method: 'PUT', body })

// WebSocket for live feed
export function connectLive(onMessage) {
  const ws = new WebSocket(
  "wss://flipkart-trafficsense-2-7b7e.onrender.com/ws/live"
  )
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  ws.onerror = () => console.warn('WS disconnected')
  return ws
}
