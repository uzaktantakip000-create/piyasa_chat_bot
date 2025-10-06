import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
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
  Copy
} from 'lucide-react'

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

function Dashboard({
  metrics,
  lastUpdatedAt,
  isLoading = false,
  isRefreshing = false,
  systemCheck = null,
  systemSummary = null,
  onRunChecks = () => {},
  isRunningChecks = false
}) {
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

  const summaryStatus = systemSummary?.overall_status ?? (summaryRuns === 0 ? 'empty' : 'healthy')
  const summaryStatusInfo = summaryStatusMeta[summaryStatus] ?? summaryStatusMeta.empty
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

        <Card className="lg:col-span-2">
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

