import { useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { X, BellRing, Activity, Filter, Trash2 } from 'lucide-react'

const severityMeta = {
  critical: {
    label: 'Kritik',
    badgeClass: 'bg-rose-100 text-rose-700 border border-rose-200',
    icon: '🚨'
  },
  error: {
    label: 'Hata',
    badgeClass: 'bg-rose-100 text-rose-700 border border-rose-200',
    icon: '⚠️'
  },
  warning: {
    label: 'Uyarı',
    badgeClass: 'bg-amber-100 text-amber-700 border border-amber-200',
    icon: '⚠️'
  },
  success: {
    label: 'Başarılı',
    badgeClass: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
    icon: '✅'
  },
  info: {
    label: 'Bilgi',
    badgeClass: 'bg-sky-100 text-sky-700 border border-sky-200',
    icon: 'ℹ️'
  }
}

const formatRelativeTime = (isoString) => {
  if (!isoString) {
    return '—'
  }
  const date = new Date(isoString)
  const diffMs = Date.now() - date.getTime()
  if (!Number.isFinite(diffMs)) {
    return '—'
  }
  const seconds = Math.round(diffMs / 1000)
  if (seconds < 45) return 'az önce'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} dk önce`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} sa önce`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days} gün önce`
  const weeks = Math.round(days / 7)
  if (weeks < 5) return `${weeks} hf önce`
  const months = Math.round(days / 30)
  if (months < 12) return `${months} ay önce`
  const years = Math.round(days / 365)
  return `${years} yıl önce`
}

export default function ActivityCenter({
  open,
  onClose,
  events = [],
  onClearEvents,
  toastHistory = [],
  onClearToastHistory
}) {
  const [activeTab, setActiveTab] = useState('events')
  const [severityFilter, setSeverityFilter] = useState('all')

  const filteredEvents = useMemo(() => {
    if (severityFilter === 'all') {
      return events
    }
    return events.filter((event) => (event.severity ?? 'info') === severityFilter)
  }, [events, severityFilter])

  const severityCounts = useMemo(() => {
    return events.reduce(
      (acc, item) => {
        const key = item.severity ?? 'info'
        acc[key] = (acc[key] || 0) + 1
        acc.all += 1
        return acc
      },
      { all: 0 }
    )
  }, [events])

  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-sm">
      <aside
        id="activity-center"
        className="flex h-full w-full max-w-3xl flex-col border-l border-border bg-background shadow-xl"
        aria-label="Etkinlik Merkezi"
      >
        <header className="border-b border-border bg-muted/50 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
                <BellRing className="h-5 w-5 text-primary" /> Etkinlik Merkezi
              </h2>
              <p className="text-sm text-muted-foreground">
                Gerçek zamanlı bildirimleri, toast geçmişini ve sistem olaylarını tek ekranda takip edin.
              </p>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Etkinlik merkezini kapat">
              <X className="h-5 w-5" />
            </Button>
          </div>
        </header>

        <div className="flex-1 overflow-hidden p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex h-full flex-col">
            <TabsList className="w-fit">
              <TabsTrigger value="events">Olay Akışı</TabsTrigger>
              <TabsTrigger value="toasts">Toast Geçmişi</TabsTrigger>
            </TabsList>
            <div className="mt-4 flex-1 overflow-hidden">
              <TabsContent value="events" className="h-full">
                <Card className="flex h-full flex-col">
                  <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-primary" /> Anlık olaylar
                      </CardTitle>
                      <CardDescription>
                        Manuel ve otomatik işlemler, test sonuçları ve bağlantı durumuna ilişkin kayıtlar.
                      </CardDescription>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="inline-flex items-center gap-2 rounded-md border border-border/60 bg-background px-3 py-2 text-xs">
                        <Filter className="h-3.5 w-3.5 text-muted-foreground" />
                        <select
                          className="bg-transparent text-xs focus:outline-none"
                          value={severityFilter}
                          onChange={(event) => setSeverityFilter(event.target.value)}
                        >
                          <option value="all">Tümü ({severityCounts.all ?? 0})</option>
                          <option value="critical">Kritik ({severityCounts.critical ?? 0})</option>
                          <option value="error">Hata ({severityCounts.error ?? 0})</option>
                          <option value="warning">Uyarı ({severityCounts.warning ?? 0})</option>
                          <option value="success">Başarılı ({severityCounts.success ?? 0})</option>
                          <option value="info">Bilgi ({severityCounts.info ?? 0})</option>
                        </select>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={onClearEvents}
                        disabled={!events.length}
                        className="flex items-center gap-2"
                      >
                        <Trash2 className="h-4 w-4" /> Temizle
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="flex-1 overflow-hidden">
                    <div className="h-full space-y-3 overflow-y-auto pr-4">
                      {filteredEvents.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          Gösterilecek kayıt bulunamadı. Yeni olaylar burada listelenecek.
                        </p>
                      ) : (
                          filteredEvents.map((event) => {
                            const meta = severityMeta[event.severity] ?? severityMeta.info
                            return (
                              <div
                                key={event.id}
                                className="rounded-lg border border-border/60 bg-card/60 p-4 shadow-sm transition hover:border-primary/50"
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div className="flex items-start gap-3">
                                    <span className="text-xl" aria-hidden="true">
                                      {meta.icon}
                                    </span>
                                    <div>
                                      <p className="text-sm font-semibold text-foreground">{event.title}</p>
                                      {event.description ? (
                                        <p className="mt-1 text-sm text-muted-foreground">{event.description}</p>
                                      ) : null}
                                      {event.meta?.context ? (
                                        <p className="mt-2 text-xs text-muted-foreground">{event.meta.context}</p>
                                      ) : null}
                                    </div>
                                  </div>
                                  <Badge variant="outline" className={meta.badgeClass}>
                                    {meta.label}
                                  </Badge>
                                </div>
                                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                  <span>{formatRelativeTime(event.timestamp)}</span>
                                  {event.source ? <span>Kaynak: {event.source}</span> : null}
                                  {event.meta?.manual ? <span>Manuel işlem</span> : null}
                                </div>
                              </div>
                            )
                          })
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="toasts" className="h-full">
                <Card className="flex h-full flex-col">
                  <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-base">
                        <BellRing className="h-4 w-4 text-primary" /> Toast bildirimleri
                      </CardTitle>
                      <CardDescription>Panelde gösterilen tüm toast bildirimlerinin geçmişi.</CardDescription>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={onClearToastHistory}
                      disabled={!toastHistory.length}
                      className="flex items-center gap-2"
                    >
                      <Trash2 className="h-4 w-4" /> Geçmişi temizle
                    </Button>
                  </CardHeader>
                  <CardContent className="flex-1 overflow-hidden">
                    <div className="h-full space-y-3 overflow-y-auto pr-4">
                      {toastHistory.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          Henüz toast bildirimi kaydı yok.
                        </p>
                      ) : (
                          toastHistory.map((toast) => {
                            const meta = severityMeta[toast.type] ?? severityMeta.info
                            return (
                              <div
                                key={toast.id}
                                className="rounded-lg border border-border/60 bg-card/60 p-4 shadow-sm"
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-semibold">{toast.title || 'Bildirim'}</p>
                                    {toast.description ? (
                                      <p className="mt-1 text-sm text-muted-foreground">{toast.description}</p>
                                    ) : null}
                                  </div>
                                  <Badge variant="outline" className={meta.badgeClass}>
                                    {meta.label}
                                  </Badge>
                                </div>
                                <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                                  <span>{formatRelativeTime(toast.timestamp)}</span>
                                  {toast.source ? <span>Kaynak: {toast.source}</span> : null}
                                </div>
                              </div>
                            )
                          })
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </aside>
    </div>
  )
}

