import { useState, useEffect, useMemo } from 'react'
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
  MessageSquare,
  Plus,
  Edit,
  Trash2,
  Power,
  PowerOff,
  Users,
  Filter,
  CheckSquare,
  Square,
  Loader2,
  ArrowUpDown
} from 'lucide-react'

import { apiFetch } from './apiClient'
import { useToast } from './components/ToastProvider'

const CHAT_FILTER_STORAGE_KEY = 'piyasa.chats.filters'

function Chats() {
  const { showToast } = useToast()
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [editingChat, setEditingChat] = useState(null)
  const [confirmingChat, setConfirmingChat] = useState(null)
  const [bulkProcessing, setBulkProcessing] = useState(false)
  const [selectedChatIds, setSelectedChatIds] = useState([])
  const [sortConfig, setSortConfig] = useState({ field: 'title', direction: 'asc' })
  const [searchTerm, setSearchTerm] = useState(() => {
    if (typeof window === 'undefined') {
      return ''
    }
    try {
      const stored = localStorage.getItem(CHAT_FILTER_STORAGE_KEY)
      if (!stored) {
        return ''
      }
      const parsed = JSON.parse(stored)
      return typeof parsed.searchTerm === 'string' ? parsed.searchTerm : ''
    } catch (error) {
      console.warn('Sohbet filtreleri okunamadı:', error)
      return ''
    }
  })
  const [statusFilter, setStatusFilter] = useState(() => {
    if (typeof window === 'undefined') {
      return 'all'
    }
    try {
      const stored = localStorage.getItem(CHAT_FILTER_STORAGE_KEY)
      if (!stored) {
        return 'all'
      }
      const parsed = JSON.parse(stored)
      return typeof parsed.statusFilter === 'string' ? parsed.statusFilter : 'all'
    } catch (error) {
      console.warn('Sohbet filtreleri okunamadı:', error)
      return 'all'
    }
  })
  const [formErrors, setFormErrors] = useState({})
  const [formData, setFormData] = useState({
    chat_id: '',
    title: '',
    is_enabled: true,
    topics: []
  })

  // Fetch chats
  const fetchChats = async () => {
    try {
      setLoading(true)
      const response = await apiFetch('/chats')
      const data = await response.json()
      setChats(data)
    } catch (error) {
      console.error('Failed to fetch chats:', error)
      showToast({
        type: 'error',
        title: 'Sohbetler yüklenemedi',
        description: error?.message || 'Sohbet listesi alınırken beklenmeyen bir hata oluştu.'
      })
    } finally {
      setLoading(false)
    }
  }

  // Create or update chat
  const saveChat = async () => {
    setFormErrors({})
    try {
      const url = editingChat
        ? `/chats/${editingChat.id}`
        : '/chats'

      const method = editingChat ? 'PATCH' : 'POST'

      // Convert topics string to array
      const chatData = {
        ...formData,
        chat_id: formData.chat_id.trim(),
        title: formData.title.trim(),
        topics: typeof formData.topics === 'string'
          ? formData.topics.split(',').map(t => t.trim()).filter(t => t)
          : formData.topics
      }

      const errors = {}
      if (!chatData.chat_id) {
        errors.chat_id = 'Chat ID zorunludur.'
      } else if (!/^(-?\d{6,})$/.test(chatData.chat_id)) {
        errors.chat_id = 'Chat ID yalnızca rakamlardan oluşmalı ve en az 6 haneli olmalıdır.'
      }

      if (!chatData.title) {
        errors.title = 'Sohbet başlığı gereklidir.'
      } else if (chatData.title.length < 3) {
        errors.title = 'Başlık en az 3 karakter olmalıdır.'
      }

      if (Object.keys(errors).length > 0) {
        setFormErrors(errors)
        return
      }

      await apiFetch(url, {
        method,
        body: JSON.stringify(chatData),
      })

      await fetchChats()
      setDialogOpen(false)
      resetForm()
      showToast({
        type: 'success',
        title: editingChat ? 'Sohbet güncellendi' : 'Sohbet eklendi',
        description: `${chatData.title} sohbeti başarıyla ${editingChat ? 'güncellendi' : 'oluşturuldu'}.`
      })
    } catch (error) {
      console.error('Failed to save chat:', error)
      showToast({
        type: 'error',
        title: 'Sohbet kaydedilemedi',
        description: error?.message || 'Sohbet kaydedilirken beklenmeyen bir hata oluştu.'
      })
    }
  }

  // Delete chat
  const deleteChat = async (chat) => {
    try {
      await apiFetch(`/chats/${chat.id}`, {
        method: 'DELETE',
      })

      await fetchChats()
      setSelectedChatIds((prev) => prev.filter((id) => id !== chat.id))
      showToast({
        type: 'success',
        title: 'Sohbet silindi',
        description: `${chat.title} sistemden kaldırıldı.`
      })
    } catch (error) {
      console.error('Failed to delete chat:', error)
      showToast({
        type: 'error',
        title: 'Sohbet silinemedi',
        description: error?.message || 'Sohbet silinirken beklenmeyen bir hata oluştu.'
      })
    }
  }

  const toggleChatStatus = async (chat) => {
    try {
      await apiFetch(`/chats/${chat.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_enabled: !chat.is_enabled })
      })
      await fetchChats()
      showToast({
        type: 'success',
        title: chat.is_enabled ? 'Sohbet pasifleştirildi' : 'Sohbet aktifleştirildi',
        description: `${chat.title} ${chat.is_enabled ? 'geçici olarak durduruldu' : 'yeniden aktif edildi'}.`
      })
    } catch (error) {
      console.error('Failed to toggle chat status:', error)
      showToast({
        type: 'error',
        title: 'Durum değiştirilemedi',
        description: error?.message || 'Sohbet durumu değiştirilirken beklenmeyen bir hata oluştu.'
      })
    }
  }

  const resetForm = () => {
    setFormData({
      chat_id: '',
      title: '',
      is_enabled: true,
      topics: []
    })
    setEditingChat(null)
    setFormErrors({})
  }

  const openEditDialog = (chat) => {
    setEditingChat(chat)
    setFormData({
      chat_id: chat.chat_id,
      title: chat.title,
      is_enabled: chat.is_enabled,
      topics: Array.isArray(chat.topics) ? chat.topics.join(', ') : ''
    })
    setFormErrors({})
    setDialogOpen(true)
  }

  const openCreateDialog = () => {
    resetForm()
    setFormErrors({})
    setDialogOpen(true)
  }

  const requestDeleteChat = (chat) => {
    setConfirmingChat(chat)
    setConfirmDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!confirmingChat) {
      return
    }
    await deleteChat(confirmingChat)
    setConfirmDialogOpen(false)
    setConfirmingChat(null)
  }

  const handleCancelDelete = () => {
    setConfirmDialogOpen(false)
    setConfirmingChat(null)
  }

  useEffect(() => {
    fetchChats()
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      const payload = JSON.stringify({ searchTerm, statusFilter })
      localStorage.setItem(CHAT_FILTER_STORAGE_KEY, payload)
    } catch (error) {
      console.warn('Sohbet filtreleri kaydedilemedi:', error)
    }
  }, [searchTerm, statusFilter])

  const filteredChats = useMemo(() => {
    const search = searchTerm.trim().toLowerCase()
    const filtered = chats.filter((chat) => {
      const topicsText = Array.isArray(chat.topics) ? chat.topics.join(', ') : chat.topics || ''
      const matchesSearch =
        !search ||
        chat.title.toLowerCase().includes(search) ||
        (chat.chat_id || '').toLowerCase().includes(search) ||
        topicsText.toLowerCase().includes(search)
      const matchesStatus =
        statusFilter === 'all' || (statusFilter === 'active' ? chat.is_enabled : !chat.is_enabled)
      return matchesSearch && matchesStatus
    })

    const sorted = [...filtered].sort((a, b) => {
      const direction = sortConfig.direction === 'asc' ? 1 : -1
      switch (sortConfig.field) {
        case 'chat_id': {
          const aValue = a.chat_id || ''
          const bValue = b.chat_id || ''
          return aValue.localeCompare(bValue, 'tr') * direction
        }
        case 'status': {
          const aValue = a.is_enabled ? 1 : 0
          const bValue = b.is_enabled ? 1 : 0
          if (aValue === bValue) {
            return a.title.localeCompare(b.title, 'tr') * direction
          }
          return (aValue - bValue) * direction
        }
        case 'topics': {
          const aValue = Array.isArray(a.topics) ? a.topics.join(', ') : a.topics || ''
          const bValue = Array.isArray(b.topics) ? b.topics.join(', ') : b.topics || ''
          return aValue.localeCompare(bValue, 'tr') * direction
        }
        case 'title':
        default:
          return a.title.localeCompare(b.title, 'tr') * direction
      }
    })

    return sorted
  }, [chats, searchTerm, statusFilter, sortConfig])

  const toggleSort = (field) => {
    setSortConfig((prev) => {
      if (prev.field === field) {
        return { field, direction: prev.direction === 'asc' ? 'desc' : 'asc' }
      }
      return { field, direction: 'asc' }
    })
  }

  const renderSortIndicator = (field) => {
    const isActive = sortConfig.field === field
    const directionClass = isActive && sortConfig.direction === 'asc' ? 'rotate-180' : ''
    return (
      <ArrowUpDown
        className={`ml-1 h-3 w-3 transition-transform ${directionClass} ${
          isActive ? 'text-primary' : 'text-muted-foreground'
        }`}
        aria-hidden="true"
      />
    )
  }

  const toggleSelectAllVisible = () => {
    if (filteredChats.length === 0) {
      return
    }
    const visibleIds = filteredChats.map((chat) => chat.id)
    const allSelected = visibleIds.every((id) => selectedChatIds.includes(id))
    if (allSelected) {
      setSelectedChatIds((prev) => prev.filter((id) => !visibleIds.includes(id)))
    } else {
      setSelectedChatIds((prev) => Array.from(new Set([...prev, ...visibleIds])))
    }
  }

  const toggleSelectChat = (chatId) => {
    setSelectedChatIds((prev) =>
      prev.includes(chatId) ? prev.filter((id) => id !== chatId) : [...prev, chatId]
    )
  }

  const handleBulkStatus = async (nextStatus) => {
    if (selectedChatIds.length === 0) {
      return
    }
    setBulkProcessing(true)
    const targets = chats.filter((chat) => selectedChatIds.includes(chat.id) && chat.is_enabled !== nextStatus)
    if (targets.length === 0) {
      showToast({
        type: 'info',
        title: 'Güncellenecek sohbet yok',
        description: 'Seçili sohbetler zaten hedef duruma sahip.'
      })
      setBulkProcessing(false)
      return
    }
    try {
      await Promise.all(
        targets.map((chat) =>
          apiFetch(`/chats/${chat.id}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_enabled: nextStatus })
          })
        )
      )
      await fetchChats()
      setSelectedChatIds([])
      showToast({
        type: 'success',
        title: nextStatus ? 'Sohbetler aktifleştirildi' : 'Sohbetler pasifleştirildi',
        description: `${targets.length} sohbet ${nextStatus ? 'aktif' : 'pasif'} duruma getirildi.`
      })
    } catch (error) {
      console.error('Bulk chat status change failed:', error)
      showToast({
        type: 'error',
        title: 'Toplu işlem başarısız',
        description: error?.message || 'Sohbetlerin durumu güncellenirken beklenmeyen bir hata oluştu.'
      })
    } finally {
      setBulkProcessing(false)
    }
  }

  const clearSelection = () => setSelectedChatIds([])

  const hasSelection = selectedChatIds.length > 0
  const allVisibleSelected = filteredChats.length > 0 && filteredChats.every((chat) => selectedChatIds.includes(chat.id))
  const noChats = chats.length === 0

  if (loading) {
    return <div className="flex items-center justify-center h-64">Yükleniyor...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Sohbetler</h2>
          <p className="text-muted-foreground">
            Telegram sohbet gruplarını yönetin
          </p>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreateDialog}>
              <Plus className="h-4 w-4 mr-2" />
              Yeni Sohbet
            </Button>
          </DialogTrigger>
          
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>
                {editingChat ? 'Sohbet Düzenle' : 'Yeni Sohbet Ekle'}
              </DialogTitle>
              <DialogDescription>
                Telegram sohbet grubu bilgilerini girin.
              </DialogDescription>
            </DialogHeader>
            
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="chat_id" className="text-right">
                  Chat ID
                </Label>
                <div className="col-span-3 space-y-1">
                  <Input
                    id="chat_id"
                    value={formData.chat_id}
                    onChange={(e) => setFormData({ ...formData, chat_id: e.target.value })}
                    className={formErrors.chat_id ? 'border-destructive focus-visible:ring-destructive' : ''}
                    placeholder="-1001234567890"
                  />
                  <p className="text-xs text-muted-foreground">@userinfobot çıktısındaki değeri aynen kullanın.</p>
                  {formErrors.chat_id && <p className="text-xs text-destructive">{formErrors.chat_id}</p>}
                </div>
              </div>

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="title" className="text-right">
                  Başlık
                </Label>
                <div className="col-span-3 space-y-1">
                  <Input
                    id="title"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    className={formErrors.title ? 'border-destructive focus-visible:ring-destructive' : ''}
                    placeholder="Sohbet grubu adı"
                  />
                  <p className="text-xs text-muted-foreground">Panelde görünecek olan anlaşılır bir başlık seçin.</p>
                  {formErrors.title && <p className="text-xs text-destructive">{formErrors.title}</p>}
                </div>
              </div>

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="topics" className="text-right">
                  Konular
                </Label>
                <div className="col-span-3 space-y-1">
                  <Input
                    id="topics"
                    value={formData.topics}
                    onChange={(e) => setFormData({ ...formData, topics: e.target.value })}
                    placeholder="BIST, USD/TRY, Kripto (virgülle ayırın)"
                  />
                  <p className="text-xs text-muted-foreground">Virgül ile ayrılmış etiketler; raporlama ve arama için kullanılır.</p>
                </div>
              </div>

              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="enabled" className="text-right">
                  Aktif
                </Label>
                <div className="col-span-3 flex items-center gap-3">
                  <Switch
                    id="enabled"
                    checked={formData.is_enabled}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_enabled: checked })}
                  />
                  <span className="text-xs text-muted-foreground">Pasif sohbetlere botlar mesaj göndermez.</span>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" onClick={saveChat}>
                {editingChat ? 'Güncelle' : 'Ekle'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Sohbet Listesi ({chats.length})
          </CardTitle>
          <CardDescription>
            Tüm sohbet gruplarının durumu ve ayarları
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="flex w-full items-center gap-2 sm:w-64">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Input
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Başlık, chat ID veya konu ara"
                  className="flex-1"
                />
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-48">
                  <SelectValue placeholder="Durum filtresi" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tümü</SelectItem>
                  <SelectItem value="active">Aktif</SelectItem>
                  <SelectItem value="inactive">Pasif</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>{filteredChats.length} sohbet listeleniyor</span>
              {hasSelection && (
                <span className="font-medium text-primary">{selectedChatIds.length} seçili</span>
              )}
            </div>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleBulkStatus(true)}
              disabled={!hasSelection || bulkProcessing}
              className="flex items-center gap-2"
            >
              {bulkProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckSquare className="h-4 w-4" />}
              Seçilileri Aktifleştir
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleBulkStatus(false)}
              disabled={!hasSelection || bulkProcessing}
              className="flex items-center gap-2"
            >
              {bulkProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              Seçilileri Pasifleştir
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearSelection}
              disabled={!hasSelection || bulkProcessing}
            >
              Seçimleri Temizle
            </Button>
          </div>

          {noChats ? (
            <div className="py-8 text-center">
              <MessageSquare className="mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-muted-foreground">Henüz sohbet eklenmemiş</p>
              <p className="text-sm text-muted-foreground">Botların mesaj göndereceği sohbet gruplarını ekleyin</p>
            </div>
          ) : filteredChats.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground">
              Filtre kriterlerine uygun sohbet bulunamadı.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      aria-label="Tüm görünür sohbetleri seç"
                      checked={allVisibleSelected}
                      onChange={toggleSelectAllVisible}
                      className="h-4 w-4 rounded border-muted-foreground"
                    />
                  </TableHead>
                  <TableHead className="whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => toggleSort('title')}
                      className="flex items-center gap-1 font-medium text-left text-foreground hover:text-primary focus:outline-none"
                    >
                      Başlık
                      {renderSortIndicator('title')}
                    </button>
                  </TableHead>
                  <TableHead className="whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => toggleSort('chat_id')}
                      className="flex items-center gap-1 font-medium text-left text-foreground hover:text-primary focus:outline-none"
                    >
                      Chat ID
                      {renderSortIndicator('chat_id')}
                    </button>
                  </TableHead>
                  <TableHead className="whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => toggleSort('status')}
                      className="flex items-center gap-1 font-medium text-left text-foreground hover:text-primary focus:outline-none"
                    >
                      Durum
                      {renderSortIndicator('status')}
                    </button>
                  </TableHead>
                  <TableHead className="whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => toggleSort('topics')}
                      className="flex items-center gap-1 font-medium text-left text-foreground hover:text-primary focus:outline-none"
                    >
                      Konular
                      {renderSortIndicator('topics')}
                    </button>
                  </TableHead>
                  <TableHead>İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredChats.map((chat) => {
                  const isSelected = selectedChatIds.includes(chat.id)
                  return (
                    <TableRow key={chat.id} className={isSelected ? 'bg-muted/30' : ''}>
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectChat(chat.id)}
                          className="h-4 w-4 rounded border-muted-foreground"
                          aria-label={`${chat.title} seçimi`}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{chat.title}</TableCell>
                      <TableCell className="font-mono text-sm">{chat.chat_id}</TableCell>
                      <TableCell>
                        <Badge variant={chat.is_enabled ? 'default' : 'secondary'}>
                          {chat.is_enabled ? 'Aktif' : 'Pasif'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {(chat.topics || []).slice(0, 3).map((topic, index) => (
                            <Badge key={index} variant="outline" className="text-xs">
                              {topic}
                            </Badge>
                          ))}
                          {(chat.topics || []).length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{(chat.topics || []).length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleChatStatus(chat)}
                            aria-label={chat.is_enabled ? 'Pasifleştir' : 'Aktifleştir'}
                          >
                            {chat.is_enabled ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(chat)}
                            aria-label="Düzenle"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => requestDeleteChat(chat)}
                            aria-label="Sil"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={confirmDialogOpen} onOpenChange={(open) => (open ? setConfirmDialogOpen(true) : handleCancelDelete())}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Sohbeti silmek istediğinize emin misiniz?</DialogTitle>
            <DialogDescription>
              {confirmingChat?.title} sohbeti ve ilişkilendirilmiş tüm ayarlar kaldırılacak.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2 sm:justify-end">
            <Button variant="ghost" onClick={handleCancelDelete}>
              Vazgeç
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              Sil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Chat Setup Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Sohbet Kurulum Rehberi
          </CardTitle>
          <CardDescription>
            Telegram sohbet gruplarını nasıl kuracağınız hakkında bilgi
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium">1. Telegram Grubu Oluşturun</h4>
            <p className="text-sm text-muted-foreground">
              Telegram'da yeni bir grup oluşturun veya mevcut bir grubu kullanın.
            </p>
          </div>
          
          <div className="space-y-2">
            <h4 className="font-medium">2. Botları Gruba Ekleyin</h4>
            <p className="text-sm text-muted-foreground">
              Tüm botları gruba admin olarak ekleyin. Botların mesaj gönderme yetkisi olmalı.
            </p>
          </div>
          
          <div className="space-y-2">
            <h4 className="font-medium">3. Chat ID'yi Alın</h4>
            <p className="text-sm text-muted-foreground">
              @userinfobot'u gruba ekleyip /start yazarak Chat ID'yi öğrenin. 
              ID genellikle -100 ile başlar (örn: -1001234567890).
            </p>
          </div>
          
          <div className="space-y-2">
            <h4 className="font-medium">4. Sohbeti Sisteme Ekleyin</h4>
            <p className="text-sm text-muted-foreground">
              Yukarıdaki "Yeni Sohbet" butonunu kullanarak Chat ID ve diğer bilgileri girin.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Chats

