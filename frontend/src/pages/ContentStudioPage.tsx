import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Content, ContentListResponse } from '../api/types'
import StatusBadge from '../components/StatusBadge'

export default function ContentStudioPage() {
  const navigate = useNavigate()
  const [contents, setContents] = useState<Content[] | null>(null)
  const [title, setTitle] = useState('')
  const [creating, setCreating] = useState(false)

  function load() {
    api.get<ContentListResponse>('/contents?limit=100').then((res) => setContents(res.items))
  }

  useEffect(load, [])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    setCreating(true)
    try {
      const content = await api.post<Content>('/contents', { title })
      setTitle('')
      navigate(`/content/${content.id}`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Content Studio</h1>
      </div>

      <form className="card toolbar" onSubmit={handleCreate} style={{ marginBottom: 16 }}>
        <input
          placeholder="New draft title..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={creating}>
          Create draft
        </button>
      </form>

      <div className="card">
        {contents === null ? (
          <p className="muted">Loading...</p>
        ) : contents.length === 0 ? (
          <p className="empty-state">No drafts yet. Create one above to get started.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {contents.map((c) => (
                <tr
                  key={c.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/content/${c.id}`)}
                >
                  <td>{c.title}</td>
                  <td>
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="muted">{new Date(c.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
