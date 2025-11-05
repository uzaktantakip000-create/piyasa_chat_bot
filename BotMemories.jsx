import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
  Brain,
  Plus,
  Edit,
  Trash2,
  Loader2,
  Calendar,
  TrendingUp,
  ArrowLeft
} from 'lucide-react'

import { apiFetch } from './apiClient'
import { useToast } from './components/ToastProvider'
import { useTranslation } from './localization'

// Memory type labels in Turkish
const MEMORY_TYPE_LABELS = {
  personal_fact: 'Kişisel Bilgi',
  past_event: 'Geçmiş Olay',
  relationship: 'İlişki',
  preference: 'Tercih',
  routine: 'Rutin'
}

const MEMORY_TYPE_COLORS = {
  personal_fact: 'bg-blue-100 text-blue-800',
  past_event: 'bg-purple-100 text-purple-800',
  relationship: 'bg-green-100 text-green-800',
  preference: 'bg-orange-100 text-orange-800',
  routine: 'bg-gray-100 text-gray-800'
}

const createMemoryDraft = () => ({
  memory_type: 'personal_fact',
  content: '',
  relevance_score: 1.0
})

function BotMemories({ botId: propBotId, botName: propBotName }) {
  const { botId: paramBotId } = useParams()
  const navigate = useNavigate()
  const botId = propBotId || paramBotId
  const [botName, setBotName] = useState(propBotName || '')

  const { t } = useTranslation()
  const tf = (key, fallback) => t(key) || fallback
  const { showToast } = useToast()

  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingMemory, setEditingMemory] = useState(null)
  const [memoryDraft, setMemoryDraft] = useState(createMemoryDraft())
  const [saving, setSaving] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)

  useEffect(() => {
    if (botId) {
      fetchMemories()
      // Fetch bot name if not provided
      if (!propBotName) {
        fetchBotDetails()
      }
    }
  }, [botId])

  const fetchBotDetails = async () => {
    try {
      const bot = await apiFetch(`/bots/${botId}`)
      setBotName(bot.name || '')
    } catch (error) {
      console.error('Failed to fetch bot details:', error)
    }
  }

  const fetchMemories = async () => {
    try {
      setLoading(true)
      const data = await apiFetch(`/bots/${botId}/memories`)
      setMemories(data || [])
    } catch (error) {
      console.error('Failed to fetch memories:', error)
      showToast({
        title: 'Hata',
        description: 'Hafızalar yüklenemedi',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleOpenDialog = (memory = null) => {
    if (memory) {
      setEditingMemory(memory)
      setMemoryDraft({
        memory_type: memory.memory_type,
        content: memory.content,
        relevance_score: memory.relevance_score
      })
    } else {
      setEditingMemory(null)
      setMemoryDraft(createMemoryDraft())
    }
    setDialogOpen(true)
  }

  const handleSaveMemory = async () => {
    if (!memoryDraft.content.trim()) {
      showToast({
        title: 'Hata',
        description: 'Hafıza içeriği boş olamaz',
        variant: 'destructive'
      })
      return
    }

    try {
      setSaving(true)

      const payload = {
        memory_type: memoryDraft.memory_type,
        content: memoryDraft.content.trim(),
        relevance_score: parseFloat(memoryDraft.relevance_score) || 1.0
      }

      if (editingMemory) {
        // Update existing memory
        await apiFetch(`/bots/memories/${editingMemory.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload)
        })
        showToast({
          title: 'Başarılı',
          description: 'Hafıza güncellendi'
        })
      } else {
        // Create new memory
        await apiFetch(`/bots/${botId}/memories`, {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        showToast({
          title: 'Başarılı',
          description: 'Hafıza eklendi'
        })
      }

      setDialogOpen(false)
      setEditingMemory(null)
      setMemoryDraft(createMemoryDraft())
      fetchMemories()
    } catch (error) {
      console.error('Failed to save memory:', error)
      showToast({
        title: 'Hata',
        description: error.message || 'Hafıza kaydedilemedi',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteMemory = async (memoryId) => {
    try {
      await apiFetch(`/bots/memories/${memoryId}`, {
        method: 'DELETE'
      })
      showToast({
        title: 'Başarılı',
        description: 'Hafıza silindi'
      })
      setConfirmDeleteId(null)
      fetchMemories()
    } catch (error) {
      console.error('Failed to delete memory:', error)
      showToast({
        title: 'Hata',
        description: 'Hafıza silinemedi',
        variant: 'destructive'
      })
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return '-'
    const date = new Date(dateString)
    return date.toLocaleDateString('tr-TR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="space-y-4">
      {paramBotId && (
        <Button variant="ghost" onClick={() => navigate('/bots')} className="mb-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Botlara Dön
        </Button>
      )}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-600" />
          <h3 className="text-lg font-semibold">
            {botName ? `${botName} - Hafızalar` : 'Bot Hafızaları'}
          </h3>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => handleOpenDialog()} size="sm">
              <Plus className="mr-2 h-4 w-4" />
              Hafıza Ekle
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>
                {editingMemory ? 'Hafıza Düzenle' : 'Yeni Hafıza Ekle'}
              </DialogTitle>
              <DialogDescription>
                Bot'un kişisel hafızası, geçmiş olayları ve tercihleri
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="memory_type">Hafıza Tipi</Label>
                <Select
                  value={memoryDraft.memory_type}
                  onValueChange={(value) =>
                    setMemoryDraft((prev) => ({ ...prev, memory_type: value }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(MEMORY_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="content">İçerik</Label>
                <Textarea
                  id="content"
                  value={memoryDraft.content}
                  onChange={(e) =>
                    setMemoryDraft((prev) => ({ ...prev, content: e.target.value }))
                  }
                  placeholder="Örn: İstanbul'da yaşıyorum ve yazılımcıyım"
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  Türkçe doğal dil kullanın. Bot bu hafızayı mesajlarında kullanabilir.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="relevance_score">
                  Önem Skoru (0.0 - 1.0)
                </Label>
                <Input
                  id="relevance_score"
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  value={memoryDraft.relevance_score}
                  onChange={(e) =>
                    setMemoryDraft((prev) => ({
                      ...prev,
                      relevance_score: parseFloat(e.target.value)
                    }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Düşük skorlu hafızalar zaman içinde daha az kullanılır
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                İptal
              </Button>
              <Button onClick={handleSaveMemory} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingMemory ? 'Güncelle' : 'Ekle'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : memories.length === 0 ? (
        <Card>
          <CardContent className="py-8">
            <div className="text-center text-muted-foreground">
              <Brain className="mx-auto h-12 w-12 mb-4 opacity-50" />
              <p className="text-sm">Henüz hafıza eklenmemiş</p>
              <p className="text-xs mt-2">
                Botunuza kişisel özellikler, geçmiş olaylar ve tercihler ekleyin
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tip</TableHead>
                  <TableHead>İçerik</TableHead>
                  <TableHead className="text-center">Önem</TableHead>
                  <TableHead className="text-center">Kullanım</TableHead>
                  <TableHead className="text-right">İşlemler</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {memories.map((memory) => (
                  <TableRow key={memory.id}>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={MEMORY_TYPE_COLORS[memory.memory_type]}
                      >
                        {MEMORY_TYPE_LABELS[memory.memory_type]}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-md">
                      <div className="truncate" title={memory.content}>
                        {memory.content}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        <Calendar className="inline h-3 w-3 mr-1" />
                        {formatDate(memory.created_at)}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-1">
                        <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">
                          {(memory.relevance_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">{memory.usage_count}x</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenDialog(memory)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Dialog
                          open={confirmDeleteId === memory.id}
                          onOpenChange={(open) =>
                            setConfirmDeleteId(open ? memory.id : null)
                          }
                        >
                          <DialogTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Hafıza Silinsin mi?</DialogTitle>
                              <DialogDescription>
                                Bu işlem geri alınamaz. Hafıza kalıcı olarak silinecek.
                              </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                              <Button
                                variant="outline"
                                onClick={() => setConfirmDeleteId(null)}
                              >
                                İptal
                              </Button>
                              <Button
                                variant="destructive"
                                onClick={() => handleDeleteMemory(memory.id)}
                              >
                                Sil
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <div className="text-xs text-muted-foreground">
        <p>
          💡 <strong>İpucu:</strong> Yüksek önem skorlu hafızalar daha sık kullanılır.
          Kullanım sayısı, hafızanın kaç kez bot mesajlarında referans edildiğini gösterir.
        </p>
      </div>
    </div>
  )
}

export default BotMemories
