import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE,
  timeout: 120000,
})

client.interceptors.response.use(
  r => r.data,
  err => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export const api = {
  health: () => client.get('/health'),

  analyze: (files, applicantId = '') => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    const url = applicantId ? `/analyze?applicant_id=${encodeURIComponent(applicantId)}` : '/analyze'
    return client.post(url, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },

  getReport: id => client.get(`/report/${id}`),
  getReportText: id => client.get(`/report/${id}/text`),

  getHistory: (page = 1, perPage = 20, verdict = null) => {
    const params = new URLSearchParams({ page, per_page: perPage })
    if (verdict) params.append('verdict', verdict)
    return client.get(`/history?${params}`)
  },

  getStats: () => client.get('/stats'),
  checkHash: hash => client.get(`/hash/${hash}`),
}

// WebSocket helper
export function createAnalysisSocket(onEvent) {
  const wsBase = BASE.replace(/^http/, 'ws')
  const ws = new WebSocket(`${wsBase}/ws/analyze`)

  ws.onopen = () => onEvent({ event: 'connected' })
  ws.onmessage = e => {
    try { onEvent(JSON.parse(e.data)) } catch {}
  }
  ws.onerror = () => onEvent({ event: 'error', message: 'WebSocket error' })
  ws.onclose = () => onEvent({ event: 'closed' })

  return {
    sendMeta: meta => ws.readyState === 1 && ws.send(JSON.stringify(meta)),
    sendFiles: async files => {
      const encoded = await Promise.all(files.map(async f => {
        const buf = await f.arrayBuffer()
        const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)))
        return { name: f.name, data: b64, size: f.size }
      }))
      ws.readyState === 1 && ws.send(JSON.stringify({ files: encoded }))
    },
    close: () => ws.close(),
    ready: () => ws.readyState === 1,
  }
}
