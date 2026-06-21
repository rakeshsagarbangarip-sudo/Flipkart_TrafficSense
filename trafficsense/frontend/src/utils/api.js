// src/utils/api.js
const BASE = 'https://flipkart-trafficsense-2-7b7e.onrender.com'

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
 if (!res.ok) {
  const text = await res.text()

  console.log("STATUS:", res.status)
  console.log("RESPONSE:", text)

  throw new Error(`Status ${res.status}: ${text}`)
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
