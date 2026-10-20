import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { JobListResponse, PublishingJob } from '../api/types'
import StatusBadge from '../components/StatusBadge'

const STATUS_FILTERS = [
  'all',
  'scheduled',
  'queued',
  'publishing',
  'processing',
  'published',
  'failed',
  'unknown',
  'cancelled',
]

export default function QueuePage() {
  const [jobs, setJobs] = useState<PublishingJob[] | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [retrying, setRetrying] = useState<string | null>(null)

  function load() {
    const query = statusFilter === 'all' ? '' : `&status=${statusFilter}`
    api
      .get<JobListResponse>(`/publishing/jobs?limit=100${query}`)
      .then((res) => setJobs(res.items))
  }

  useEffect(load, [statusFilter])

  async function handleRetry(jobId: string) {
    setRetrying(jobId)
    try {
      await api.post(`/publishing/jobs/${jobId}/retry`)
      load()
    } finally {
      setRetrying(null)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Publishing Queue</h1>
      </div>

      <div className="toolbar">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 200 }}>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All statuses' : s}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        {jobs === null ? (
          <p className="muted">Loading...</p>
        ) : jobs.length === 0 ? (
          <p className="empty-state">No publishing jobs match this filter.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Scheduled for</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Last error</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{new Date(job.scheduled_at).toLocaleString()}</td>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td>{job.attempts}</td>
                  <td className="muted" style={{ maxWidth: 320 }}>
                    {job.last_error ?? '-'}
                  </td>
                  <td>
                    {(job.status === 'failed' || job.status === 'unknown') && (
                      <button
                        className="btn"
                        onClick={() => handleRetry(job.id)}
                        disabled={retrying === job.id}
                      >
                        {retrying === job.id ? 'Retrying...' : 'Retry'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
