import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Activity,
  Bot,
  MessageSquare,
  Users,
  TrendingUp,
  AlertTriangle,
  Clock,
  Zap
} from 'lucide-react'

const placeholder = (width = 'w-20') => (
  <div className={`h-6 rounded bg-muted/60 ${width} animate-pulse`} aria-hidden="true" />
)

function Dashboard({ metrics, lastUpdatedAt, isLoading = false, isRefreshing = false }) {
  const safeMetrics = metrics || {}
  const botUtilization = safeMetrics.total_bots > 0 ? (safeMetrics.active_bots / safeMetrics.total_bots) * 100 : 0
  const rateLimit429Rate = safeMetrics.messages_last_hour > 0
    ? (safeMetrics.telegram_429_count / safeMetrics.messages_last_hour) * 100
    : 0
  const isStale = lastUpdatedAt ? Date.now() - lastUpdatedAt.getTime() > 10000 : false
  const formattedLastUpdated = lastUpdatedAt
    ? lastUpdatedAt.toLocaleTimeString('tr-TR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    : 'Veri alınamadı'

  const messageRateStatus = botUtilization >= 85 || rateLimit429Rate >= 5 ? 'destructive' : botUtilization >= 70 ? 'warning' : 'info'
  const utilisationAccent =
    messageRateStatus === 'destructive'
      ? 'text-destructive'
      : messageRateStatus === 'warning'
        ? 'text-amber-600'
        : 'text-emerald-600'
  const rateLimitAccent = rateLimit429Rate >= 10 ? 'text-destructive' : rateLimit429Rate >= 5 ? 'text-amber-600' : 'text-muted-foreground'

  const renderValue = (value, width) => {
    if (isLoading) {
      return placeholder(width)
    }
    return value
  }

  const renderSubtle = (value, width = 'w-24') => {
    if (isLoading) {
      return <div className={`h-4 rounded bg-muted/40 ${width} animate-pulse`} aria-hidden="true" />
    }
    return value
  }

  return (
    <div className="space-y-6">
      <Card className={`${isStale ? 'border-destructive/50 bg-destructive/10' : ''}`}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className={`h-4 w-4 ${isRefreshing ? 'text-primary' : ''}`} />
            Veri Durumu
          </CardTitle>
          <Badge variant={isRefreshing ? 'default' : isStale ? 'destructive' : 'secondary'}>
            {isRefreshing ? 'Güncelleniyor…' : formattedLastUpdated}
          </Badge>
        </CardHeader>
        <CardContent>
          <p className={`text-sm ${isStale ? 'text-destructive' : 'text-muted-foreground'}`}>
            {isStale
              ? '⚠️ Gösterilen veriler 10 saniyeden daha eski olabilir.'
              : isRefreshing
                ? 'Son metrikler yükleniyor, değerler bir süre önceki hali gösterebilir.'
                : 'Veriler güncel görünüyor.'}
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Toplam Bot</CardTitle>
            <Bot className={`h-4 w-4 ${isLoading ? 'text-muted-foreground' : utilisationAccent}`} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {renderValue(safeMetrics.total_bots, 'w-16')}
            </div>
            <p className="text-xs text-muted-foreground">
              {renderSubtle(`${safeMetrics.active_bots} aktif`, 'w-20')}
            </p>
            <div className="mt-2">
              <Progress value={botUtilization} />
            </div>
          </CardContent>
        </Card>

        <Card className={messageRateStatus === 'destructive' ? 'border-destructive/40 bg-destructive/5' : messageRateStatus === 'warning' ? 'border-amber-200/70 bg-amber-50/60' : ''}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Saatlik Mesaj</CardTitle>
            <MessageSquare className={`h-4 w-4 ${messageRateStatus === 'destructive' ? 'text-destructive' : messageRateStatus === 'warning' ? 'text-amber-600' : 'text-muted-foreground'}`} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {renderValue(safeMetrics.messages_last_hour, 'w-20')}
            </div>
            <p className={`text-xs ${messageRateStatus === 'destructive' ? 'text-destructive' : messageRateStatus === 'warning' ? 'text-amber-700' : 'text-muted-foreground'}`}>
              {renderSubtle(`${safeMetrics.messages_per_minute?.toFixed?.(1) ?? '0.0'} msg/dk`, 'w-24')}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktif Sohbet</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {renderValue(safeMetrics.total_chats, 'w-16')}
            </div>
            <p className="text-xs text-muted-foreground">
              {renderSubtle('Toplam sohbet sayısı', 'w-28')}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ölçek Faktörü</CardTitle>
            <Zap className={`h-4 w-4 ${safeMetrics.scale_factor > 1.5 ? 'text-primary' : 'text-muted-foreground'}`} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {renderValue(`${safeMetrics.scale_factor}x`, 'w-16')}
            </div>
            <p className="text-xs text-muted-foreground">
              {renderSubtle('Hız çarpanı', 'w-20')}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className={`h-5 w-5 ${safeMetrics.simulation_active ? 'text-emerald-600' : 'text-muted-foreground'}`} />
              Sistem Durumu
            </CardTitle>
            <CardDescription>
              Simülasyon ve sistem metrikleri
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Simülasyon Durumu</span>
              <Badge variant={safeMetrics.simulation_active ? 'default' : 'secondary'}>
                {safeMetrics.simulation_active ? 'Çalışıyor' : 'Durduruldu'}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Bot Kullanımı</span>
              <span className={`text-sm ${utilisationAccent}`}>
                {renderSubtle(`${botUtilization.toFixed(1)}%`, 'w-16')}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Mesaj Hızı</span>
              <span className={`text-sm ${messageRateStatus === 'destructive' ? 'text-destructive' : messageRateStatus === 'warning' ? 'text-amber-700' : 'text-muted-foreground'}`}>
                {renderSubtle(`${safeMetrics.messages_per_minute?.toFixed?.(1) ?? '0.0'} msg/dk`, 'w-20')}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Ölçek Faktörü</span>
              <span className="text-sm text-muted-foreground">
                {renderSubtle(`${safeMetrics.scale_factor}x`, 'w-16')}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className={rateLimit429Rate >= 5 ? 'border-destructive/40 bg-destructive/5' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className={`h-5 w-5 ${rateLimitAccent}`} />
              Hız Sınırları & Hatalar
            </CardTitle>
            <CardDescription>
              Telegram API sınırları ve hata oranları
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Rate Limit Hits</span>
              <Badge variant={safeMetrics.rate_limit_hits > 0 ? 'destructive' : 'secondary'}>
                {renderValue(safeMetrics.rate_limit_hits, 'w-12')}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Telegram 429 Errors</span>
              <Badge variant={safeMetrics.telegram_429_count > 0 ? 'destructive' : 'secondary'}>
                {renderValue(safeMetrics.telegram_429_count, 'w-12')}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">429 Hata Oranı</span>
              <span className={`text-sm ${rateLimitAccent}`}>
                {renderSubtle(`${rateLimit429Rate.toFixed(2)}%`, 'w-16')}
              </span>
            </div>

            {(safeMetrics.rate_limit_hits > 0 || safeMetrics.telegram_429_count > 0) && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                ⚠️ Yüksek hata oranı tespit edildi. Hız ayarlarını kontrol edin.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            Performans Önerileri
          </CardTitle>
          <CardDescription>
            Sistem performansını optimize etmek için öneriler
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {safeMetrics.telegram_429_count > 10 && (
              <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
                📊 Çok fazla 429 hatası alınıyor. Mesaj hızını düşürmeyi düşünün.
              </div>
            )}

            {safeMetrics.messages_per_minute < 1 && safeMetrics.simulation_active && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
                🚀 Mesaj hızı düşük. Ölçek faktörünü artırabilirsiniz.
              </div>
            )}

            {botUtilization < 50 && safeMetrics.total_bots > 0 && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                ✅ Bot kullanımı optimal seviyede. Daha fazla bot ekleyebilirsiniz.
              </div>
            )}

            {safeMetrics.total_bots === 0 && (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-800">
                🤖 Henüz bot eklenmemiş. Simülasyonu başlatmak için bot ekleyin.
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Dashboard

