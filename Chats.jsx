import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  MessageSquare,
  Plus,
  Edit,
  Trash2,
  Users
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:8000'

function Chats() {
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingChat, setEditingChat] = useState(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [chatToDelete, setChatToDelete] = useState(null)
  const { toast } = useToast()
  const [formData, setFormData] = useState({
    chat_id: '',
    title: '',
    is_enabled: true,
    topics: []
  })

  // Fetch chats
  const fetchChats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/chats`)
      if (response.ok) {
        const data = await response.json()
        setChats(data)
      } else {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }
    } catch (error) {
      console.error('Failed to fetch chats:', error)
      toast({
        title: 'Sohbetler yüklenemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

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

  // Create or update chat
  const saveChat = async () => {
    try {
      const url = editingChat
        ? `${API_BASE_URL}/chats/${editingChat.id}`
        : `${API_BASE_URL}/chats`
      
      const method = editingChat ? 'PATCH' : 'POST'
      
      // Convert topics string to array
      const chatData = {
        ...formData,
        topics: typeof formData.topics === 'string' 
          ? formData.topics.split(',').map(t => t.trim()).filter(t => t)
          : formData.topics
      }
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(chatData),
      })

      if (!response.ok) {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }

      await fetchChats()
      setDialogOpen(false)
      resetForm()
      toast({
        title: editingChat ? 'Sohbet güncellendi' : 'Sohbet oluşturuldu',
        description: `${chatData.title || editingChat?.title || 'Sohbet'} başarıyla kaydedildi.`
      })
    } catch (error) {
      console.error('Failed to save chat:', error)
      toast({
        title: 'Sohbet kaydedilemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
      })
    }
  }

  // Delete chat
  const deleteChat = async () => {
    if (!chatToDelete) return
    try {
      const response = await fetch(`${API_BASE_URL}/chats/${chatToDelete.id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        const message = await getErrorMessage(response)
        throw new Error(message)
      }

      await fetchChats()
      toast({
        title: 'Sohbet silindi',
        description: `${chatToDelete.title || 'Sohbet'} başarıyla silindi.`
      })
    } catch (error) {
      console.error('Failed to delete chat:', error)
      toast({
        title: 'Sohbet silinemedi',
        description: error?.message || 'Beklenmeyen bir hata oluştu.',
        variant: 'destructive'
      })
    } finally {
      setDeleteDialogOpen(false)
      setChatToDelete(null)
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
  }

  const openEditDialog = (chat) => {
    setEditingChat(chat)
    setFormData({
      chat_id: chat.chat_id,
      title: chat.title,
      is_enabled: chat.is_enabled,
      topics: Array.isArray(chat.topics) ? chat.topics.join(', ') : ''
    })
    setDialogOpen(true)
  }

  const openCreateDialog = () => {
    resetForm()
    setDialogOpen(true)
  }

  const openDeleteDialog = (chat) => {
    setChatToDelete(chat)
    setDeleteDialogOpen(true)
  }

  useEffect(() => {
    fetchChats()
  }, [])

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
                <Input
                  id="chat_id"
                  value={formData.chat_id}
                  onChange={(e) => setFormData({...formData, chat_id: e.target.value})}
                  className="col-span-3"
                  placeholder="-1001234567890"
                />
              </div>
              
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="title" className="text-right">
                  Başlık
                </Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => setFormData({...formData, title: e.target.value})}
                  className="col-span-3"
                  placeholder="Sohbet grubu adı"
                />
              </div>
              
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="topics" className="text-right">
                  Konular
                </Label>
                <Input
                  id="topics"
                  value={formData.topics}
                  onChange={(e) => setFormData({...formData, topics: e.target.value})}
                  className="col-span-3"
                  placeholder="BIST, USD/TRY, Kripto (virgülle ayırın)"
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
              <Button type="submit" onClick={saveChat}>
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
          {chats.length === 0 ? (
            <div className="text-center py-8">
              <MessageSquare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">Henüz sohbet eklenmemiş</p>
              <p className="text-sm text-muted-foreground">
                Botların mesaj göndereceği sohbet gruplarını ekleyin
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Başlık</TableHead>
                  <TableHead>Chat ID</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead>Konular</TableHead>
                  <TableHead>İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {chats.map((chat) => (
                  <TableRow key={chat.id}>
                    <TableCell className="font-medium">{chat.title}</TableCell>
                    <TableCell className="font-mono text-sm">{chat.chat_id}</TableCell>
                    <TableCell>
                      <Badge variant={chat.is_enabled ? "default" : "secondary"}>
                        {chat.is_enabled ? "Aktif" : "Pasif"}
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
                          onClick={() => openEditDialog(chat)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openDeleteDialog(chat)}
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
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sohbeti silmek istediğinize emin misiniz?</AlertDialogTitle>
            <AlertDialogDescription>
              {chatToDelete
                ? `${chatToDelete.title} adlı sohbet kalıcı olarak silinecektir.`
                : 'Seçilen sohbet silinecektir.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Vazgeç</AlertDialogCancel>
            <AlertDialogAction onClick={deleteChat}>Sil</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default Chats

