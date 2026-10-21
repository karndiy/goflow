import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Content, ContentVariant, GenerationJob, MediaAsset, SocialAccount } from '../api/types'
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

  const [genPlatform, setGenPlatform] = useState('mock')
  const [genBrief, setGenBrief] = useState('')
  const [activeJob, setActiveJob] = useState<GenerationJob | null>(null)
  const pollRef = useRef<number | null>(null)

  function load() {
    if (!id) return
    api.get<Content>(`/contents/${id}`).then(setContent)
    api.get<ContentVariant[]>(`/contents/${id}/variants`).then(setVariants)
    api.get<SocialAccount[]>('/accounts').then(setAccounts)
  }

  useEffect(load, [id])

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [])

  async function handleGenerate(e: FormEvent) {
    e.preventDefault()
    if (!id || !genBrief.trim()) return
    setError(null)
    try {
      const job = await api.post<GenerationJob>(`/contents/${id}/generate`, {
        platform: genPlatform,
        brief: genBrief,
      })
      setActiveJob(job)
      setGenBrief('')

      pollRef.current = window.setInterval(async () => {
        const updated = await api.get<GenerationJob>(
          `/contents/${id}/generation-jobs/${job.id}`,
        )
        setActiveJob(updated)
        if (updated.status === 'completed' || updated.status === 'failed') {
          if (pollRef.current) window.clearInterval(pollRef.current)
          pollRef.current = null
          if (updated.status === 'completed') load()
        }
      }, 1500)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? 'The AI assistant is not configured yet. Set an Anthropic API key in Settings.'
            : err.message
          : 'Could not start generation',
      )
    }
  }

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

  async function handleUploadMedia(variant: ContentVariant, file: File) {
    if (!id) return
    setError(null)
    try {
      const asset = await api.upload<MediaAsset>('/media', file)
      await api.put(`/contents/${id}/variants/${variant.id}/media`, {
        media_asset_ids: [...variant.media.map((m) => m.id), asset.id],
      })
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not upload media')
    }
  }

  async function handleRemoveMedia(variant: ContentVariant, mediaId: string) {
    if (!id) return
    setError(null)
    try {
      await api.put(`/contents/${id}/variants/${variant.id}/media`, {
        media_asset_ids: variant.media.filter((m) => m.id !== mediaId).map((m) => m.id),
      })
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not remove media')
    }
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

      {content.status === 'draft' && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Write with Claude</h3>
          <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
            Describe what you want, and Claude will draft (or redraft) the variant for that
            platform. You can still edit it by hand afterward.
          </p>
          <form
            onSubmit={handleGenerate}
            style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}
          >
            <select
              value={genPlatform}
              onChange={(e) => setGenPlatform(e.target.value)}
              style={{ width: 140 }}
            >
              <option value="mock">mock</option>
              <option value="facebook">facebook</option>
              <option value="tiktok">tiktok</option>
            </select>
            <textarea
              placeholder="e.g. Announce our new dark mode feature, upbeat tone, one emoji"
              value={genBrief}
              onChange={(e) => setGenBrief(e.target.value)}
              rows={2}
              style={{ flex: 1 }}
            />
            <button
              className="btn btn-primary"
              type="submit"
              disabled={activeJob !== null && activeJob.status !== 'completed' && activeJob.status !== 'failed'}
            >
              Generate with Claude
            </button>
          </form>

          {activeJob && (
            <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <StatusBadge status={activeJob.status} />
              <span className="muted" style={{ fontSize: 13 }}>
                {activeJob.platform}
                {activeJob.status === 'failed' && activeJob.error_message
                  ? `: ${activeJob.error_message}`
                  : ''}
              </span>
            </div>
          )}
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

              {v.media.length > 0 && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  {v.media.map((m) => (
                    <div key={m.id} style={{ position: 'relative' }}>
                      {m.mime_type.startsWith('image/') ? (
                        <img
                          src={m.file_url}
                          alt={m.filename ?? 'media'}
                          style={{
                            width: 72,
                            height: 72,
                            objectFit: 'cover',
                            borderRadius: 4,
                            border: '1px solid #ddd',
                          }}
                        />
                      ) : (
                        <div
                          className="muted"
                          style={{
                            width: 72,
                            height: 72,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            border: '1px solid #ddd',
                            borderRadius: 4,
                            fontSize: 11,
                            textAlign: 'center',
                            padding: 4,
                          }}
                        >
                          {m.filename ?? 'video'}
                        </div>
                      )}
                      {content.status === 'draft' && (
                        <button
                          className="btn btn-danger"
                          title="Remove media"
                          style={{
                            position: 'absolute',
                            top: -8,
                            right: -8,
                            padding: '0 6px',
                            fontSize: 11,
                            lineHeight: '18px',
                          }}
                          onClick={() => handleRemoveMedia(v, m.id)}
                        >
                          x
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {content.status === 'draft' && (
                <label className="btn" style={{ display: 'inline-block', cursor: 'pointer', fontSize: 13, marginBottom: 8 }}>
                  Add media
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) handleUploadMedia(v, file)
                      e.target.value = ''
                    }}
                  />
                </label>
              )}

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
              <option value="tiktok">tiktok</option>
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
