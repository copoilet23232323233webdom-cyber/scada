import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LayoutDashboard, LogOut, Moon, Sun, Users, Activity } from 'lucide-react'
import { useState } from 'react'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [darkMode, setDarkMode] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const isActive = (path: string) => location.pathname === path

  return (
    <div className={`min-h-screen ${darkMode ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <nav className={`${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b shadow-sm`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-6">
              <Link to="/" className="flex items-center space-x-2">
                <LayoutDashboard className="h-8 w-8 text-blue-600" />
                <span className={`text-xl font-bold ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                  Webdom Monitor
                </span>
              </Link>
              
              <div className="hidden md:flex items-center space-x-1">
                <Link
                  to="/"
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive('/') 
                      ? 'bg-blue-100 text-blue-700' 
                      : `${darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100'}`
                  }`}
                >
                  <Activity className="h-4 w-4 inline mr-1" />
                  Dashboard
                </Link>
                
                {user?.role === 'admin' && (
                  <Link
                    to="/admin/users"
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive('/admin/users') 
                        ? 'bg-blue-100 text-blue-700' 
                        : `${darkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-600 hover:bg-gray-100'}`
                    }`}
                  >
                    <Users className="h-4 w-4 inline mr-1" />
                    Usuarios
                  </Link>
                )}
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setDarkMode(!darkMode)}
                className={`p-2 rounded-lg ${darkMode ? 'bg-gray-700 text-yellow-400' : 'bg-gray-100 text-gray-600'}`}
              >
                {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
              
              <div className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                {user?.username} ({user?.role})
              </div>
              
              <button
                onClick={handleLogout}
                className="flex items-center space-x-1 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg"
              >
                <LogOut className="h-4 w-4" />
                <span>Salir</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
