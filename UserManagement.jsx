import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  UserPlus,
  Edit,
  Trash2,
  Key,
  Loader2,
  Shield,
  ShieldAlert,
  ShieldCheck
} from 'lucide-react'

import { apiFetch } from './apiClient'
import { useToast } from './components/ToastProvider'

function UserManagement() {
  const { showToast } = useToast()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [mfaDialogOpen, setMfaDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [deletingUser, setDeletingUser] = useState(null)
  const [mfaUser, setMfaUser] = useState(null)
  const [mfaSecret, setMfaSecret] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    role: 'viewer',
    mfa_enabled: false
  })
  const [editFormData, setEditFormData] = useState({
    role: '',
    is_active: true,
    reset_password: ''
  })

  // Fetch users
  const fetchUsers = async () => {
    try {
      setLoading(true)
      const response = await apiFetch('/users')
      const data = await response.json()
      setUsers(data)
    } catch (error) {
      console.error('Failed to fetch users:', error)
      showToast({
        type: 'error',
        title: 'Kullanıcılar yüklenemedi',
        description: error?.message || 'Kullanıcı listesi alınırken hata oluştu.'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  // Create user
  const handleCreate = async () => {
    if (!formData.username || !formData.password) {
      showToast({
        type: 'error',
        title: 'Eksik bilgi',
        description: 'Kullanıcı adı ve şifre zorunludur.'
      })
      return
    }

    if (formData.password.length < 6) {
      showToast({
        type: 'error',
        title: 'Zayıf şifre',
        description: 'Şifre en az 6 karakter olmalıdır.'
      })
      return
    }

    try {
      setSubmitting(true)
      await apiFetch('/users', {
        method: 'POST',
        body: formData
      })
      showToast({
        type: 'success',
        title: 'Kullanıcı oluşturuldu',
        description: `${formData.username} başarıyla eklendi.`
      })
      setAddDialogOpen(false)
      setFormData({ username: '', password: '', role: 'viewer', mfa_enabled: false })
      fetchUsers()
    } catch (error) {
      console.error('Failed to create user:', error)
      showToast({
        type: 'error',
        title: 'Kullanıcı oluşturulamadı',
        description: error?.message || 'Kullanıcı eklenirken hata oluştu.'
      })
    } finally {
      setSubmitting(false)
    }
  }

  // Update user
  const handleUpdate = async () => {
    if (!editingUser) return

    const payload = {}
    if (editFormData.role && editFormData.role !== editingUser.role) {
      payload.role = editFormData.role
    }
    if (editFormData.is_active !== editingUser.is_active) {
      payload.is_active = editFormData.is_active
    }
    if (editFormData.reset_password) {
      if (editFormData.reset_password.length < 6) {
        showToast({
          type: 'error',
          title: 'Zayıf şifre',
          description: 'Şifre en az 6 karakter olmalıdır.'
        })
        return
      }
      payload.reset_password = editFormData.reset_password
    }

    if (Object.keys(payload).length === 0) {
      showToast({
        type: 'info',
        title: 'Değişiklik yok',
        description: 'Güncellenecek bir alan seçilmedi.'
      })
      return
    }

    try {
      setSubmitting(true)
      await apiFetch(`/users/${editingUser.id}`, {
        method: 'PATCH',
        body: payload
      })
      showToast({
        type: 'success',
        title: 'Kullanıcı güncellendi',
        description: `${editingUser.username} başarıyla güncellendi.`
      })
      setEditDialogOpen(false)
      setEditingUser(null)
      setEditFormData({ role: '', is_active: true, reset_password: '' })
      fetchUsers()
    } catch (error) {
      console.error('Failed to update user:', error)
      showToast({
        type: 'error',
        title: 'Kullanıcı güncellenemedi',
        description: error?.message || 'Kullanıcı güncellenirken hata oluştu.'
      })
    } finally {
      setSubmitting(false)
    }
  }

  // Delete user
  const handleDelete = async () => {
    if (!deletingUser) return

    try {
      setSubmitting(true)
      await apiFetch(`/users/${deletingUser.id}`, {
        method: 'DELETE'
      })
      showToast({
        type: 'success',
        title: 'Kullanıcı silindi',
        description: `${deletingUser.username} başarıyla silindi.`
      })
      setDeleteDialogOpen(false)
      setDeletingUser(null)
      fetchUsers()
    } catch (error) {
      console.error('Failed to delete user:', error)
      showToast({
        type: 'error',
        title: 'Kullanıcı silinemedi',
        description: error?.message || 'Kullanıcı silinirken hata oluştu.'
      })
    } finally {
      setSubmitting(false)
    }
  }

  // Reset MFA
  const handleResetMFA = async () => {
    if (!mfaUser) return

    try {
      setSubmitting(true)
      const response = await apiFetch(`/users/${mfaUser.id}/reset-mfa`, {
        method: 'POST'
      })
      const data = await response.json()
      setMfaSecret(data.mfa_secret)
      showToast({
        type: 'success',
        title: 'MFA sıfırlandı',
        description: `${mfaUser.username} için yeni MFA kodu oluşturuldu.`
      })
      fetchUsers()
    } catch (error) {
      console.error('Failed to reset MFA:', error)
      showToast({
        type: 'error',
        title: 'MFA sıfırlanamadı',
        description: error?.message || 'MFA sıfırlanırken hata oluştu.'
      })
    } finally {
      setSubmitting(false)
    }
  }

  const getRoleIcon = (role) => {
    switch (role) {
      case 'admin':
        return <ShieldAlert className="w-4 h-4 text-red-500" />
      case 'operator':
        return <ShieldCheck className="w-4 h-4 text-blue-500" />
      default:
        return <Shield className="w-4 h-4 text-gray-500" />
    }
  }

  const getRoleBadge = (role) => {
    const colors = {
      admin: 'bg-red-100 text-red-800 border-red-200',
      operator: 'bg-blue-100 text-blue-800 border-blue-200',
      viewer: 'bg-gray-100 text-gray-800 border-gray-200'
    }
    return (
      <Badge variant="outline" className={colors[role]}>
        {getRoleIcon(role)}
        <span className="ml-1">{role}</span>
      </Badge>
    )
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center p-8">
        <Loader2 className="w-8 h-8 animate-spin text-gray-500" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="text-2xl">Kullanıcı Yönetimi</CardTitle>
              <CardDescription>API kullanıcılarını yönetin (sadece admin)</CardDescription>
            </div>
            <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <UserPlus className="w-4 h-4 mr-2" />
                  Yeni Kullanıcı
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Yeni Kullanıcı Ekle</DialogTitle>
                  <DialogDescription>Yeni bir API kullanıcısı oluşturun.</DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Kullanıcı Adı</Label>
                    <Input
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                      placeholder="kullanici_adi"
                    />
                  </div>
                  <div>
                    <Label>Şifre</Label>
                    <Input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      placeholder="En az 6 karakter"
                    />
                  </div>
                  <div>
                    <Label>Rol</Label>
                    <Select value={formData.role} onValueChange={(value) => setFormData({ ...formData, role: value })}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="viewer">Viewer (Sadece Okuma)</SelectItem>
                        <SelectItem value="operator">Operator (Bot/Chat Yönetimi)</SelectItem>
                        <SelectItem value="admin">Admin (Tam Yetki)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={formData.mfa_enabled}
                      onCheckedChange={(checked) => setFormData({ ...formData, mfa_enabled: checked })}
                    />
                    <Label>MFA Etkinleştir</Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                    İptal
                  </Button>
                  <Button onClick={handleCreate} disabled={submitting}>
                    {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                    Oluştur
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Kullanıcı Adı</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>MFA</TableHead>
                <TableHead>Oluşturulma</TableHead>
                <TableHead className="text-right">İşlemler</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell>{getRoleBadge(user.role)}</TableCell>
                  <TableCell>
                    {user.is_active ? (
                      <Badge className="bg-green-100 text-green-800 border-green-200">Aktif</Badge>
                    ) : (
                      <Badge variant="outline" className="bg-gray-100 text-gray-800">
                        Pasif
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{user.mfa_enabled ? 'Aktif' : '-'}</TableCell>
                  <TableCell>{new Date(user.created_at).toLocaleDateString('tr-TR')}</TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditingUser(user)
                        setEditFormData({
                          role: user.role,
                          is_active: user.is_active,
                          reset_password: ''
                        })
                        setEditDialogOpen(true)
                      }}
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setMfaUser(user)
                        setMfaSecret(null)
                        setMfaDialogOpen(true)
                      }}
                    >
                      <Key className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        setDeletingUser(user)
                        setDeleteDialogOpen(true)
                      }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Kullanıcı Düzenle</DialogTitle>
            <DialogDescription>
              {editingUser?.username} kullanıcısını düzenleyin.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Rol</Label>
              <Select value={editFormData.role} onValueChange={(value) => setEditFormData({ ...editFormData, role: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">Viewer</SelectItem>
                  <SelectItem value="operator">Operator</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                checked={editFormData.is_active}
                onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
              />
              <Label>Aktif</Label>
            </div>
            <div>
              <Label>Yeni Şifre (opsiyonel)</Label>
              <Input
                type="password"
                value={editFormData.reset_password}
                onChange={(e) => setEditFormData({ ...editFormData, reset_password: e.target.value })}
                placeholder="Boş bırakın değişiklik istemiyorsanız"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              İptal
            </Button>
            <Button onClick={handleUpdate} disabled={submitting}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Güncelle
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Kullanıcıyı Sil</DialogTitle>
            <DialogDescription>
              {deletingUser?.username} kullanıcısını silmek istediğinize emin misiniz?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              İptal
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={submitting}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Sil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MFA Reset Dialog */}
      <Dialog open={mfaDialogOpen} onOpenChange={setMfaDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>MFA Sıfırla</DialogTitle>
            <DialogDescription>
              {mfaUser?.username} için yeni MFA kodu oluştur.
            </DialogDescription>
          </DialogHeader>
          {mfaSecret ? (
            <div className="space-y-4">
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded">
                <p className="text-sm font-medium text-yellow-800 mb-2">Yeni MFA Secret:</p>
                <code className="block p-2 bg-white border border-yellow-300 rounded font-mono text-sm break-all">
                  {mfaSecret}
                </code>
              </div>
              <p className="text-sm text-gray-600">
                Bu kodu kullanıcıya iletin. Google Authenticator veya benzer bir uygulamada kullanabilirler.
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-600">
              Mevcut MFA kodu sıfırlanacak ve yeni bir kod oluşturulacak.
            </p>
          )}
          <DialogFooter>
            {mfaSecret ? (
              <Button onClick={() => setMfaDialogOpen(false)}>Kapat</Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => setMfaDialogOpen(false)}>
                  İptal
                </Button>
                <Button onClick={handleResetMFA} disabled={submitting}>
                  {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Sıfırla
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default UserManagement
