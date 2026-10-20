import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AuditLogEntry, AuditLogListResponse } from '../api/types'

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
]

export default function UpdateLogPage() {
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
      <div className="page-header">
        <h1>Update Log</h1>
      </div>

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
