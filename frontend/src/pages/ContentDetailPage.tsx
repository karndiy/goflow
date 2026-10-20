import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Content, ContentVariant, SocialAccount } from '../api/types'
import StatusBadge from '../components/StatusBadge'

const CANCELLABLE_STATUSES = ['scheduled', 'publishing', 'partial_failure']
const SCHEDULABLE_STATUSES = ['draft', 'failed', 'partial_failure']

export default function ContentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [content, setContent] = useState<Content | null>(null)
  const [variants, setVariants] = useState<ContentVariant[]>([])
  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [error, setError] = useState<string | null>(null)

  const [newPlatform, setNewPlatform] = useState('mock')
  const [newText, setNewText] = useState('')

  const [scheduleAccountId, setScheduleAccountId] = useState<Record<string, string>>({})
  const [scheduleAt, setScheduleAt] = useState<Record<string, string>>({})

  function load() {
    if (!id) return
    api.get<Content>(`/contents/${id}`).then(setContent)
    api.get<ContentVariant[]>(`/contents/${id}/variants`).then(setVariants)
    api.get<SocialAccount[]>('/accounts').then(setAccounts)
  }

  useEffect(load, [id])

  async function handleAddVariant(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setError(null)
    try {
      await api.post(`/contents/${id}/variants`, {
        platform: newPlatform,
        text: newText,
        media_type: 'none',
      })
      setNewText('')
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add variant')
    }
  }

  async function handleDeleteVariant(variantId: string) {
    if (!id) return
    await api.delete(`/contents/${id}/variants/${variantId}`)
    load()
  }

  async function handleSchedule(platform: string) {
    if (!id) return
    const accountId = scheduleAccountId[platform]
    const at = scheduleAt[platform]
    if (!accountId || !at) {
      setError('Pick an account and a date/time before scheduling')
      return
    }
    setError(null)
    try {
      await api.post(`/contents/${id}/schedule`, {
        assignments: [
          {
            social_account_id: accountId,
            platform,
            scheduled_at: new Date(at).toISOString(),
          },
        ],
      })
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not schedule')
    }
  }

  async function handleCancel() {
    if (!id) return
    await api.post(`/contents/${id}/cancel`)
    load()
  }

  async function handleDeleteContent() {
    if (!id) return
    await api.delete(`/contents/${id}`)
    navigate('/content')
  }

  if (!content) return <p className="muted">Loading...</p>

  const accountsByPlatform = (platform: string) => accounts.filter((a) => a.platform === platform)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 style={{ marginBottom: 4 }}>{content.title}</h1>
          <StatusBadge status={content.status} />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {CANCELLABLE_STATUSES.includes(content.status) && (
            <button className="btn" onClick={handleCancel}>
              Cancel scheduled posts
            </button>
          )}
          {content.status === 'draft' && (
            <button className="btn btn-danger" onClick={handleDeleteContent}>
              Delete draft
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: '#f3c7c7', marginBottom: 14 }}>
          <p className="error-text" style={{ margin: 0 }}>
            {error}
          </p>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Platform variants</h3>
        {variants.length === 0 && <p className="empty-state">No variants yet. Add one below.</p>}
        {variants.map((v) => (
          <div className="variant-row" key={v.id}>
            <div style={{ flex: 1 }}>
              <strong style={{ textTransform: 'capitalize' }}>{v.platform}</strong>
              <p style={{ margin: '4px 0' }}>{v.text || <span className="muted">(empty)</span>}</p>

              {SCHEDULABLE_STATUSES.includes(content.status) && (
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
                  <select
                    value={scheduleAccountId[v.platform] ?? ''}
                    onChange={(e) =>
                      setScheduleAccountId((prev) => ({ ...prev, [v.platform]: e.target.value }))
                    }
                    style={{ width: 200 }}
                  >
                    <option value="">Select account...</option>
                    {accountsByPlatform(v.platform).map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.account_name}
                      </option>
                    ))}
                  </select>
                  <input
                    type="datetime-local"
                    style={{ width: 200 }}
                    value={scheduleAt[v.platform] ?? ''}
                    onChange={(e) =>
                      setScheduleAt((prev) => ({ ...prev, [v.platform]: e.target.value }))
                    }
                  />
                  <button className="btn btn-primary" onClick={() => handleSchedule(v.platform)}>
                    Schedule
                  </button>
                </div>
              )}
            </div>
            {content.status === 'draft' && (
              <button className="btn btn-danger" onClick={() => handleDeleteVariant(v.id)}>
                Remove
              </button>
            )}
          </div>
        ))}

        {content.status === 'draft' && (
          <form
            onSubmit={handleAddVariant}
            style={{ display: 'flex', gap: 8, marginTop: 14, alignItems: 'flex-start' }}
          >
            <select
              value={newPlatform}
              onChange={(e) => setNewPlatform(e.target.value)}
              style={{ width: 140 }}
            >
              <option value="mock">mock</option>
              <option value="facebook">facebook</option>
            </select>
            <textarea
              placeholder="Post text for this platform..."
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
              rows={2}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" type="submit">
              Add variant
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
