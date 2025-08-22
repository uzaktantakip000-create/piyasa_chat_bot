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

function Dashboard({ metrics }) {
  const botUtilization = metrics.total_bots > 0 ? (metrics.active_bots / metrics.total_bots) * 100 : 0
  const rateLimit429Rate = metrics.messages_last_hour > 0 ? (metrics.telegram_429_count / metrics.messages_last_hour) * 100 : 0

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Total Bots */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Toplam Bot</CardTitle>
            <Bot className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_bots}</div>
            <p className="text-xs text-muted-foreground">
              {metrics.active_bots} aktif
            </p>
            <Progress value={botUtilization} className="mt-2" />
          </CardContent>
        </Card>

        {/* Messages per Hour */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Saatlik Mesaj</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.messages_last_hour}</div>
            <p className="text-xs text-muted-foreground">
              {metrics.messages_per_minute.toFixed(1)} msg/dk
            </p>
          </CardContent>
        </Card>

        {/* Active Chats */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktif Sohbet</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_chats}</div>
            <p className="text-xs text-muted-foreground">
              Toplam sohbet sayısı
            </p>
          </CardContent>
        </Card>

        {/* Scale Factor */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ölçek Faktörü</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.scale_factor}x</div>
            <p className="text-xs text-muted-foreground">
              Hız çarpanı
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Sistem Durumu
            </CardTitle>
            <CardDescription>
              Simülasyon ve sistem metrikleri
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Simülasyon Durumu</span>
              <Badge variant={metrics.simulation_active ? "default" : "secondary"}>
                {metrics.simulation_active ? "Çalışıyor" : "Durduruldu"}
              </Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Bot Kullanımı</span>
              <span className="text-sm text-muted-foreground">
                {botUtilization.toFixed(1)}%
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Mesaj Hızı</span>
              <span className="text-sm text-muted-foreground">
                {metrics.messages_per_minute.toFixed(1)} msg/dk
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Ölçek Faktörü</span>
              <span className="text-sm text-muted-foreground">
                {metrics.scale_factor}x
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Rate Limiting & Errors */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Hız Sınırları & Hatalar
            </CardTitle>
            <CardDescription>
              Telegram API sınırları ve hata oranları
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Rate Limit Hits</span>
              <Badge variant={metrics.rate_limit_hits > 0 ? "destructive" : "secondary"}>
                {metrics.rate_limit_hits}
              </Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Telegram 429 Errors</span>
              <Badge variant={metrics.telegram_429_count > 0 ? "destructive" : "secondary"}>
                {metrics.telegram_429_count}
              </Badge>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">429 Hata Oranı</span>
              <span className="text-sm text-muted-foreground">
                {rateLimit429Rate.toFixed(2)}%
              </span>
            </div>
            
            {(metrics.rate_limit_hits > 0 || metrics.telegram_429_count > 0) && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                <p className="text-sm text-destructive">
                  ⚠️ Yüksek hata oranı tespit edildi. Hız ayarlarını kontrol edin.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Performance Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Performans Önerileri
          </CardTitle>
          <CardDescription>
            Sistem performansını optimize etmek için öneriler
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {metrics.telegram_429_count > 10 && (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  📊 Çok fazla 429 hatası alınıyor. Mesaj hızını düşürmeyi düşünün.
                </p>
              </div>
            )}
            
            {metrics.messages_per_minute < 1 && metrics.simulation_active && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  🚀 Mesaj hızı düşük. Ölçek faktörünü artırabilirsiniz.
                </p>
              </div>
            )}
            
            {botUtilization < 50 && metrics.total_bots > 0 && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm text-green-800">
                  ✅ Bot kullanımı optimal seviyede. Daha fazla bot ekleyebilirsiniz.
                </p>
              </div>
            )}
            
            {metrics.total_bots === 0 && (
              <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <p className="text-sm text-gray-800">
                  🤖 Henüz bot eklenmemiş. Simülasyonu başlatmak için bot ekleyin.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Dashboard

