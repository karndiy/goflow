import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { UserRequestEntry, UserRequestListResponse } from '../api/types'
import StatusBadge from '../components/StatusBadge'

export default function RequestsPage() {
  const [prompt, setPrompt] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [requests, setRequests] = useState<UserRequestEntry[] | null>(null)
  const [query, setQuery] = useState('')

  function load() {
    const params = new URLSearchParams({ limit: '50' })
    if (query) params.set('q', query)
    api
      .get<UserRequestListResponse>(`/requests?${params.toString()}`)
      .then((res) => setRequests(res.items))
  }

  useEffect(load, [query])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!prompt.trim()) return
    setError(null)
    setSubmitting(true)
    try {
      await api.post('/requests', { prompt })
      setPrompt('')
      load()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? 'The AI assistant is not configured yet. Set an Anthropic API key in Settings.'
            : err.message
          : 'Could not submit request',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Requests</h1>
      </div>

      <form className="card" onSubmit={handleSubmit} style={{ marginBottom: 16 }}>
        <div className="form-row" style={{ marginBottom: 10 }}>
          <label htmlFor="request-prompt">Ask Claude a question or submit a feature request</label>
          <textarea
            id="request-prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder="e.g. Can we add a weekly summary email of published posts?"
            required
          />
        </div>
        {error && <p className="error-text">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? 'Sending to Claude...' : 'Send to Claude'}
        </button>
      </form>

      <div className="toolbar">
        <input
          placeholder="Search past requests..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ maxWidth: 320 }}
        />
      </div>

      {requests === null ? (
        <p className="muted">Loading...</p>
      ) : requests.length === 0 ? (
        <p className="empty-state">No requests yet.</p>
      ) : (
        requests.map((r) => (
          <div className="card" key={r.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontWeight: 600 }}>{r.prompt}</p>
                <p className="muted" style={{ fontSize: 12, margin: '4px 0' }}>
                  {r.requester_email} &middot; {new Date(r.created_at).toLocaleString()}
                </p>
              </div>
              <StatusBadge status={r.status} />
            </div>
            {r.status === 'answered' && (
              <p style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{r.response}</p>
            )}
            {r.status === 'failed' && (
              <p className="error-text" style={{ marginBottom: 0 }}>
                {r.error_message}
              </p>
            )}
          </div>
        ))
      )}
    </div>
  )
}
