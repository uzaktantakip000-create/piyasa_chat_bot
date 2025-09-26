import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  Bot,
  Plus,
  Edit,
  Trash2,
  Power,
  PowerOff
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:8000'

function Bots() {
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingBot, setEditingBot] = useState(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [botToDelete, setBotToDelete] = useState(null)
  const { toast } = useToast()
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
  const getErrorMessage = async (response) => {
    try {
      const data = await response.json()
      if (typeof data === 'string') {
        return data
      }
      return data?.detail || data?.message || 'Beklenmeyen bir hata oluştu.'
    } catch (error) {
      return response.statusText || 'Beklenmeyen bir hata oluştu.'
    }
  }

  const fetchBots = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/bots`)
      if (response.ok) {
        const data = await response.json()
        setBots(data)
      } else {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }
    } catch (error) {
      console.error('Failed to fetch bots:', error)
      toast({
        title: 'Botlar yüklenemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  // Create or update bot
  const saveBot = async () => {
    try {
      const url = editingBot 
        ? `${API_BASE_URL}/bots/${editingBot.id}`
        : `${API_BASE_URL}/bots`
      
      const method = editingBot ? 'PATCH' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      })

      if (!response.ok) {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }

      await fetchBots()
      setDialogOpen(false)
      resetForm()
      toast({
        title: editingBot ? 'Bot güncellendi' : 'Bot oluşturuldu',
        description: `${formData.name || editingBot?.name || 'Bot'} başarıyla kaydedildi.`
      })
    } catch (error) {
      console.error('Failed to save bot:', error)
      toast({
        title: 'Bot kaydedilemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
      })
    }
  }

  // Delete bot
  const deleteBot = async () => {
    if (!botToDelete) return
    try {
      const response = await fetch(`${API_BASE_URL}/bots/${botToDelete.id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }

      await fetchBots()
      toast({
        title: 'Bot silindi',
        description: `${botToDelete.name || 'Bot'} başarıyla silindi.`
      })
    } catch (error) {
      console.error('Failed to delete bot:', error)
      toast({
        title: 'Bot silinemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
      })
    } finally {
      setDeleteDialogOpen(false)
      setBotToDelete(null)
    }
  }

  // Toggle bot status
  const toggleBot = async (bot) => {
    try {
      const response = await fetch(`${API_BASE_URL}/bots/${bot.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          is_enabled: !bot.is_enabled
        }),
      })

      if (!response.ok) {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }

      await fetchBots()
      toast({
        title: 'Bot durumu güncellendi',
        description: `${bot.name} ${bot.is_enabled ? 'pasif' : 'aktif'} hale getirildi.`
      })
    } catch (error) {
      console.error('Failed to toggle bot:', error)
      toast({
        title: 'Bot durumu değiştirilemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
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
  }

  const openEditDialog = (bot) => {
    setEditingBot(bot)
    setFormData({
      name: bot.name,
      token: bot.token,
      username: bot.username,
      is_enabled: bot.is_enabled,
      persona_hint: bot.persona_hint || '',
      active_hours: bot.active_hours || [],
      speed_profile: bot.speed_profile || {}
    })
    setDialogOpen(true)
  }

  const openCreateDialog = () => {
    resetForm()
    setDialogOpen(true)
  }

  const openDeleteDialog = (bot) => {
    setBotToDelete(bot)
    setDeleteDialogOpen(true)
  }

  useEffect(() => {
    fetchBots()
  }, [])

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
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                  İsim
                </Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="col-span-3"
                  placeholder="Bot ismi"
                />
              </div>
              
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="username" className="text-right">
                  Kullanıcı Adı
                </Label>
                <Input
                  id="username"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  className="col-span-3"
                  placeholder="@botusername"
                />
              </div>
              
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="token" className="text-right">
                  Token
                </Label>
                <Input
                  id="token"
                  type="password"
                  value={formData.token}
                  onChange={(e) => setFormData({...formData, token: e.target.value})}
                  className="col-span-3"
                  placeholder="Bot token"
                />
              </div>
              
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="persona" className="text-right">
                  Kişilik
                </Label>
                <Textarea
                  id="persona"
                  value={formData.persona_hint}
                  onChange={(e) => setFormData({...formData, persona_hint: e.target.value})}
                  className="col-span-3"
                  placeholder="Bot kişiliği hakkında ipucu"
                  rows={3}
                />
              </div>
              
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="enabled" className="text-right">
                  Aktif
                </Label>
                <Switch
                  id="enabled"
                  checked={formData.is_enabled}
                  onCheckedChange={(checked) => setFormData({...formData, is_enabled: checked})}
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button type="submit" onClick={saveBot}>
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
          {bots.length === 0 ? (
            <div className="text-center py-8">
              <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">Henüz bot eklenmemiş</p>
              <p className="text-sm text-muted-foreground">
                Simülasyonu başlatmak için en az bir bot ekleyin
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>İsim</TableHead>
                  <TableHead>Kullanıcı Adı</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead>Kişilik</TableHead>
                  <TableHead>İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bots.map((bot) => (
                  <TableRow key={bot.id}>
                    <TableCell className="font-medium">{bot.name}</TableCell>
                    <TableCell>@{bot.username}</TableCell>
                    <TableCell>
                      <Badge variant={bot.is_enabled ? "default" : "secondary"}>
                        {bot.is_enabled ? "Aktif" : "Pasif"}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-xs truncate">
                      {bot.persona_hint || "Varsayılan"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleBot(bot)}
                        >
                          {bot.is_enabled ? (
                            <PowerOff className="h-4 w-4" />
                          ) : (
                            <Power className="h-4 w-4" />
                          )}
                        </Button>
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(bot)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openDeleteDialog(bot)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Botu silmek istediğinize emin misiniz?</AlertDialogTitle>
            <AlertDialogDescription>
              {botToDelete
                ? `${botToDelete.name} adlı bot kalıcı olarak silinecektir.`
                : 'Seçilen bot silinecektir.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Vazgeç</AlertDialogCancel>
            <AlertDialogAction onClick={deleteBot}>Sil</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default Bots

