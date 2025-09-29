import { useState, useEffect, useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
  Bot,
  Plus,
  Edit,
  Trash2,
  Power,
  PowerOff,
  Settings,
  Filter,
  CheckSquare,
  Square,
  Loader2
} from 'lucide-react'

import { apiFetch } from './apiClient'
import { useToast } from './components/ToastProvider'

function Bots() {
  const { showToast } = useToast()
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [editingBot, setEditingBot] = useState(null)
  const [confirmingBot, setConfirmingBot] = useState(null)
  const [bulkProcessing, setBulkProcessing] = useState(false)
  const [selectedBotIds, setSelectedBotIds] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [formErrors, setFormErrors] = useState({})
  const [formData, setFormData] = useState({
    name: '',
    token: '',
    username: '',
    is_enabled: true,
    persona_hint: '',
    active_hours: [],
    speed_profile: {}
  })

  // Fetch bots
  const fetchBots = async () => {
    try {
      setLoading(true)
      const response = await apiFetch('/bots')
      const data = await response.json()
      setBots(data)
    } catch (error) {
      console.error('Failed to fetch bots:', error)
      showToast({
        type: 'error',
        title: 'Botlar yüklenemedi',
        description: error?.message || 'Bot listesi alınırken beklenmeyen bir hata oluştu.'
      })
    } finally {
      setLoading(false)
    }
  }

  // Create or update bot
  const saveBot = async () => {
    setFormErrors({})
    const errors = {}
    const trimmedName = formData.name.trim()
    const trimmedUsername = formData.username.trim()
    const normalizedUsername = trimmedUsername.replace(/^@/, '')
    const trimmedToken = formData.token.trim()

    if (!trimmedName || trimmedName.length < 3) {
      errors.name = 'Bot adı en az 3 karakter olmalı.'
    }

    if (!normalizedUsername) {
      errors.username = 'Kullanıcı adı zorunludur.'
    } else if (!/^[A-Za-z0-9_]{5,}$/.test(normalizedUsername)) {
      errors.username = 'Kullanıcı adı en az 5 karakter olmalı ve yalnızca harf/rakam/içermelidir.'
    }

    if (!editingBot || trimmedToken) {
      const tokenPattern = /^\d{6,}:[A-Za-z0-9_-]{30,}$/
      if (!trimmedToken) {
        errors.token = 'Bot token değeri gerekli.'
      } else if (!tokenPattern.test(trimmedToken)) {
        errors.token = 'Token formatı geçersiz. Örn: 123456789:ABCdefGhijkLMNOPQRSTUvwxYZ012345678.'
      }
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    try {
      const url = editingBot ? `/bots/${editingBot.id}` : '/bots'
      const method = editingBot ? 'PATCH' : 'POST'
      const payload = {
        ...formData,
        name: trimmedName,
        token: trimmedToken,
        username: normalizedUsername
      }

      if (editingBot && !payload.token) {
        delete payload.token
      }

      const response = await apiFetch(url, {
        method,
        body: JSON.stringify(payload),
      })

      await response.json()
      await fetchBots()
      setDialogOpen(false)
      resetForm()
      showToast({
        type: 'success',
        title: editingBot ? 'Bot güncellendi' : 'Bot eklendi',
        description: `${payload.name} botu başarıyla ${editingBot ? 'güncellendi' : 'oluşturuldu'}.`
      })
    } catch (error) {
      console.error('Failed to save bot:', error)
      showToast({
        type: 'error',
        title: 'Bot kaydedilemedi',
        description: error?.message || 'Bot kaydedilirken beklenmeyen bir hata oluştu.'
      })
    }
  }

  // Delete bot
  const deleteBot = async (bot) => {
    try {
      await apiFetch(`/bots/${bot.id}`, {
        method: 'DELETE',
      })
      await fetchBots()
      setSelectedBotIds((prev) => prev.filter((id) => id !== bot.id))
      showToast({
        type: 'success',
        title: 'Bot silindi',
        description: `${bot.name} sistemden kaldırıldı.`
      })
    } catch (error) {
      console.error('Failed to delete bot:', error)
      showToast({
        type: 'error',
        title: 'Bot silinemedi',
        description: error?.message || 'Bot silinirken beklenmeyen bir hata oluştu.'
      })
    }
  }

  // Toggle bot status
  const toggleBot = async (bot) => {
    try {
      await apiFetch(`/bots/${bot.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          is_enabled: !bot.is_enabled
        }),
      })
      await fetchBots()
      showToast({
        type: 'success',
        title: bot.is_enabled ? 'Bot pasifleştirildi' : 'Bot aktifleştirildi',
        description: `${bot.name} ${bot.is_enabled ? 'geçici olarak durduruldu' : 'yeniden aktif edildi'}.`
      })
    } catch (error) {
      console.error('Failed to toggle bot:', error)
      showToast({
        type: 'error',
        title: 'Durum değiştirilemedi',
        description: error?.message || 'Bot durumu değiştirilirken beklenmeyen bir hata oluştu.'
      })
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      token: '',
      username: '',
      is_enabled: true,
      persona_hint: '',
      active_hours: [],
      speed_profile: {}
    })
    setEditingBot(null)
    setFormErrors({})
  }

  const openEditDialog = (bot) => {
    setEditingBot(bot)
    setFormData({
      name: bot.name,
      token: '',
      username: bot.username,
      is_enabled: bot.is_enabled,
      persona_hint: bot.persona_hint || '',
      active_hours: bot.active_hours || [],
      speed_profile: bot.speed_profile || {}
    })
    setFormErrors({})
    setDialogOpen(true)
  }

  const openCreateDialog = () => {
    resetForm()
    setFormErrors({})
    setDialogOpen(true)
  }

  const requestDeleteBot = (bot) => {
    setConfirmingBot(bot)
    setConfirmDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!confirmingBot) {
      return
    }
    await deleteBot(confirmingBot)
    setConfirmDialogOpen(false)
    setConfirmingBot(null)
  }

  const handleCancelDelete = () => {
    setConfirmDialogOpen(false)
    setConfirmingBot(null)
  }

  useEffect(() => {
    fetchBots()
  }, [])

  const filteredBots = useMemo(() => {
    const search = searchTerm.trim().toLowerCase()
    return bots.filter((bot) => {
      const matchesSearch =
        !search ||
        bot.name.toLowerCase().includes(search) ||
        (bot.username || '').toLowerCase().includes(search) ||
        (bot.persona_hint || '').toLowerCase().includes(search)
      const matchesStatus =
        statusFilter === 'all' || (statusFilter === 'active' ? bot.is_enabled : !bot.is_enabled)
      return matchesSearch && matchesStatus
    })
  }, [bots, searchTerm, statusFilter])

  const toggleSelectAllVisible = () => {
    if (filteredBots.length === 0) {
      return
    }
    const visibleIds = filteredBots.map((bot) => bot.id)
    const allSelected = visibleIds.every((id) => selectedBotIds.includes(id))
    if (allSelected) {
      setSelectedBotIds((prev) => prev.filter((id) => !visibleIds.includes(id)))
    } else {
      setSelectedBotIds((prev) => Array.from(new Set([...prev, ...visibleIds])))
    }
  }

  const toggleSelectBot = (botId) => {
    setSelectedBotIds((prev) =>
      prev.includes(botId) ? prev.filter((id) => id !== botId) : [...prev, botId]
    )
  }

  const handleBulkStatus = async (nextStatus) => {
    if (selectedBotIds.length === 0) {
      return
    }
    setBulkProcessing(true)
    const targets = bots.filter((bot) => selectedBotIds.includes(bot.id) && bot.is_enabled !== nextStatus)
    if (targets.length === 0) {
      showToast({
        type: 'info',
        title: 'Güncellenecek bot yok',
        description: 'Seçili botlar zaten hedef duruma sahip.'
      })
      setBulkProcessing(false)
      return
    }
    try {
      await Promise.all(
        targets.map((bot) =>
          apiFetch(`/bots/${bot.id}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_enabled: nextStatus })
          })
        )
      )
      await fetchBots()
      setSelectedBotIds([])
      showToast({
        type: 'success',
        title: nextStatus ? 'Botlar aktifleştirildi' : 'Botlar pasifleştirildi',
        description: `${targets.length} bot ${nextStatus ? 'aktif' : 'pasif'} duruma getirildi.`
      })
    } catch (error) {
      console.error('Bulk status change failed:', error)
      showToast({
        type: 'error',
        title: 'Toplu işlem başarısız',
        description: error?.message || 'Botların durumu güncellenirken beklenmeyen bir hata oluştu.'
      })
    } finally {
      setBulkProcessing(false)
    }
  }

  const clearSelection = () => {
    setSelectedBotIds([])
  }

  const hasSelection = selectedBotIds.length > 0
  const allVisibleSelected = filteredBots.length > 0 && filteredBots.every((bot) => selectedBotIds.includes(bot.id))
  const noBots = bots.length === 0

  if (loading) {
    return <div className="flex items-center justify-center h-64">Yükleniyor...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Botlar</h2>
          <p className="text-muted-foreground">
            Telegram botlarını yönetin ve yapılandırın
          </p>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreateDialog}>
              <Plus className="h-4 w-4 mr-2" />
              Yeni Bot
            </Button>
          </DialogTrigger>
          
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>
                {editingBot ? 'Bot Düzenle' : 'Yeni Bot Ekle'}
              </DialogTitle>
              <DialogDescription>
                Bot bilgilerini girin. Token'ı BotFather'dan alabilirsiniz.
              </DialogDescription>
            </DialogHeader>
            
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-start gap-4">
                <Label htmlFor="name" className="text-right">
                  İsim
                </Label>
                <div className="col-span-3 space-y-1">
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className={formErrors.name ? 'border-destructive focus-visible:ring-destructive' : ''}
                    placeholder="Bot ismi"
                  />
                  <p className="text-xs text-muted-foreground">Panelde gösterilen takma ad.</p>
                  {formErrors.name && <p className="text-xs text-destructive">{formErrors.name}</p>}
                </div>
              </div>

              <div className="grid grid-cols-4 items-start gap-4">
                <Label htmlFor="username" className="text-right">
                  Kullanıcı Adı
                </Label>
                <div className="col-span-3 space-y-1">
                  <Input
                    id="username"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className={formErrors.username ? 'border-destructive focus-visible:ring-destructive' : ''}
                    placeholder="@botusername"
                  />
                  <p className="text-xs text-muted-foreground">BotFather üzerinden aldığınız kullanıcı adını @ işareti olmadan girin.</p>
                  {formErrors.username && <p className="text-xs text-destructive">{formErrors.username}</p>}
                </div>
              </div>

              <div className="grid grid-cols-4 items-start gap-4">
                <Label htmlFor="token" className="text-right">
                  Token
                </Label>
                <div className="col-span-3 space-y-1">
                  <Input
                    id="token"
                    type="password"
                    value={formData.token}
                    onChange={(e) => setFormData({ ...formData, token: e.target.value })}
                    className={formErrors.token ? 'border-destructive focus-visible:ring-destructive' : ''}
                    placeholder={editingBot ? 'Yeni token (opsiyonel)' : 'Bot token'}
                  />
                  <p className="text-xs text-muted-foreground">Format örneği: 123456789:ABCdefGhijkLMNOPQRSTUvwxYZ012345678</p>
                  {editingBot && (
                    <p className="text-xs text-muted-foreground">Kayıtlı token: {editingBot.token_masked || 'belirtilmemiş'}</p>
                  )}
                  {formErrors.token && <p className="text-xs text-destructive">{formErrors.token}</p>}
                </div>
              </div>

              <div className="grid grid-cols-4 items-start gap-4">
                <Label htmlFor="persona" className="text-right">
                  Kişilik
                </Label>
                <div className="col-span-3 space-y-1">
                  <Textarea
                    id="persona"
                    value={formData.persona_hint}
                    onChange={(e) => setFormData({ ...formData, persona_hint: e.target.value })}
                    placeholder="Bot kişiliği hakkında ipucu"
                    rows={3}
                  />
                  <p className="text-xs text-muted-foreground">Mesaj tonu ve hitap şeklini anlatan kısa bir not ekleyin.</p>
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
                  <span className="text-xs text-muted-foreground">Aktif olmayan botlar mesaj göndermeyecektir.</span>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" onClick={saveBot}>
                {editingBot ? 'Güncelle' : 'Ekle'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Bot Listesi ({bots.length})
          </CardTitle>
          <CardDescription>
            Tüm botların durumu ve ayarları
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
                  placeholder="İsim, kullanıcı adı veya kişilik ara"
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
              <span>{filteredBots.length} bot listeleniyor</span>
              {hasSelection && (
                <span className="font-medium text-primary">{selectedBotIds.length} seçili</span>
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

          {noBots ? (
            <div className="py-8 text-center">
              <Bot className="mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-muted-foreground">Henüz bot eklenmemiş</p>
              <p className="text-sm text-muted-foreground">Simülasyonu başlatmak için en az bir bot ekleyin</p>
            </div>
          ) : filteredBots.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground">
              Filtre kriterlerine uygun bot bulunamadı.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      aria-label="Tüm görünür botları seç"
                      checked={allVisibleSelected}
                      onChange={toggleSelectAllVisible}
                      className="h-4 w-4 rounded border-muted-foreground"
                    />
                  </TableHead>
                  <TableHead>İsim</TableHead>
                  <TableHead>Kullanıcı Adı</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead>Kişilik</TableHead>
                  <TableHead>İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredBots.map((bot) => {
                  const isSelected = selectedBotIds.includes(bot.id)
                  return (
                    <TableRow key={bot.id} className={isSelected ? 'bg-muted/30' : ''}>
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectBot(bot.id)}
                          className="h-4 w-4 rounded border-muted-foreground"
                          aria-label={`${bot.name} seçimi`}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{bot.name}</TableCell>
                      <TableCell>{bot.username ? `@${bot.username}` : '-'}</TableCell>
                      <TableCell>
                        <Badge variant={bot.is_enabled ? 'default' : 'secondary'}>
                          {bot.is_enabled ? 'Aktif' : 'Pasif'}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-xs truncate">
                        {bot.persona_hint || 'Varsayılan'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleBot(bot)}
                            aria-label={bot.is_enabled ? 'Pasifleştir' : 'Aktifleştir'}
                          >
                            {bot.is_enabled ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(bot)}
                            aria-label="Düzenle"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => requestDeleteBot(bot)}
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
            <DialogTitle>Botu silmek istediğinize emin misiniz?</DialogTitle>
            <DialogDescription>
              {confirmingBot?.name} kalıcı olarak kaldırılacak ve token bilgisi silinecek.
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
    </div>
  )
}

export default Bots

