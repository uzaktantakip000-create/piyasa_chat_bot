import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  FileText,
  RefreshCw,
  Search,
  Filter,
  Download,
  Eye
} from 'lucide-react'

import { apiFetch } from './apiClient'
import { toast } from 'sonner'
import { SkeletonTable } from './components/ui/skeleton'
import { EmptyState, EmptySearchResults } from './components/EmptyState'
import { SearchInput } from './components/ui/search-input'

function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [limitFilter, setLimitFilter] = useState('100')

  // Fetch logs
  const fetchLogs = async () => {
    try {
      const response = await apiFetch(`/logs?limit=${limitFilter}`)
      const data = await response.json()
      setLogs(data)
    } catch (error) {
      console.error('Failed to fetch logs:', error)
      alert('Loglar getirilirken hata oluştu: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  // Filter logs based on search term
  const filteredLogs = logs.filter(log => 
    log.text.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.bot_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.chat_title.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Format date
  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleString('tr-TR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // Export logs
  const exportLogs = () => {
    const csvContent = [
      ['Tarih', 'Bot', 'Sohbet', 'Mesaj', 'Reply To'].join(','),
      ...filteredLogs.map(log => [
        formatDate(log.created_at),
        log.bot_name,
        log.chat_title,
        `"${log.text.replace(/"/g, '""')}"`,
        log.reply_to || ''
      ].join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `telegram_logs_${new Date().toISOString().split('T')[0]}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  useEffect(() => {
    fetchLogs()
  }, [limitFilter])

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchLogs, 10000) // Refresh every 10 seconds
      return () => clearInterval(interval)
    }
  }, [autoRefresh, limitFilter])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Loglar</h2>
          <p className="text-muted-foreground">
            Gönderilen mesajların geçmişini görüntüleyin
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={exportLogs}
            disabled={filteredLogs.length === 0}
          >
            <Download className="h-4 w-4 mr-2" />
            CSV İndir
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? 'Otomatik' : 'Manuel'}
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={fetchLogs}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filtreler
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <SearchInput
                placeholder="Mesaj, bot adı veya sohbet adında ara..."
                value={searchTerm}
                onChange={setSearchTerm}
                onClear={() => setSearchTerm('')}
              />
            </div>
            
            <Select value={limitFilter} onValueChange={setLimitFilter}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="50">Son 50</SelectItem>
                <SelectItem value="100">Son 100</SelectItem>
                <SelectItem value="200">Son 200</SelectItem>
                <SelectItem value="500">Son 500</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Mesaj Geçmişi ({filteredLogs.length})
          </CardTitle>
          <CardDescription>
            En son gönderilen mesajlar (en yeni üstte)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <SkeletonTable rows={10} columns={5} />
          ) : filteredLogs.length === 0 ? (
            searchTerm ? (
              <EmptySearchResults
                searchTerm={searchTerm}
                onClear={() => setSearchTerm('')}
              />
            ) : (
              <EmptyState
                icon={FileText}
                title="Henüz log kaydı yok"
                description="Botlar mesaj göndermeye başladığında loglar burada görünecek."
              />
            )
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tarih</TableHead>
                    <TableHead>Bot</TableHead>
                    <TableHead>Sohbet</TableHead>
                    <TableHead>Mesaj</TableHead>
                    <TableHead>Reply</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="font-mono text-sm">
                        {formatDate(log.created_at)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {log.bot_name}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-32 truncate">
                        {log.chat_title}
                      </TableCell>
                      <TableCell className="max-w-md">
                        <div className="truncate" title={log.text}>
                          {log.text}
                        </div>
                      </TableCell>
                      <TableCell>
                        {log.reply_to && (
                          <Badge variant="secondary" className="text-xs">
                            Reply
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Toplam Mesaj</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filteredLogs.length}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Reply Oranı</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {filteredLogs.length > 0 
                ? Math.round((filteredLogs.filter(log => log.reply_to).length / filteredLogs.length) * 100)
                : 0}%
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Aktif Bot Sayısı</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {new Set(filteredLogs.map(log => log.bot_name)).size}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Logs

