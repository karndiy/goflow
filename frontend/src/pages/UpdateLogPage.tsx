import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { AuditLogEntry, AuditLogListResponse, Release } from '../api/types'

const KNOWN_ACTIONS = [
  'auth.login',
  'workspace.update',
  'content.create',
  'content.update',
  'content.delete',
  'content.schedule',
  'content.cancel',
  'publishing.retry',
  'accounts.facebook_connected',
  'settings.platform_credential_set',
  'settings.platform_credential_delete',
  'settings.ai_set',
  'requests.create',
]

export default function UpdateLogPage() {
  const [tab, setTab] = useState<'activity' | 'versions'>('activity')

  return (
    <div>
      <div className="page-header">
        <h1>Update Log</h1>
      </div>

      <div className="toolbar">
        <button
          className="btn"
          style={tab === 'activity' ? { borderColor: 'var(--primary)' } : undefined}
          onClick={() => setTab('activity')}
        >
          Activity Log
        </button>
        <button
          className="btn"
          style={tab === 'versions' ? { borderColor: 'var(--primary)' } : undefined}
          onClick={() => setTab('versions')}
        >
          Version History
        </button>
      </div>

      {tab === 'activity' ? <ActivityLog /> : <VersionHistory />}
    </div>
  )
}

function ActivityLog() {
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null)
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 25

  function load() {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (query) params.set('q', query)
    if (actionFilter) params.set('action', actionFilter)
    api
      .get<AuditLogListResponse>(`/audit-logs?${params.toString()}`)
      .then((res) => {
        setEntries(res.items)
        setTotal(res.total)
      })
  }

  useEffect(load, [query, actionFilter, offset])

  function handleSearchChange(value: string) {
    setOffset(0)
    setQuery(value)
  }

  function handleActionChange(value: string) {
    setOffset(0)
    setActionFilter(value)
  }

  return (
    <div>
      <div className="toolbar">
        <input
          placeholder="Search by actor, action, or target..."
          value={query}
          onChange={(e) => handleSearchChange(e.target.value)}
          style={{ maxWidth: 320 }}
        />
        <select
          value={actionFilter}
          onChange={(e) => handleActionChange(e.target.value)}
          style={{ width: 220 }}
        >
          <option value="">All actions</option>
          {KNOWN_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        {entries === null ? (
          <p className="muted">Loading...</p>
        ) : entries.length === 0 ? (
          <p className="empty-state">No matching activity.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Target</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="muted">{new Date(entry.created_at).toLocaleString()}</td>
                  <td>{entry.actor_email}</td>
                  <td>
                    <code>{entry.action}</code>
                  </td>
                  <td className="muted">
                    {entry.target_type
                      ? `${entry.target_type}${entry.target_id ? ` (${entry.target_id.slice(0, 8)})` : ''}`
                      : '-'}
                  </td>
                  <td className="muted" style={{ maxWidth: 280 }}>
                    {Object.keys(entry.details).length > 0 ? JSON.stringify(entry.details) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > limit && (
        <div className="toolbar" style={{ justifyContent: 'flex-end' }}>
          <button
            className="btn"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - limit))}
          >
            ← Newer
          </button>
          <span className="muted" style={{ fontSize: 13 }}>
            {offset + 1}-{Math.min(offset + limit, total)} of {total}
          </span>
          <button
            className="btn"
            disabled={offset + limit >= total}
            onClick={() => setOffset((o) => o + limit)}
          >
            Older →
          </button>
        </div>
      )}
    </div>
  )
}

function VersionHistory() {
  const [releases, setReleases] = useState<Release[] | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [version, setVersion] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.get<Release[]>('/releases').then(setReleases)
  }

  useEffect(load, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.post('/releases', { version, title, description: description || null })
      setVersion('')
      setTitle('')
      setDescription('')
      setShowForm(false)
      load()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? 'Only workspace owners/admins can add version entries.'
            : err.message
          : 'Could not add version entry',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="toolbar">
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'Add version entry'}
        </button>
      </div>

      {showForm && (
        <form className="card" onSubmit={handleSubmit} style={{ marginBottom: 16, maxWidth: 480 }}>
          <div className="form-row">
            <label htmlFor="rel-version">Version</label>
            <input
              id="rel-version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="0.7.0"
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="rel-title">Title</label>
            <input
              id="rel-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Short summary of what shipped"
              required
            />
          </div>
          <div className="form-row">
            <label htmlFor="rel-description">Details (optional)</label>
            <textarea
              id="rel-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </form>
      )}

      {releases === null ? (
        <p className="muted">Loading...</p>
      ) : releases.length === 0 ? (
        <p className="empty-state">No version history recorded yet.</p>
      ) : (
        releases.map((r) => (
          <div className="card" key={r.id}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
              <span className="badge badge-active">v{r.version}</span>
              <strong>{r.title}</strong>
              <span className="muted" style={{ fontSize: 12, marginLeft: 'auto' }}>
                {new Date(r.released_at).toLocaleDateString()}
              </span>
            </div>
            {r.description && (
              <p style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{r.description}</p>
            )}
          </div>
        ))
      )}
    </div>
  )
}
