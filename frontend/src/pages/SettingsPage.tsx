import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { AISettings, PlatformCredential, Workspace } from '../api/types'

const CLAUDE_MODELS = ['claude-opus-5', 'claude-sonnet-5', 'claude-haiku-4-5']

const COMMON_TIMEZONES = [
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'America/Chicago',
  'Australia/Sydney',
  'UTC',
]

const SUPPORTED_PLATFORMS = ['facebook', 'tiktok'] as const

export default function SettingsPage() {
  const { user } = useAuth()
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.get<Workspace>('/workspace').then((ws) => {
      setWorkspace(ws)
      setName(ws.name)
      setTimezone(ws.timezone)
    })
  }, [])

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    setSaving(true)
    try {
      const updated = await api.patch<Workspace>('/workspace', { name, timezone })
      setWorkspace(updated)
      setSaved(true)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? 'Only workspace owners/admins can change these settings.'
            : err.message
          : 'Could not save settings',
      )
    } finally {
      setSaving(false)
    }
  }

  if (!workspace) return <p className="muted">Loading...</p>

  const timezoneOptions = COMMON_TIMEZONES.includes(timezone)
    ? COMMON_TIMEZONES
    : [timezone, ...COMMON_TIMEZONES]

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <h3 style={{ marginTop: 0 }}>Workspace</h3>
        <form onSubmit={handleSave}>
          <div className="form-row">
            <label htmlFor="ws-name">Workspace name</label>
            <input id="ws-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="form-row">
            <label htmlFor="ws-timezone">Timezone</label>
            <select id="ws-timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {timezoneOptions.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
          {error && <p className="error-text">{error}</p>}
          {saved && !error && (
            <p className="muted" style={{ fontSize: 13 }}>
              Saved.
            </p>
          )}
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </form>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <h3 style={{ marginTop: 0 }}>Account</h3>
        <p>
          <strong>Email:</strong> {user?.email}
        </p>
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Workspace created {new Date(workspace.created_at).toLocaleDateString()}
        </p>
      </div>

      <PlatformCredentialsSection />
      <AISettingsSection />
    </div>
  )
}

function AISettingsSection() {
  const [settings, setSettings] = useState<AISettings | null>(null)
  const [editing, setEditing] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('claude-opus-5')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function load() {
    api.get<AISettings>('/settings/ai').then((s) => {
      setSettings(s)
      if (s.model) setModel(s.model)
    })
  }

  useEffect(load, [])

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.put('/settings/ai', { api_key: apiKey, model })
      setApiKey('')
      setEditing(false)
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save AI settings')
    } finally {
      setSaving(false)
    }
  }

  if (!settings) return null

  return (
    <div className="card" style={{ maxWidth: 480 }}>
      <h3 style={{ marginTop: 0 }}>AI Assistant (Claude)</h3>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        Powers the Requests page and AI-assisted content writing. Your Anthropic API key is
        encrypted at rest.
      </p>
      <p>
        {settings.has_api_key ? (
          <span className="badge badge-active">configured ({settings.model})</span>
        ) : (
          <span className="badge badge-draft">not configured</span>
        )}
      </p>

      {editing ? (
        <form onSubmit={handleSave} style={{ display: 'grid', gap: 8, maxWidth: 320 }}>
          <input
            placeholder="Anthropic API key (sk-ant-...)"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            required
          />
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {CLAUDE_MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          {error && <p className="error-text">{error}</p>}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button className="btn" type="button" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button className="btn" onClick={() => setEditing(true)}>
          {settings.has_api_key ? 'Update' : 'Set up'}
        </button>
      )}
    </div>
  )
}

function PlatformCredentialsSection() {
  const [credentials, setCredentials] = useState<PlatformCredential[] | null>(null)

  function load() {
    api.get<PlatformCredential[]>('/settings/platform-credentials').then(setCredentials)
  }

  useEffect(load, [])

  if (credentials === null) return null
  const byPlatform = new Map(credentials.map((c) => [c.platform, c]))

  return (
    <div className="card" style={{ maxWidth: 480 }}>
      <h3 style={{ marginTop: 0 }}>Platform API keys</h3>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        App-level credentials used to connect Facebook/TikTok accounts via OAuth. These are
        encrypted at rest and never shown back in full.
      </p>
      {SUPPORTED_PLATFORMS.map((platform) => (
        <PlatformCredentialRow
          key={platform}
          platform={platform}
          credential={byPlatform.get(platform) ?? null}
          onChanged={load}
        />
      ))}
    </div>
  )
}

function PlatformCredentialRow({
  platform,
  credential,
  onChanged,
}: {
  platform: string
  credential: PlatformCredential | null
  onChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [appId, setAppId] = useState(credential?.app_id ?? '')
  const [appSecret, setAppSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.put(`/settings/platform-credentials/${platform}`, {
        app_id: appId,
        app_secret: appSecret,
      })
      setAppSecret('')
      setEditing(false)
      onChanged()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : `Could not save ${platform} credentials`,
      )
    } finally {
      setSaving(false)
    }
  }

  async function handleRemove() {
    await api.delete(`/settings/platform-credentials/${platform}`)
    onChanged()
  }

  return (
    <div className="variant-row">
      <div style={{ flex: 1 }}>
        <strong style={{ textTransform: 'capitalize' }}>{platform}</strong>{' '}
        {credential ? (
          <span className="badge badge-active">configured</span>
        ) : (
          <span className="badge badge-draft">not configured</span>
        )}
        {credential && !editing && (
          <p className="muted" style={{ fontSize: 13, margin: '4px 0' }}>
            App ID: {credential.app_id}
          </p>
        )}

        {editing ? (
          <form onSubmit={handleSave} style={{ marginTop: 8, display: 'grid', gap: 8, maxWidth: 320 }}>
            <input
              placeholder="App ID"
              value={appId}
              onChange={(e) => setAppId(e.target.value)}
              required
            />
            <input
              placeholder="App Secret"
              type="password"
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
              required
            />
            {error && <p className="error-text">{error}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" type="submit" disabled={saving}>
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button className="btn" type="button" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => setEditing(true)}>
              {credential ? 'Update' : 'Set up'}
            </button>
            {credential && (
              <button className="btn btn-danger" onClick={handleRemove}>
                Remove
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
