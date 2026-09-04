import { useEffect, useState } from 'react'
import { usersAPI } from '../services/api'
import { User } from '../types'
import { UserPlus, Edit2, Trash2, Shield, User as UserIcon } from 'lucide-react'

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'client',
    assigned_plants: ''
  })
  const [editingId, setEditingId] = useState<number | null>(null)

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    try {
      const response = await usersAPI.getAll()
      setUsers(response.data)
    } catch (error) {
      console.error('Error cargando usuarios:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingId) {
        await usersAPI.update(editingId, {
          email: formData.email,
          full_name: formData.full_name,
          role: formData.role,
          assigned_plants: formData.assigned_plants
        })
      } else {
        await usersAPI.create(formData)
      }
      setShowForm(false)
      setEditingId(null)
      setFormData({ username: '', email: '', password: '', full_name: '', role: 'client', assigned_plants: '' })
      loadUsers()
    } catch (error) {
      console.error('Error guardando usuario:', error)
    }
  }

  const handleEdit = (user: User) => {
    setEditingId(user.id)
    setFormData({
      username: user.username,
      email: user.email,
      password: '',
      full_name: user.full_name || '',
      role: user.role,
      assigned_plants: user.assigned_plants || ''
    })
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Estás seguro de eliminar este usuario?')) return
    try {
      await usersAPI.delete(id)
      loadUsers()
    } catch (error) {
      console.error('Error eliminando usuario:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Administración de Usuarios</h1>
        <button
          onClick={() => { setShowForm(true); setEditingId(null); setFormData({ username: '', email: '', password: '', full_name: '', role: 'client', assigned_plants: '' }) }}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          <UserPlus className="h-5 w-5" />
          <span>Nuevo Usuario</span>
        </button>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-8 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold mb-6">{editingId ? 'Editar Usuario' : 'Nuevo Usuario'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                  disabled={!!editingId}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              {!editingId && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre Completo</label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="client">Cliente</option>
                  <option value="admin">Administrador</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plantas Asignadas (separadas por coma)</label>
                <input
                  type="text"
                  value={formData.assigned_plants}
                  onChange={(e) => setFormData({...formData, assigned_plants: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="Olivenza, Torralba"
                />
              </div>
              <div className="flex space-x-3 pt-4">
                <button type="submit" className="flex-1 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700">
                  {editingId ? 'Actualizar' : 'Crear'}
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="flex-1 bg-gray-200 text-gray-700 py-2 rounded-lg hover:bg-gray-300">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-md overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Usuario</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rol</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Plantas</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-blue-100 rounded-lg">
                      {user.role === 'admin' ? <Shield className="h-5 w-5 text-blue-600" /> : <UserIcon className="h-5 w-5 text-gray-600" />}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{user.username}</div>
                      <div className="text-sm text-gray-500">{user.full_name}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">{user.email}</td>
                <td className="px-6 py-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    user.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {user.role}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">{user.assigned_plants || 'Todas'}</td>
                <td className="px-6 py-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {user.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <button onClick={() => handleEdit(user)} className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg mr-2">
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button onClick={() => handleDelete(user.id)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}