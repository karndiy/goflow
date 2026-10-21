import { useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { SocialAccount } from '../api/types'
import StatusBadge from '../components/StatusBadge'

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<SocialAccount[] | null>(null)
  const [connectError, setConnectError] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(false)

  function load() {
    api.get<SocialAccount[]>('/accounts').then(setAccounts)
  }

  useEffect(load, [])

  async function connectFacebook() {
    setConnectError(null)
    setConnecting(true)
    try {
      const { authorization_url } = await api.post<{ authorization_url: string }>(
        '/accounts/facebook/connect',
      )
      window.location.href = authorization_url
    } catch (err) {
      setConnectError(
        err instanceof ApiError
          ? err.status === 503
            ? 'Facebook integration is not configured on the server (missing META_APP_ID/META_APP_SECRET).'
            : err.message
          : 'Could not start Facebook connection',
      )
    } finally {
      setConnecting(false)
    }
  }

  async function connectTikTok() {
    setConnectError(null)
    setConnecting(true)
    try {
      const { authorization_url } = await api.post<{ authorization_url: string }>(
        '/accounts/tiktok/connect',
      )
      window.location.href = authorization_url
    } catch (err) {
      setConnectError(
        err instanceof ApiError
          ? err.status === 503
            ? 'TikTok integration is not configured on the server (missing TIKTOK_CLIENT_KEY/TIKTOK_CLIENT_SECRET, or set it in Settings).'
            : err.message
          : 'Could not start TikTok connection',
      )
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Accounts</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={connectFacebook} disabled={connecting}>
            {connecting ? 'Connecting...' : 'Connect Facebook Page'}
          </button>
          <button className="btn btn-primary" onClick={connectTikTok} disabled={connecting}>
            {connecting ? 'Connecting...' : 'Connect TikTok'}
          </button>
        </div>
      </div>

      {connectError && (
        <div className="card" style={{ borderColor: '#f3c7c7', marginBottom: 14 }}>
          <p className="error-text" style={{ margin: 0 }}>
            {connectError}
          </p>
        </div>
      )}

      <div className="card">
        {accounts === null ? (
          <p className="muted">Loading...</p>
        ) : accounts.length === 0 ? (
          <p className="empty-state">
            No social accounts connected yet. Connect a Facebook Page or TikTok account to get
            started.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Platform</th>
                <th>Account</th>
                <th>Status</th>
                <th>Connected</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td style={{ textTransform: 'capitalize' }}>{a.platform}</td>
                  <td>{a.account_name}</td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="muted">{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
