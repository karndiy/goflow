import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) return <p className="muted" style={{ padding: 24 }}>Loading...</p>
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
