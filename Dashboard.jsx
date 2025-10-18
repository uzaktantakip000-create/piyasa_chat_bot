import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Activity,
  Bot,
  MessageSquare,
  Users,
  TrendingUp,
  AlertTriangle,
  Clock,
  CalendarDays,
  Zap,
  ShieldCheck,
  FlaskConical,
  CheckCircle,
  XCircle,
  Loader2,
  Info,
  ListChecks,
  ChevronDown,
  ChevronUp,
  Copy,
  Target,
  HelpCircle,
  Sparkles,
  Flag,
  BookOpenCheck
} from 'lucide-react'
import { useAdaptiveView, isTableView } from './useAdaptiveView'
import { useTranslation } from './localization'
import ViewModeToggle from './components/ViewModeToggle'

const formatRelativeTime = (date) => {
  if (!date) {
    return null
  }
  const diffMs = Date.now() - date.getTime()
  if (!Number.isFinite(diffMs)) {
    return null
  }
  const diffSeconds = Math.round(diffMs / 1000)
  if (diffSeconds < 45) {
    return 'Az önce'
  }
  const diffMinutes = Math.round(diffSeconds / 60)
  if (diffMinutes < 60) {
    return `${diffMinutes} dk önce`
  }
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `${diffHours} sa önce`
  }
  const diffDays = Math.round(diffHours / 24)
  if (diffDays < 7) {
    return `${diffDays} gün önce`
  }
  const diffWeeks = Math.round(diffDays / 7)
  if (diffWeeks < 4) {
    return `${diffWeeks} hf önce`
  }
  const diffMonths = Math.round(diffDays / 30)
  if (diffMonths < 12) {
    return `${diffMonths} ay önce`
  }
  const diffYears = Math.round(diffDays / 365)
  return `${diffYears} yıl önce`
}

const placeholder = (width = 'w-20') => (
  <div className={`h-6 rounded bg-muted/60 ${width} animate-pulse`} aria-hidden="true" />
)

const TASK_STATUS_META = {
  critical: {
    label: 'Kritik',
    badgeClass: 'border border-rose-200 bg-rose-50 text-rose-700',
    pillClass: 'bg-rose-100 text-rose-700',
    description: 'Acil aksiyon gerekli'
  },
  warning: {
    label: 'Uyarı',
    badgeClass: 'border border-amber-200 bg-amber-50 text-amber-700',
    pillClass: 'bg-amber-100 text-amber-700',
    description: 'Yakından izleyin'
  },
  success: {
    label: 'İyi durumda',
    badgeClass: 'border border-emerald-200 bg-emerald-50 text-emerald-700',
    pillClass: 'bg-emerald-100 text-emerald-700',
    description: 'Hedeflerle uyumlu'
  },
  info: {
    label: 'Bilgi',
    badgeClass: 'border border-sky-200 bg-sky-50 text-sky-700',
    pillClass: 'bg-sky-100 text-sky-700',
    description: 'Takip etmeye devam edin'
  }
}

const ROLE_GUIDES = {
  admin: {
    label: 'Admin',
    description:
      'Altyapı güvenliği, oranlar ve kritik test sonuçlarının paylaşımı senin sorumluluğunda. Aşağıdaki görevlerle günlük nabzı tut.',
    iconAccent: 'text-primary',
    tasks: [
      {
        id: 'system-health',
        title: 'Sistem sağlık raporunu doğrula',
        detail: 'Otomasyon testleri son 24 saat içinde başarısız olduysa aksiyon planı oluştur.',
        computeStatus: (metrics, summary) => {
          if (!summary) {
            return { level: 'info', message: 'Test özeti bekleniyor' }
          }
          if (summary.overall_status === 'critical') {
            return { level: 'critical', message: summary.overall_message || 'Kritik hata var' }
          }
          if (summary.overall_status === 'warning') {
            return { level: 'warning', message: summary.overall_message || 'Bazı adımlar uyarı veriyor' }
          }
          const lastRun = summary.last_run_at ? new Date(summary.last_run_at) : null
          const stale = lastRun ? Date.now() - lastRun.getTime() > 1000 * 60 * 60 * 24 : true
          if (stale) {
            return { level: 'warning', message: '24 saati aşkın süredir test koşusu yok' }
          }
          return { level: 'success', message: 'Testler yeşil görünüyor' }
        },
        nextStep: 'Test sonuçlarını ekiple paylaş'
      },
      {
        id: 'rate-limit',
        title: 'Rate limit ve hata eğrilerini izle',
        detail: 'Telegram 429 oranı %5 üzerine çıkarsa hız ve sıra ayarlarını gözden geçir.',
        computeStatus: (metrics) => {
          const rate = metrics.messages_last_hour > 0
            ? (metrics.telegram_429_count / metrics.messages_last_hour) * 100
            : 0
          if (rate >= 10) {
            return { level: 'critical', message: `%${rate.toFixed(1)} 429 hatası` }
          }
          if (rate >= 5) {
            return { level: 'warning', message: `%${rate.toFixed(1)} 429 hatası` }
          }
          return { level: 'success', message: `%${rate.toFixed(1)} 429 hatası` }
        },
        nextStep: 'Hız profillerini optimize et'
      },
      {
        id: 'access-audit',
        title: 'Erişim denetimini tamamla',
        detail: 'RBAC rollerini ve API anahtarı rotasyon tarihlerini kontrol et.',
        computeStatus: (_, __, sessionMeta) => {
          if (!sessionMeta?.apiKeyLastRotated) {
            return { level: 'warning', message: 'API anahtarı hiç yenilenmemiş' }
          }
          const lastRotated = new Date(sessionMeta.apiKeyLastRotated)
          const stale = Date.now() - lastRotated.getTime() > 1000 * 60 * 60 * 24 * 30
          if (stale) {
            return { level: 'warning', message: '30+ gündür anahtar yenilenmedi' }
          }
          return { level: 'info', message: lastRotated.toLocaleDateString('tr-TR') }
        },
        nextStep: 'Güvenlik raporu oluştur'
      }
    ],
    tour: [
      {
        id: 'health-widget',
        title: 'Sistem Sağlığı Kartı',
        description:
          'Son otomasyon koşusunu, hata dağılımını ve servis sağlık durumunu tek noktadan inceleyerek hızlı aksiyon al.',
        anchor: 'automation-tests',
        tip: 'Aksiyon listesini panoya kopyalayarak olay yönetim aracına aktarabilirsin.'
      },
      {
        id: 'rate-limits',
        title: 'Hız Sınırı Paneli',
        description: '429 oranı eşikleri geçtiğinde uyarılar tetiklenir. Önceliklendirme için kırmızı etiketleri takip et.',
        anchor: 'rate-limits',
        tip: 'Operatörlerle paylaşmak için ekran görüntüsü veya CSV dışa aktarımı ekleniyor.'
      },
      {
        id: 'activity-center',
        title: 'Etkinlik Merkezi',
        description: 'Gerçek zamanlı bildirimleri ve toast geçmişini buradan yönet. Kritik olayları işaretle.',
        anchor: 'activity-center',
        tip: 'Filtreleyerek yalnızca kritik olayları göster.'
      }
    ]
  },
  operator: {
    label: 'Operatör',
    description:
      'Günlük operasyonu sürdür, bot ve sohbet akışlarını dengede tut. Aşağıdaki görevler temponu korumana yardım eder.',
    iconAccent: 'text-emerald-600',
    tasks: [
      {
        id: 'simulation',
        title: 'Simülasyon temposunu ayarla',
        detail: 'Simülasyon aktif değilse yeniden başlat, hız çarpanı 1.5x altına düşerse artır.',
        computeStatus: (metrics) => {
          if (!metrics.simulation_active) {
            return { level: 'critical', message: 'Simülasyon durdu' }
          }
          if (metrics.scale_factor < 1) {
            return { level: 'warning', message: `${metrics.scale_factor}x hız` }
          }
          return { level: 'success', message: `${metrics.scale_factor}x hız` }
        },
        nextStep: 'Wizard üzerinden parametreleri güncelle'
      },
      {
        id: 'bot-balance',
        title: 'Bot yük dağılımını takip et',
        detail: 'Aktif bot oranı %70 altında ise yeni bot eklemeyi düşün.',
        computeStatus: (metrics) => {
          if (!metrics.total_bots) {
            return { level: 'warning', message: 'Bot bulunamadı' }
          }
          const utilisation = (metrics.active_bots / metrics.total_bots) * 100
          if (utilisation < 50) {
            return { level: 'warning', message: `%${utilisation.toFixed(0)} aktif` }
          }
          return { level: 'success', message: `%${utilisation.toFixed(0)} aktif` }
        },
        nextStep: 'Bot listesinde filtreleme yap'
      },
      {
        id: 'chat-hygiene',
        title: 'Sohbet hijyenini sağla',
        detail: 'Uzun süredir kapalı sohbetleri temizle, kritik sohbetleri pinle.',
        computeStatus: (metrics) => {
          if (!metrics.total_chats) {
            return { level: 'info', message: 'Sohbet verisi bekleniyor' }
          }
          if (metrics.total_chats > 120) {
            return { level: 'warning', message: `${metrics.total_chats} sohbet` }
          }
          return { level: 'success', message: `${metrics.total_chats} sohbet` }
        },
        nextStep: 'Sohbetler sekmesinde filtreleri uygula'
      }
    ],
    tour: [
      {
        id: 'ops-panel',
        title: 'Operasyon Paneli',
        description: 'Temel metrik kartları simülasyon temposu ve mesaj hızını karşılaştırır.',
        anchor: 'metrics-grid',
        tip: 'Ctrl+Alt+C kısayolu ile testi başlatıp sonucu bekle.'
      },
      {
        id: 'persona-refresh',
        title: 'Persona hatırlatıcıları',
        description: 'Davranış motoru hangi kullanıcılara persona tazeleme yapılacağını burada listeler.',
        anchor: 'behavior-insights',
        tip: 'Her tazeleme sonrası notu Activity Center üzerinden paylaş.'
      },
      {
        id: 'suggestions',
        title: 'Akıllı öneriler',
        description: 'Sistem davranışına göre aksiyon önerilerini bu bölümde görürsün.',
        anchor: 'smart-suggestions',
        tip: 'Önerileri uyguladığında "Yapıldı" olarak işaretle.'
      }
    ]
  },
  viewer: {
    label: 'Analist',
    description:
      'Durum farkındalığını koru, trendleri yakala ve raporla. Önerilen odak alanları aşağıda.',
    iconAccent: 'text-sky-600',
    tasks: [
      {
        id: 'trend-monitor',
        title: 'Trend göstergelerini yorumla',
        detail: 'Mesaj hızındaki ani düşüşler için not al ve rapora ekle.',
        computeStatus: (metrics) => {
          const messagesPerMinute = Number(metrics.messages_per_minute ?? 0)
          if (messagesPerMinute < 0.5) {
            return { level: 'warning', message: `${messagesPerMinute.toFixed(1)} msg/dk` }
          }
          return { level: 'info', message: `${messagesPerMinute.toFixed(1)} msg/dk` }
        },
        nextStep: 'Trend raporuna işaretle'
      },
      {
        id: 'summary-digest',
        title: 'Test sonuçlarını özetle',
        detail: 'Özet KPI kartından başarı oranı ve önerileri alıp haftalık rapora ekle.',
        computeStatus: (_, summary) => {
          if (!summary) {
            return { level: 'info', message: 'Veri bekleniyor' }
          }
          const successRate = Math.round((summary.success_rate ?? 0) * 1000) / 10
          if (successRate < 70) {
            return { level: 'critical', message: `%${successRate.toFixed(1)} başarı` }
          }
          if (successRate < 90) {
            return { level: 'warning', message: `%${successRate.toFixed(1)} başarı` }
          }
          return { level: 'success', message: `%${successRate.toFixed(1)} başarı` }
        },
        nextStep: 'Analist notlarını güncelle'
      },
      {
        id: 'insight-share',
        title: 'İçgörü paylaş',
        detail: 'Activity Center içindeki kritik olayları etiketleyip ekip kanalına aktar.',
        computeStatus: () => ({ level: 'info', message: 'Haftalık en az 2 içgörü paylaş' }),
        nextStep: 'Paylaşılan içgörüleri arşivle'
      }
    ],
    tour: [
      {
        id: 'kpi-banner',
        title: 'KPI kartları',
        description: 'Metrik kartları hızlı kıyaslama sağlar, renk kodları pozitif/negatif durumları gösterir.',
        anchor: 'metrics-grid',
        tip: 'Kartlara tıklayarak detay modülünü aç.'
      },
      {
        id: 'history',
        title: 'Son test koşuları',
        description: 'Başarılı ve hatalı adımlar arasındaki farkları inceleyerek trend çıkar.',
        anchor: 'automation-tests',
        tip: 'Tüm koşuları CSV olarak dışa aktarma planlandı.'
      },
      {
        id: 'knowledge',
        title: 'Bilgi tabanı bağlantıları',
        description: 'Yardım makaleleri ve rehberli turlar buradan erişilebilir olacak.',
        anchor: 'help-drawer',
        tip: 'Eksik içerikleri Activity Center üzerinden bildir.'
      }
    ]
  }
}

function Dashboard({
  metrics,
  lastUpdatedAt,
  isLoading = false,
  isRefreshing = false,
  systemCheck = null,
  systemSummary = null,
  onRunChecks = () => {},
  isRunningChecks = false,
  sessionRole = 'viewer',
  sessionMeta = null
}) {
  const safeMetrics = metrics || {}
  const { t, locale } = useTranslation()
  const tf = (key, fallback) => {
    try {
      return t?.(key) || fallback
    } catch (error) {
      console.warn('Translation error:', error)
      return fallback
    }
  }
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
  const [metricsView, , metricsViewActions] = useAdaptiveView('dashboard.metrics', 'cards')

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

  const metricsItems = [
    {
      id: 'total-bots',
      title: 'Toplam Bot',
      icon: Bot,
      iconClass: `h-4 w-4 ${isLoading ? 'text-muted-foreground' : utilisationAccent}`,
      valueNode: renderValue(safeMetrics.total_bots, 'w-16'),
      subNode: renderSubtle(`${safeMetrics.active_bots} aktif`, 'w-20'),
      subClass: 'text-muted-foreground',
      footerNode: <Progress value={botUtilization} />
    },
    {
      id: 'messages-hour',
      title: 'Saatlik Mesaj',
      icon: MessageSquare,
      iconClass: `h-4 w-4 ${
        messageRateStatus === 'destructive'
          ? 'text-destructive'
          : messageRateStatus === 'warning'
            ? 'text-amber-600'
            : 'text-muted-foreground'
      }`,
      valueNode: renderValue(safeMetrics.messages_last_hour, 'w-20'),
      valueClass:
        messageRateStatus === 'destructive'
          ? 'text-destructive'
          : messageRateStatus === 'warning'
            ? 'text-amber-700'
            : '',
      subNode: renderSubtle(`${safeMetrics.messages_per_minute?.toFixed?.(1) ?? '0.0'} msg/dk`, 'w-24'),
      subClass:
        messageRateStatus === 'destructive'
          ? 'text-destructive'
          : messageRateStatus === 'warning'
            ? 'text-amber-700'
            : 'text-muted-foreground',
      cardClass:
        messageRateStatus === 'destructive'
          ? 'border-destructive/40 bg-destructive/5'
          : messageRateStatus === 'warning'
            ? 'border-amber-200/70 bg-amber-50/60'
            : '',
      footerNode: null
    },
    {
      id: 'total-chats',
      title: 'Aktif Sohbet',
      icon: Users,
      iconClass: 'h-4 w-4 text-muted-foreground',
      valueNode: renderValue(safeMetrics.total_chats, 'w-16'),
      subNode: renderSubtle('Toplam sohbet sayısı', 'w-28'),
      subClass: 'text-muted-foreground',
      footerNode: null
    },
    {
      id: 'scale-factor',
      title: 'Ölçek Faktörü',
      icon: Zap,
      iconClass: `h-4 w-4 ${safeMetrics.scale_factor > 1.5 ? 'text-primary' : 'text-muted-foreground'}`,
      valueNode: renderValue(`${safeMetrics.scale_factor}x`, 'w-16'),
      subNode: renderSubtle('Hız çarpanı', 'w-20'),
      subClass: 'text-muted-foreground',
      footerNode: null
    }
  ]

  const summaryPending = !systemSummary && (isLoading || isRefreshing)
  const summaryRuns = systemSummary?.total_runs ?? 0
  const summarySuccessPercent = systemSummary ? Math.round(systemSummary.success_rate * 1000) / 10 : 0
  const formattedSuccessPercent = summarySuccessPercent.toFixed(1)
  const summarySuccessAccent =
    summaryRuns === 0
      ? 'text-muted-foreground'
      : summarySuccessPercent >= 90
        ? 'text-emerald-600'
        : summarySuccessPercent >= 70
          ? 'text-amber-600'
          : 'text-rose-600'
  const averageDurationValue =
    systemSummary && typeof systemSummary.average_duration === 'number'
      ? systemSummary.average_duration.toFixed(1)
      : '—'
  const summaryLastRun = systemSummary?.last_run_at ? new Date(systemSummary.last_run_at) : null
  const summaryLastRunLabel = summaryLastRun
    ? summaryLastRun.toLocaleString('tr-TR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    : 'Çalıştırılmadı'
  const summaryLastRunRelative = summaryLastRun ? formatRelativeTime(summaryLastRun) : null
  const summaryWindowStart = systemSummary?.window_start ? new Date(systemSummary.window_start) : null
  const summaryWindowEnd = systemSummary?.window_end ? new Date(systemSummary.window_end) : null
  const summaryWindowLabel =
    summaryWindowStart && summaryWindowEnd
      ? `${summaryWindowStart.toLocaleDateString('tr-TR', {
          day: '2-digit',
          month: '2-digit'
        })} – ${summaryWindowEnd.toLocaleDateString('tr-TR', {
          day: '2-digit',
          month: '2-digit'
        })}`
      : null
  const summaryWindowDays = systemSummary
    ? Math.max(
        1,
        Math.round(
          (new Date(systemSummary.window_end).getTime() - new Date(systemSummary.window_start).getTime()) /
            (1000 * 60 * 60 * 24)
        )
      )
    : 7
  const summaryBuckets = systemSummary?.daily_breakdown ?? []
  const recentBuckets = summaryBuckets.slice(-3).reverse()
  const summaryRecentRuns = systemSummary?.recent_runs ?? []
  const hasRecentRuns = summaryRecentRuns.length > 0

  const fallbackRole = useMemo(
    () => (ROLE_GUIDES[sessionRole] ? sessionRole : 'operator'),
    [sessionRole]
  )
  const [activeRole, setActiveRole] = useState(fallbackRole)
  useEffect(() => {
    setActiveRole(fallbackRole)
  }, [fallbackRole])
  const roleGuide = ROLE_GUIDES[activeRole] ?? ROLE_GUIDES.operator
  const [selectedTourStep, setSelectedTourStep] = useState(roleGuide?.tour?.[0]?.id ?? null)
  useEffect(() => {
    setSelectedTourStep(roleGuide?.tour?.[0]?.id ?? null)
  }, [roleGuide])
  const activeTourStep = useMemo(
    () => roleGuide?.tour?.find((step) => step.id === selectedTourStep) ?? null,
    [roleGuide, selectedTourStep]
  )

  const resolveTaskStatus = (task) => {
    if (!task) {
      return { level: 'info', message: '' }
    }
    const result = task.computeStatus?.(safeMetrics, systemSummary, sessionMeta) ?? { level: 'info', message: '' }
    const meta = TASK_STATUS_META[result.level] ?? TASK_STATUS_META.info
    return {
      meta,
      message: result.message,
      level: result.level ?? 'info'
    }
  }

  const summaryStatusMeta = {
    healthy: {
      label: 'Sağlıklı',
      badgeClass: 'border border-emerald-200 bg-emerald-50 text-emerald-700',
      icon: ShieldCheck,
      iconClass: 'text-emerald-600',
      containerClass: 'border border-emerald-200/70 bg-emerald-50/50'
    },
    warning: {
      label: 'Uyarı',
      badgeClass: 'border border-amber-200 bg-amber-50 text-amber-700',
      icon: AlertTriangle,
      iconClass: 'text-amber-600',
      containerClass: 'border border-amber-200/70 bg-amber-50/50'
    },
    critical: {
      label: 'Kritik',
      badgeClass: 'border border-rose-200 bg-rose-50 text-rose-700',
      icon: XCircle,
      iconClass: 'text-rose-600',
      containerClass: 'border border-rose-200/70 bg-rose-50/50'
    },
    empty: {
      label: 'Veri Yok',
      badgeClass: 'border border-muted-foreground/40 bg-muted/30 text-muted-foreground',
      icon: Info,
      iconClass: 'text-muted-foreground',
      containerClass: 'border border-dashed border-muted-foreground/40 bg-muted/20'
    }
  }

  const runStatusMeta = {
    passed: {
      label: 'Başarılı',
      icon: CheckCircle,
      textClass: 'text-emerald-600',
      chipClass: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
      containerClass: 'border border-emerald-200/70 bg-emerald-50/60'
    },
    failed: {
      label: 'Başarısız',
      icon: XCircle,
      textClass: 'text-rose-600',
      chipClass: 'bg-rose-100 text-rose-700 border border-rose-200',
      containerClass: 'border border-rose-200/70 bg-rose-50/60'
    }
  }

  const summaryStatus = systemSummary?.overall_status ?? (summaryRuns === 0 ? 'empty' : 'healthy')
  const summaryStatusInfo = summaryStatusMeta[summaryStatus] ?? summaryStatusMeta.empty
  const suggestionAppearance = useMemo(
    () => ({
      critical: {
        container: 'border border-rose-200/80 bg-rose-50/80',
        badgeClass: 'border border-rose-200 bg-rose-100 text-rose-700',
        label: t('dashboard.suggestions.label.critical') || 'Kritik'
      },
      warning: {
        container: 'border border-amber-200/80 bg-amber-50/80',
        badgeClass: 'border border-amber-200 bg-amber-100 text-amber-700',
        label: t('dashboard.suggestions.label.warning') || 'Uyarı'
      },
      info: {
        container: 'border border-sky-200/80 bg-sky-50/80',
        badgeClass: 'border border-sky-200 bg-sky-100 text-sky-700',
        label: t('dashboard.suggestions.label.info') || 'Bilgi'
      },
      success: {
        container: 'border border-emerald-200/80 bg-emerald-50/80',
        badgeClass: 'border border-emerald-200 bg-emerald-100 text-emerald-700',
        label: t('dashboard.suggestions.label.success') || 'Stabil'
      },
      neutral: {
        container: 'border border-border/70 bg-muted/30',
        badgeClass: 'border border-border bg-background text-muted-foreground',
        label: t('dashboard.suggestions.label.neutral') || 'Bilgi'
      }
    }),
    [t, locale]
  )
  const suggestionEntries = useMemo(() => {
    const entries = []
    if ((safeMetrics.total_bots ?? 0) < 2) {
      entries.push({
        icon: Bot,
        iconClass: 'text-primary',
        title: t('dashboard.suggestions.lowBot.title') || 'Bot sayınız sınırlı görünüyor',
        body: t('dashboard.suggestions.lowBot.body') || 'Kurulum sihirbazından yeni bir persona ekleyerek sohbet yoğunluğunu dengeleyebilirsiniz.',
        action: t('dashboard.suggestions.lowBot.action') || 'Kurulum > Bot & Sohbet adımı üzerinden yeni bot oluşturun.',
        severity: 'info'
      })
    }
    if (rateLimit429Rate >= 5) {
      entries.push({
        icon: AlertTriangle,
        iconClass: rateLimit429Rate >= 10 ? 'text-rose-600' : 'text-amber-600',
        title: t('dashboard.suggestions.rateLimit.title') || 'Telegram 429 oranı yükseliyor',
        body: t('dashboard.suggestions.rateLimit.body') || 'Dakikadaki mesaj limiti ile prime hours ayarlarını düşürmek throttling riskini azaltır.',
        action: t('dashboard.suggestions.rateLimit.action') || 'Ayarlar > Zamanlama sekmesinden limitleri düşürün veya prime hours aralığını daraltın.',
        severity: rateLimit429Rate >= 10 ? 'critical' : 'warning'
      })
    }
    if (summaryStatus === 'critical' || summaryStatus === 'warning') {
      entries.push({
        icon: FlaskConical,
        iconClass: summaryStatus === 'critical' ? 'text-rose-600' : 'text-amber-600',
        title: t('dashboard.suggestions.tests.title') || 'Test özetinde açık maddeler var',
        body: t('dashboard.suggestions.tests.body') || 'Son otomasyon koşusundaki başarısız adımlar için runbook aksiyonlarını gözden geçirin.',
        action: t('dashboard.suggestions.tests.action') || 'Etkinlik Merkezi ve Runbook kartlarından ilgili kayıtları inceleyin.',
        severity: summaryStatus === 'critical' ? 'critical' : 'warning'
      })
    }
    if (!entries.length && summaryRuns === 0) {
      entries.push({
        icon: CalendarDays,
        iconClass: 'text-muted-foreground',
        title: t('dashboard.suggestions.noRuns.title') || 'Henüz doğrulama koşusu yapılmadı',
        body: t('dashboard.suggestions.noRuns.body') || 'İlk otomasyon koşusunu çalıştırmak sistem sağlığını takip etmenizi kolaylaştırır.',
        action: t('dashboard.suggestions.noRuns.action') || 'Dashboard sağ üstündeki "Kontrolleri Çalıştır" butonuyla testi başlatın.',
        severity: 'neutral'
      })
    }
    if (!entries.length) {
      entries.push({
        icon: Sparkles,
        iconClass: 'text-primary',
        title: t('dashboard.suggestions.stable.title') || 'Sistem stabil görünüyor',
        body: t('dashboard.suggestions.stable.body') || 'Davranış ayarlarını deneysel olarak güncelleyip kullanıcı segmentleri için A/B çalıştırabilirsiniz.',
        action: t('dashboard.suggestions.stable.action') || 'Ayarlar > Davranış sekmesinden persona farklılaştırmaları yapmayı deneyin.',
        severity: 'success'
      })
    }
    return entries
  }, [safeMetrics.total_bots, rateLimit429Rate, summaryStatus, summaryRuns, t, locale])
  const SummaryStatusIcon = summaryStatusInfo.icon
  const summaryStatusIconClass = summaryStatusInfo.iconClass ?? 'text-muted-foreground'
  const summaryMessage = systemSummary?.overall_message ??
    (summaryRuns === 0
      ? 'Son günlerde otomasyon testi sonucu bulunmuyor.'
      : 'Sistem özeti alınamadı.')
  const summaryInsights = systemSummary?.insights ?? []
  const summaryActions = systemSummary?.recommended_actions ?? []

  const [insightsExpanded, setInsightsExpanded] = useState(false)
  const [actionsExpanded, setActionsExpanded] = useState(false)
  const [copyStatus, setCopyStatus] = useState(null)

  useEffect(() => {
    setInsightsExpanded(false)
    setActionsExpanded(false)
  }, [summaryRuns, summaryPending])

  useEffect(() => {
    if (!copyStatus) {
      return undefined
    }
    const timeout = window.setTimeout(() => setCopyStatus(null), 2500)
    return () => window.clearTimeout(timeout)
  }, [copyStatus])

  const hasExtraInsights = summaryInsights.length > 2
  const displayedInsights = useMemo(
    () => (hasExtraInsights && !insightsExpanded ? summaryInsights.slice(0, 2) : summaryInsights),
    [summaryInsights, hasExtraInsights, insightsExpanded]
  )
  const insightsRemainder = Math.max(summaryInsights.length - displayedInsights.length, 0)

  const hasExtraActions = summaryActions.length > 2
  const displayedActions = useMemo(
    () => (hasExtraActions && !actionsExpanded ? summaryActions.slice(0, 2) : summaryActions),
    [summaryActions, hasExtraActions, actionsExpanded]
  )
  const actionsRemainder = Math.max(summaryActions.length - displayedActions.length, 0)

  const clipboardSupported =
    typeof navigator !== 'undefined' && typeof navigator.clipboard?.writeText === 'function'

  const handleCopyActions = async () => {
    if (!summaryActions.length) {
      return
    }
    if (!clipboardSupported) {
      setCopyStatus({ type: 'error', message: 'Tarayıcınız panoya kopyalamayı desteklemiyor.' })
      return
    }
    try {
      await navigator.clipboard.writeText(summaryActions.join('\n'))
      setCopyStatus({ type: 'success', message: 'Aksiyon listesi panoya kopyalandı.' })
    } catch (error) {
      console.warn('Aksiyonlar panoya kopyalanamadı:', error)
      setCopyStatus({ type: 'error', message: 'Panoya kopyalama başarısız oldu.' })
    }
  }

  const renderRecommendedActions = (showEmptyFallback = false) => {
    if (!summaryActions.length) {
      if (!showEmptyFallback) {
        return null
      }
      return (
        <p className="text-xs text-muted-foreground">
          Panelden testleri çalıştırarak özet oluşturabilirsiniz.
        </p>
      )
    }
    return (
      <div className="rounded-lg border border-primary/40 bg-primary/5 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs uppercase tracking-wide text-primary">Önerilen aksiyonlar</p>
          <div className="flex items-center gap-1">
            {hasExtraActions ? (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs"
                onClick={() => setActionsExpanded((prev) => !prev)}
              >
                {actionsExpanded ? (
                  <span className="flex items-center gap-1">
                    <ChevronUp className="h-3 w-3" /> Daralt
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <ChevronDown className="h-3 w-3" /> Tümünü göster
                  </span>
                )}
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={handleCopyActions}
              disabled={!summaryActions.length || !clipboardSupported}
              title={clipboardSupported ? 'Aksiyon listesini panoya kopyala' : 'Tarayıcı panoya kopyalamayı desteklemiyor'}
            >
              <span className="flex items-center gap-1">
                {copyStatus?.type === 'success' ? (
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <Copy className="h-3.5 w-3.5 text-muted-foreground" />
                )}
                {copyStatus?.type === 'success' ? 'Kopyalandı' : 'Kopyala'}
              </span>
            </Button>
          </div>
        </div>
        {copyStatus ? (
          <p
            className={`mt-1 text-xs ${copyStatus.type === 'error' ? 'text-rose-600' : 'text-emerald-600'}`}
            aria-live="polite"
          >
            {copyStatus.message}
          </p>
        ) : null}
        <ul className="mt-2 space-y-2">
          {displayedActions.map((action) => (
            <li key={action} className="flex items-start gap-2 text-sm text-primary">
              <ListChecks className="mt-0.5 h-4 w-4 text-primary" />
              <span>{action}</span>
            </li>
          ))}
        </ul>
        {!actionsExpanded && actionsRemainder > 0 ? (
          <p className="mt-2 text-xs text-muted-foreground">+{actionsRemainder} ek öneri daha var.</p>
        ) : null}
      </div>
    )
  }

  const insightStyles = {
    success: {
      icon: CheckCircle,
      iconClass: 'text-emerald-600',
      containerClass: 'border border-emerald-200 bg-emerald-50'
    },
    info: {
      icon: Info,
      iconClass: 'text-sky-600',
      containerClass: 'border border-sky-200 bg-sky-50'
    },
    warning: {
      icon: AlertTriangle,
      iconClass: 'text-amber-600',
      containerClass: 'border border-amber-200 bg-amber-50'
    },
    critical: {
      icon: XCircle,
      iconClass: 'text-rose-600',
      containerClass: 'border border-rose-200 bg-rose-50'
    }
  }

  const statusBadgeClass = systemCheck?.status === 'passed'
    ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
    : 'bg-rose-100 text-rose-700 border-rose-200'
  const statusLabel = systemCheck?.status === 'passed' ? 'Başarılı' : systemCheck?.status === 'failed' ? 'Hata var' : 'Çalıştırılmadı'
  const lastCheckAt = systemCheck?.created_at ? new Date(systemCheck.created_at) : null
  const formattedCheckTime = lastCheckAt
    ? lastCheckAt.toLocaleString('tr-TR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        day: '2-digit',
        month: '2-digit'
      })
    : null

  const summarizeStep = (text) => {
    if (!text) {
      return null
    }
    const trimmed = text.trim()
    if (!trimmed) {
      return null
    }
    return trimmed.split('\n').slice(0, 2).join(' ')
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

      <section id="metrics-grid" className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="text-base font-semibold text-muted-foreground">Metrik görünümü</h3>
          <ViewModeToggle
            mode={metricsView}
            onChange={metricsViewActions.set}
            cardsLabel={tf('view.cards', 'Kartlar')}
            tableLabel={tf('view.table', 'Tablo')}
            ariaLabel={tf('view.modeLabel', 'Görünüm modu')}
          />
        </div>

        {isTableView(metricsView) ? (
          <div className="overflow-hidden rounded-lg border border-border bg-background">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Metrik</th>
                  <th className="px-4 py-3 text-right font-medium">Değer</th>
                  <th className="px-4 py-3 text-left font-medium">Detay</th>
                </tr>
              </thead>
              <tbody>
                {metricsItems.map((item) => (
                  <tr key={item.id} className="border-t border-border/60">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <item.icon className={`${item.iconClass}`} />
                        <span className="font-medium">{item.title}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className={`flex justify-end text-sm font-semibold ${item.valueClass ?? ''}`}>
                        {item.valueNode}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className={`text-xs ${item.subClass ?? 'text-muted-foreground'}`}>{item.subNode || '—'}</div>
                      {item.footerNode ? <div className="mt-2 max-w-xs">{item.footerNode}</div> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {metricsItems.map((item) => {
              const Icon = item.icon
              return (
                <Card key={item.id} className={item.cardClass ?? ''}>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">{item.title}</CardTitle>
                    <Icon className={item.iconClass} />
                  </CardHeader>
                  <CardContent>
                    <div className={`text-2xl font-bold ${item.valueClass ?? ''}`}>{item.valueNode}</div>
                    <div className={`mt-1 text-xs ${item.subClass ?? 'text-muted-foreground'}`}>{item.subNode}</div>
                    {item.footerNode ? <div className="mt-2">{item.footerNode}</div> : null}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </section>

      <Card className="border-primary/40 bg-primary/5">
        <CardHeader className="gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" /> {t('dashboard.suggestions.title') || 'Akıllı Öneriler'}
            </CardTitle>
            <CardDescription>
              {t('dashboard.suggestions.description') || 'Canlı metrikler ve test sonuçlarına göre proaktif aksiyon önerileri.'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {suggestionEntries.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
              {t('dashboard.suggestions.empty', 'Şu anda gösterilecek öneri yok.')}
            </div>
          ) : (
            suggestionEntries.map((entry, index) => {
              const Icon = entry.icon
              const appearance = suggestionAppearance[entry.severity] ?? suggestionAppearance.neutral
              return (
                <div
                  key={index}
                  className={`flex items-start gap-3 rounded-md px-3 py-3 shadow-sm ${appearance.container}`}
                >
                  <Icon className={`h-4 w-4 mt-1 ${entry.iconClass}`} />
                  <div className="space-y-1">
                    <Badge variant="outline" className={`h-5 rounded-sm px-2 text-[10px] uppercase tracking-wide ${appearance.badgeClass}`}>
                      {appearance.label}
                    </Badge>
                    <p className="text-sm font-medium text-foreground">{entry.title}</p>
                    <p className="text-xs text-muted-foreground">{entry.body}</p>
                    {entry.action ? (
                      <p className="text-xs font-medium text-primary">{entry.action}</p>
                    ) : null}
                  </div>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      <Card id="role-guides" className="border-primary/40 bg-primary/5">
        <CardHeader className="gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Rol Bazlı Görev Panoları
            </CardTitle>
            <CardDescription>
              Kullanıcı rolüne göre odak görevleri ve bağlamsal yardım turları.
            </CardDescription>
          </div>
          <Badge variant="outline" className="mt-2 w-fit text-xs uppercase tracking-wide">
            Aktif Rol: {ROLE_GUIDES[activeRole]?.label || 'Operatör'}
          </Badge>
        </CardHeader>
        <CardContent>
          <Tabs value={activeRole} onValueChange={setActiveRole} className="w-full">
            <div className="flex flex-col gap-4 lg:flex-row">
              <TabsList className="flex-col items-stretch justify-start gap-2 lg:w-52">
                {Object.entries(ROLE_GUIDES).map(([roleKey, config]) => (
                  <TabsTrigger key={roleKey} value={roleKey} className="justify-start">
                    <span className="text-sm font-medium">{config.label}</span>
                  </TabsTrigger>
                ))}
              </TabsList>
              <div className="flex-1">
                {Object.entries(ROLE_GUIDES).map(([roleKey, config]) => (
                  <TabsContent key={roleKey} value={roleKey} className="space-y-4">
                    <div className="rounded-lg border border-border/70 bg-background/80 p-4 shadow-sm">
                      <div className="flex items-start gap-3">
                        <Target className={`mt-0.5 h-5 w-5 ${config.iconAccent}`} />
                        <div>
                          <p className="text-sm font-semibold">{config.label} odak alanı</p>
                          <p className="text-sm text-muted-foreground">{config.description}</p>
                        </div>
                      </div>
                    </div>
                    <div className="grid gap-4 lg:grid-cols-3">
                      <div className="space-y-3 lg:col-span-2">
                        {config.tasks.map((task) => {
                          const status = resolveTaskStatus(task)
                          return (
                            <div
                              key={task.id}
                              className="rounded-lg border border-border/60 bg-card/60 p-4 shadow-sm"
                            >
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-semibold">{task.title}</p>
                                  <p className="text-sm text-muted-foreground">{task.detail}</p>
                                </div>
                                <Badge variant="outline" className={status.meta.badgeClass}>
                                  {status.meta.label}
                                </Badge>
                              </div>
                              {status.message ? (
                                <p className="mt-2 text-xs text-muted-foreground">{status.message}</p>
                              ) : null}
                              {task.nextStep ? (
                                <div className="mt-3 flex items-center gap-2 text-xs text-primary">
                                  <Flag className="h-3.5 w-3.5" />
                                  <span>{task.nextStep}</span>
                                </div>
                              ) : null}
                            </div>
                          )
                        })}
                      </div>
                      <div className="rounded-lg border border-dashed border-primary/40 bg-primary/10 p-4">
                        <div className="flex items-start gap-2">
                          <HelpCircle className="h-5 w-5 text-primary" />
                          <div>
                            <p className="text-sm font-semibold">Bağlamsal yardım turu</p>
                            <p className="text-xs text-muted-foreground">
                              Panodaki kritik bileşenleri sırayla keşfetmek için adımları seç.
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          {config.tour.map((step) => {
                            const isActive = step.id === selectedTourStep
                            return (
                              <Button
                                key={step.id}
                                type="button"
                                variant={isActive ? 'default' : 'ghost'}
                                className={`w-full justify-start text-left ${
                                  isActive ? '' : 'bg-transparent'
                                }`}
                                onClick={() => setSelectedTourStep(step.id)}
                              >
                                <span className="flex flex-col text-sm">
                                  <span className="font-semibold">{step.title}</span>
                                  <span className="text-xs text-muted-foreground">{step.description}</span>
                                </span>
                              </Button>
                            )
                          })}
                        </div>
                        {activeTourStep ? (
                          <div className="mt-4 rounded-lg border border-primary/60 bg-background/80 p-3 shadow-sm">
                            <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                              {activeTourStep.title}
                            </p>
                            <p className="mt-2 text-sm text-muted-foreground">{activeTourStep.description}</p>
                            {activeTourStep.tip ? (
                              <div className="mt-3 flex items-start gap-2 rounded-md bg-primary/5 p-2 text-xs text-primary">
                                <BookOpenCheck className="mt-0.5 h-4 w-4" />
                                <div>
                                  <p className="font-semibold">İpucu</p>
                                  <p>{activeTourStep.tip}</p>
                                </div>
                              </div>
                            ) : null}
                            {activeTourStep.anchor ? (
                              <p className="mt-3 text-[11px] uppercase tracking-wide text-muted-foreground">
                                Hedef: #{activeTourStep.anchor}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </TabsContent>
                ))}
              </div>
            </div>
          </Tabs>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
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

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Sistem Sağlık Özeti
            </CardTitle>
            <CardDescription>Son {summaryWindowDays} günlük görünüm</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(summaryPending || systemSummary) && (
              <div className="rounded-lg border border-border/60 bg-card/40 p-3 text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
                  <div className="flex-1">
                    {summaryPending
                      ? placeholder('w-32')
                      : summaryWindowLabel
                        ? `Kapsam: ${summaryWindowLabel}`
                        : 'Veri kapsamı hesaplanıyor.'}
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                  <div className="flex-1">
                    {summaryPending
                      ? placeholder('w-28')
                      : summaryLastRunRelative
                        ? `Son koşu ${summaryLastRunRelative} (${summaryLastRunLabel})`
                        : 'Son koşu bilgisi bulunmuyor.'}
                  </div>
                </div>
              </div>
            )}
            {summaryPending ? (
              <div className="space-y-3">
                {placeholder('w-full')}
                {placeholder('w-5/6')}
                {placeholder('w-2/3')}
              </div>
            ) : !systemSummary ? (
              <p className="text-sm text-muted-foreground">
                Sistem özeti alınamadı. Yenilemeyi deneyin veya kısa süre sonra tekrar bakın.
              </p>
            ) : summaryRuns === 0 ? (
              <div className="space-y-4">
                <div className={`rounded-lg p-4 ${summaryStatusInfo.containerClass}`}>
                  <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    <SummaryStatusIcon className={`h-4 w-4 ${summaryStatusIconClass}`} />
                    {summaryStatusInfo.label}
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{summaryMessage}</p>
                </div>
                {renderRecommendedActions(true)}
              </div>
            ) : (
              <>
                <div className={`rounded-lg p-4 ${summaryStatusInfo.containerClass}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <SummaryStatusIcon className={`h-4 w-4 ${summaryStatusIconClass}`} />
                      Genel Durum
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${summaryStatusInfo.badgeClass}`}>
                      {summaryStatusInfo.label}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{summaryMessage}</p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Toplam Koşu</span>
                    <span className="text-base font-semibold">{summaryRuns}</span>
                  </div>
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Başarı Oranı</span>
                      <span className={`text-base font-semibold ${summarySuccessAccent}`}>
                        {formattedSuccessPercent}%
                      </span>
                    </div>
                    <Progress value={summarySuccessPercent} className="mt-2 h-2" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Ortalama Süre</span>
                    <span className="text-base font-semibold">{averageDurationValue} sn</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Son Koşu</span>
                    <span className="text-xs text-muted-foreground">{summaryLastRunLabel}</span>
                  </div>
                </div>

                {summaryInsights.length ? (
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Öne çıkan noktalar</p>
                      {hasExtraInsights ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-xs"
                          onClick={() => setInsightsExpanded((prev) => !prev)}
                        >
                          {insightsExpanded ? (
                            <span className="flex items-center gap-1">
                              <ChevronUp className="h-3 w-3" /> Daralt
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <ChevronDown className="h-3 w-3" /> Tümünü göster
                            </span>
                          )}
                        </Button>
                      ) : null}
                    </div>
                    <ul className="mt-2 space-y-2">
                      {displayedInsights.map((insight) => {
                        const style = insightStyles[insight.level] ?? insightStyles.info
                        const InsightIcon = style.icon
                        return (
                          <li key={insight.message} className={`rounded-lg p-3 ${style.containerClass}`}>
                            <div className="flex items-start gap-3">
                              <InsightIcon className={`mt-0.5 h-4 w-4 ${style.iconClass}`} />
                              <span className="text-sm text-foreground">{insight.message}</span>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                    {!insightsExpanded && insightsRemainder > 0 ? (
                      <p className="mt-2 text-xs text-muted-foreground">+{insightsRemainder} ek not daha var.</p>
                    ) : null}
                  </div>
                ) : null}

                {renderRecommendedActions()}

                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Son koşular</p>
                  {summaryPending && !hasRecentRuns ? (
                    <div className="mt-2 space-y-2">
                      {[0, 1].map((index) => (
                        <div
                          // eslint-disable-next-line react/no-array-index-key
                          key={index}
                          className="rounded-md border border-border/40 bg-muted/30 p-3"
                        >
                          <div className="flex items-center justify-between">
                            {placeholder('w-24')}
                            <div className="h-3 w-20 rounded bg-muted/50 animate-pulse" aria-hidden="true" />
                          </div>
                          <div className="mt-2 h-3 w-3/4 rounded bg-muted/40 animate-pulse" aria-hidden="true" />
                        </div>
                      ))}
                    </div>
                  ) : hasRecentRuns ? (
                    <ul className="mt-2 space-y-2">
                      {summaryRecentRuns.map((run) => {
                        const statusInfo = runStatusMeta[run.status] ?? runStatusMeta.failed
                        const RunStatusIcon = statusInfo.icon
                        const runDate = run.created_at ? new Date(run.created_at) : null
                        const runRelative = runDate ? formatRelativeTime(runDate) : null
                        const runDateLabel = runDate
                          ? runDate.toLocaleString('tr-TR', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit'
                            })
                          : 'Zaman bilgisi yok'
                        const detailParts = []
                        if (typeof run.total_steps === 'number' && Number.isFinite(run.total_steps)) {
                          const passedSteps =
                            typeof run.passed_steps === 'number' && Number.isFinite(run.passed_steps)
                              ? run.passed_steps
                              : null
                          const failedSteps =
                            typeof run.failed_steps === 'number' && Number.isFinite(run.failed_steps)
                              ? run.failed_steps
                              : null
                          let stepsLabel = `${run.total_steps} adım`
                          if (typeof passedSteps === 'number') {
                            stepsLabel = `${passedSteps}/${run.total_steps} adım tamamlandı`
                          }
                          if (typeof failedSteps === 'number' && failedSteps > 0) {
                            stepsLabel += `, ${failedSteps} hata`
                          }
                          detailParts.push(stepsLabel)
                        }
                        if (typeof run.duration === 'number' && Number.isFinite(run.duration)) {
                          detailParts.push(`${run.duration.toFixed(1)} sn`)
                        }
                        if (run.triggered_by) {
                          detailParts.push(`Tetikleyen: ${run.triggered_by}`)
                        }
                        const detailText = detailParts.join(' • ')

                        return (
                          <li key={run.id} className={`rounded-md p-3 ${statusInfo.containerClass}`}>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <RunStatusIcon className={`h-4 w-4 ${statusInfo.textClass}`} />
                                <span
                                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${statusInfo.chipClass}`}
                                >
                                  {statusInfo.label}
                                </span>
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {runRelative ? runRelative : 'Zaman bilinmiyor'}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">{runDateLabel}</p>
                            {detailText ? (
                              <p className="mt-1 text-xs text-muted-foreground">{detailText}</p>
                            ) : null}
                          </li>
                        )
                      })}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Son {summaryWindowDays} gün içinde kayıtlı otomasyon koşusu bulunamadı.
                    </p>
                  )}
                </div>

                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Günlük dağılım</p>
                  {recentBuckets.length ? (
                    <ul className="mt-2 space-y-2">
                      {recentBuckets.map((bucket) => {
                        const bucketDate = new Date(`${bucket.date}T00:00:00Z`)
                        const formattedDate = bucketDate.toLocaleDateString('tr-TR', {
                          day: '2-digit',
                          month: '2-digit'
                        })
                        const bucketSuccess = bucket.total > 0 ? Math.round((bucket.passed / bucket.total) * 100) : 0
                        const bucketAccent =
                          bucket.total === 0
                            ? 'text-muted-foreground'
                            : bucketSuccess >= 90
                              ? 'text-emerald-600'
                              : bucketSuccess >= 70
                                ? 'text-amber-600'
                                : 'text-rose-600'
                        return (
                          <li key={bucket.date} className="rounded-md border border-border/60 bg-card/40 p-3">
                            <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
                              <span>{formattedDate}</span>
                              <span className={bucketAccent}>
                                {bucket.passed}/{bucket.total} • %{bucketSuccess}
                              </span>
                            </div>
                            <Progress value={bucketSuccess} className="mt-2 h-1.5" />
                          </li>
                        )
                      })}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-muted-foreground">Günlük dağılım verisi bulunmuyor.</p>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card id="rate-limits" className={rateLimit429Rate >= 5 ? 'border-destructive/40 bg-destructive/5' : ''}>
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

        <Card id="automation-tests" className="lg:col-span-2">
          <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                Otomasyon Testleri
              </CardTitle>
              <CardDescription>
                Preflight, smoke test ve stres test sonuçları
                <span className="mt-1 block text-xs text-muted-foreground">
                  Kısayol: Ctrl+Alt+C
                </span>
              </CardDescription>
            </div>
            <Button
              onClick={onRunChecks}
              disabled={isRunningChecks}
              variant="outline"
              title="Kısayol: Ctrl+Alt+C"
              aria-label="Otomasyon testlerini çalıştır (Ctrl+Alt+C)"
            >
              {isRunningChecks ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FlaskConical className="mr-2 h-4 w-4" />
              )}
              {isRunningChecks ? 'Testler çalışıyor…' : 'Testleri çalıştır'}
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {systemCheck ? (
              <>
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-sm font-medium">Son durum</p>
                    <p className="text-xs text-muted-foreground">
                      {formattedCheckTime ? `Tarih: ${formattedCheckTime}` : null}
                      {systemCheck?.triggered_by ? ` • Tetikleyen: ${systemCheck.triggered_by}` : ''}
                      {systemCheck?.duration ? ` • ${systemCheck.duration.toFixed(1)} sn` : ''}
                    </p>
                  </div>
                  <Badge variant="outline" className={statusBadgeClass}>
                    {statusLabel}
                  </Badge>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="text-xs text-muted-foreground">Toplam adım</p>
                    <p className="text-lg font-semibold">{systemCheck.total_steps}</p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="text-xs text-muted-foreground">Başarılı</p>
                    <p className="text-lg font-semibold text-emerald-600">{systemCheck.passed_steps}</p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="text-xs text-muted-foreground">Hata</p>
                    <p className="text-lg font-semibold text-rose-600">{systemCheck.failed_steps}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  {systemCheck.steps?.map((step) => {
                    const summary = summarizeStep(step.stdout) || summarizeStep(step.stderr)
                    return (
                      <div key={step.name} className="rounded-lg border border-border/60 bg-card/50 p-3">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-center gap-2">
                            {step.success ? (
                              <CheckCircle className="h-4 w-4 text-emerald-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-rose-600" />
                            )}
                            <div>
                              <p className="text-sm font-medium capitalize">{step.name.replace('-', ' ')}</p>
                              {summary ? (
                                <p className="text-xs text-muted-foreground break-words">{summary}</p>
                              ) : null}
                            </div>
                          </div>
                          <span className="text-xs text-muted-foreground">{step.duration?.toFixed?.(1) ?? '0.0'} sn</span>
                        </div>
                        {!summary && (step.stderr || step.stdout) ? (
                          <p className={`mt-2 text-xs ${step.success ? 'text-muted-foreground' : 'text-rose-600'} break-words`}>
                            {(step.stderr || step.stdout)?.trim()?.slice(0, 160)}
                          </p>
                        ) : null}
                      </div>
                    )
                  })}
                </div>

                {systemCheck.health_checks?.length ? (
                  <div className="space-y-2">
                    <p className="text-sm font-medium flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-primary" />
                      Servis Sağlık Durumu
                    </p>
                    <div className="grid gap-2 md:grid-cols-2">
                      {systemCheck.health_checks.map((hc) => {
                        const isHealthy = hc.status === 'healthy'
                        const isSkipped = hc.status === 'skipped'
                        const accent = isHealthy
                          ? 'text-emerald-600'
                          : isSkipped
                            ? 'text-amber-600'
                            : 'text-rose-600'
                        const Icon = isHealthy ? CheckCircle : isSkipped ? AlertTriangle : XCircle
                        const statusLabel = isSkipped ? 'Atlandı' : isHealthy ? 'Sağlıklı' : 'Sorun'
                        return (
                          <div
                            key={hc.name}
                            className="flex items-start gap-3 rounded-lg border border-border/60 bg-card/40 p-3"
                          >
                            <Icon className={`mt-0.5 h-4 w-4 ${accent}`} />
                            <div>
                              <p className="text-sm font-medium capitalize">{hc.name}</p>
                              <p className={`text-xs ${accent}`}>
                                {statusLabel}
                                {hc.detail ? ` • ${hc.detail}` : ''}
                              </p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="flex items-center justify-between rounded-lg border border-dashed border-border p-4">
                <div>
                  <p className="text-sm font-medium">Henüz test kaydı yok</p>
                  <p className="text-xs text-muted-foreground">
                    Testleri çalıştırarak preflight ve stres testinin son durumunu burada görüntüleyebilirsiniz.
                  </p>
                </div>
                <ShieldCheck className="h-10 w-10 text-muted-foreground/60" />
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

