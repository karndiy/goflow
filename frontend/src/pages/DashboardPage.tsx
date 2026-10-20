import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { DashboardSummary } from '../api/types'
import StatusBadge from '../components/StatusBadge'

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .get<DashboardSummary>('/dashboard/summary')
      .then(setSummary)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="muted">Loading...</p>
  if (!summary) return <p className="muted">Could not load dashboard data.</p>

  const totalContent = Object.values(summary.content_by_status).reduce((a, b) => a + b, 0)
  const activeJobs =
    (summary.jobs_by_status.scheduled ?? 0) +
    (summary.jobs_by_status.queued ?? 0) +
    (summary.jobs_by_status.publishing ?? 0) +
    (summary.jobs_by_status.processing ?? 0)
  const failedJobs = (summary.jobs_by_status.failed ?? 0) + (summary.jobs_by_status.unknown ?? 0)

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
      </div>

      <div className="grid grid-cols-4">
        <div className="stat-tile">
          <div className="value">{totalContent}</div>
          <div className="label">Total drafts &amp; posts</div>
        </div>
        <div className="stat-tile">
          <div className="value">{activeJobs}</div>
          <div className="label">Active publishing jobs</div>
        </div>
        <div className="stat-tile">
          <div className="value">{summary.jobs_by_status.published ?? 0}</div>
          <div className="label">Published</div>
        </div>
        <div className="stat-tile">
          <div className="value">{failedJobs}</div>
          <div className="label">Failed / needs attention</div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Content by status</h3>
        {totalContent === 0 ? (
          <p className="empty-state">No content yet. Head to Content Studio to create a draft.</p>
        ) : (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {Object.entries(summary.content_by_status).map(([status, count]) => (
              <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <StatusBadge status={status} /> <span>{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Connected accounts</h3>
        {summary.accounts.length === 0 ? (
          <p className="empty-state">No social accounts connected yet.</p>
        ) : (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {summary.accounts.map((a) => (
              <div key={`${a.platform}-${a.status}`} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <strong>{a.platform}</strong>
                <StatusBadge status={a.status} />
                <span className="muted">x{a.count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
