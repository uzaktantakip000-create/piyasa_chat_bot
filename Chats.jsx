import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  MessageSquare,
  Plus,
  Edit,
  Trash2,
  Power,
  PowerOff,
  Users
} from 'lucide-react'

import { apiFetch } from './apiClient'

function Chats() {
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingChat, setEditingChat] = useState(null)
  const [formData, setFormData] = useState({
    chat_id: '',
    title: '',
    is_enabled: true,
    topics: []
  })

  // Fetch chats
  const fetchChats = async () => {
    try {
      const response = await apiFetch('/chats')
      const data = await response.json()
      setChats(data)
    } catch (error) {
      console.error('Failed to fetch chats:', error)
    } finally {
      setLoading(false)
    }
  }

  // Create or update chat
  const saveChat = async () => {
    try {
      const url = editingChat
        ? `/chats/${editingChat.id}`
        : '/chats'
      
      const method = editingChat ? 'PATCH' : 'POST'
      
      // Convert topics string to array
      const chatData = {
        ...formData,
        topics: typeof formData.topics === 'string' 
          ? formData.topics.split(',').map(t => t.trim()).filter(t => t)
          : formData.topics
      }
      
      await apiFetch(url, {
        method,
        body: JSON.stringify(chatData),
      })

      await fetchChats()
      setDialogOpen(false)
      resetForm()
    } catch (error) {
      console.error('Failed to save chat:', error)
      alert('Sohbet kaydedilirken hata oluştu: ' + error.message)
    }
  }

  // Delete chat
  const deleteChat = async (chatId) => {
    if (!confirm('Bu sohbeti silmek istediğinizden emin misiniz?')) {
      return
    }

    try {
      await apiFetch(`/chats/${chatId}`, {
        method: 'DELETE',
      })

      await fetchChats()
    } catch (error) {
      console.error('Failed to delete chat:', error)
      alert('Sohbet silinirken hata oluştu: ' + error.message)
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
                          onClick={() => deleteChat(chat.id)}
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
    </div>
  )
}

export default Chats

