import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ContentStudioPage from './pages/ContentStudioPage'
import ContentDetailPage from './pages/ContentDetailPage'
import AccountsPage from './pages/AccountsPage'
import QueuePage from './pages/QueuePage'
import CalendarPage from './pages/CalendarPage'
import SettingsPage from './pages/SettingsPage'
import UpdateLogPage from './pages/UpdateLogPage'
import RequestsPage from './pages/RequestsPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/content" element={<ContentStudioPage />} />
              <Route path="/content/:id" element={<ContentDetailPage />} />
              <Route path="/queue" element={<QueuePage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/accounts" element={<AccountsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/updates" element={<UpdateLogPage />} />
              <Route path="/requests" element={<RequestsPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
