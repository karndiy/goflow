import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { CalendarEntry } from '../api/types'
import StatusBadge from '../components/StatusBadge'

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}
function startOfCalendarGrid(d: Date) {
  const start = startOfMonth(d)
  const day = start.getDay()
  const grid = new Date(start)
  grid.setDate(start.getDate() - day)
  return grid
}

export default function CalendarPage() {
  const [month, setMonth] = useState(() => startOfMonth(new Date()))
  const [entries, setEntries] = useState<CalendarEntry[]>([])

  const gridStart = useMemo(() => startOfCalendarGrid(month), [month])
  const days = useMemo(
    () => Array.from({ length: 42 }, (_, i) => {
      const d = new Date(gridStart)
      d.setDate(gridStart.getDate() + i)
      return d
    }),
    [gridStart],
  )

  useEffect(() => {
    const start = days[0]
    const end = new Date(days[41])
    end.setDate(end.getDate() + 1)
    api
      .get<CalendarEntry[]>(
        `/publishing/calendar?start=${start.toISOString()}&end=${end.toISOString()}`,
      )
      .then(setEntries)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gridStart])

  const entriesByDay = useMemo(() => {
    const map = new Map<string, CalendarEntry[]>()
    for (const entry of entries) {
      const key = new Date(entry.scheduled_at).toDateString()
      map.set(key, [...(map.get(key) ?? []), entry])
    }
    return map
  }, [entries])

  return (
    <div>
      <div className="page-header">
        <h1>Calendar</h1>
        <div className="toolbar" style={{ margin: 0 }}>
          <button
            className="btn"
            onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
          >
            ← Prev
          </button>
          <strong>{month.toLocaleString(undefined, { month: 'long', year: 'numeric' })}</strong>
          <button
            className="btn"
            onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
          >
            Next →
          </button>
        </div>
      </div>

      <div
        className="card"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1, padding: 1 }}
      >
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
          <div key={d} style={{ padding: 8, fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>
            {d}
          </div>
        ))}
        {days.map((day) => {
          const inMonth = day.getMonth() === month.getMonth()
          const dayEntries = entriesByDay.get(day.toDateString()) ?? []
          return (
            <div
              key={day.toISOString()}
              style={{
                minHeight: 100,
                background: inMonth ? 'var(--surface)' : '#fafafb',
                padding: 6,
                fontSize: 12,
              }}
            >
              <div style={{ color: inMonth ? 'var(--text)' : 'var(--text-muted)', marginBottom: 4 }}>
                {day.getDate()}
              </div>
              {dayEntries.map((e) => (
                <div key={e.job_id} style={{ marginBottom: 3 }} title={e.content_title}>
                  <StatusBadge status={e.status} />{' '}
                  <span style={{ display: 'block' }}>
                    {e.content_title} <span className="muted">({e.platform})</span>
                  </span>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
