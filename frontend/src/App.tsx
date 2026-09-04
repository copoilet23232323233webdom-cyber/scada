import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import PlantDetail from './pages/PlantDetail'
import GatewayControl from './pages/GatewayControl'
import AdminUsers from './pages/AdminUsers'
import Login from './pages/Login'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div></div>
  return user ? <>{children}</> : <Navigate to="/login" />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="plant/:plantId" element={<PlantDetail />} />
        <Route path="gateway/:id/control" element={<GatewayControl />} />
        <Route path="admin/users" element={<AdminUsers />} />
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
