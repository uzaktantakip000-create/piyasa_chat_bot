import { useState, useEffect, useMemo, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom'
import { Sidebar } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Activity,
  Bot,
  MessageSquare,
  Settings,
  FileText,
  Play,
  Pause,
  BarChart3,
  Users,
  TrendingUp,
  Wand2,
  LifeBuoy,
  Clock,
  RotateCw,
  Loader2,
  BellRing
} from 'lucide-react'
import Dashboard from './Dashboard'
import Bots from './Bots'
import Chats from './Chats'
import SettingsPage from './Settings'
import Logs from './Logs'
import Wizard from './components/Wizard'
import QuickStart from './QuickStart'
import { apiFetch, getStoredApiKey, setStoredApiKey, isApiError } from './apiClient'
import './App.css'
import LoginPanel from './components/LoginPanel'
import InlineNotice from './components/InlineNotice'
import { ToastProvider, useToast } from './components/ToastProvider'
import { ThemeProvider } from './components/ThemeProvider'
import ActivityCenter from './components/ActivityCenter'

function AppShell() {
  const toastApi = useToast()
  const showToast = toastApi.showToast
  const toastHistory = toastApi.history ?? []
  const clearToastHistory = toastApi.clearHistory ?? (() => {})
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [simulationActive, setSimulationActive] = useState(false)
  const [metrics, setMetrics] = useState({
    total_bots: 0,
    active_bots: 0,
    total_chats: 0,
    messages_last_hour: 0,
    messages_per_minute: 0,
    simulation_active: false,
    scale_factor: 1.0,
    rate_limit_hits: 0,
    telegram_429_count: 0
  })
  const [systemCheck, setSystemCheck] = useState(null)
  const [systemSummary, setSystemSummary] = useState(null)
  const [authenticating, setAuthenticating] = useState(false)
  const [authError, setAuthError] = useState('')
  const [globalStatus, setGlobalStatus] = useState(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null)
  const [metricsPhase, setMetricsPhase] = useState('idle')
  const [firstMetricsLoaded, setFirstMetricsLoaded] = useState(false)
  const [manualRefreshing, setManualRefreshing] = useState(false)
  const [checksPhase, setChecksPhase] = useState('idle')
  const [activityFeed, setActivityFeed] = useState([])
  const [activityCenterOpen, setActivityCenterOpen] = useState(false)
  const [activitySeenAt, setActivitySeenAt] = useState(() => Date.now())

  const pushActivity = useCallback((event) => {
    setActivityFeed((current) => {
      const entry = {
        id: event?.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        title: event?.title ?? 'Olay',
        description: event?.description ?? '',
        severity: event?.severity ?? 'info',
        source: event?.source ?? 'sistem',
        timestamp: event?.timestamp ?? new Date().toISOString(),
        meta: event?.meta ?? {}
      }
      const next = [entry, ...current]
      return next.slice(0, 80)
    })
  }, [])

  const clearActivityFeed = useCallback(() => {
    setActivityFeed([])
  }, [])

  const unreadCount = useMemo(() => {
    return activityFeed.filter((event) => {
      if (!event?.timestamp) {
        return false
      }
      const ts = new Date(event.timestamp).getTime()
      return Number.isFinite(ts) && ts > activitySeenAt
    }).length
  }, [activityFeed, activitySeenAt])

  const handleOpenActivityCenter = useCallback(() => {
    setActivityCenterOpen(true)
    setActivitySeenAt(Date.now())
  }, [])

  const handleCloseActivityCenter = useCallback(() => {
    setActivityCenterOpen(false)
    setActivitySeenAt(Date.now())
  }, [])


  const safeMessagesPerMinute = useMemo(() => {
    const value = Number(metrics?.messages_per_minute ?? 0)
    return Number.isFinite(value) ? value : 0
  }, [metrics])

  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [sessionMeta, setSessionMeta] = useState(() => {
    const storedKey = getStoredApiKey()
    return storedKey ? { apiKey: storedKey } : null
  })

  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      try {
        const response = await apiFetch('/auth/me')
        const data = await response.json()
        if (cancelled) {
          return
        }
        setIsAuthenticated(true)
        setSessionMeta((prev) => ({
          ...(prev || {}),
          username: data.username,
          role: data.role,
          apiKeyLastRotated: data.api_key_last_rotated
        }))
      } catch (error) {
        if (cancelled) {
          return
        }
        if (!error?.message?.includes('401')) {
          console.warn('Oturum doğrulaması alınamadı:', error)
        }
        setIsAuthenticated(false)
        setSessionMeta((prev) => (prev?.apiKey ? { apiKey: prev.apiKey } : null))
      }
    }

    bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const logout = useCallback((message = '') => {
    apiFetch('/auth/logout', { method: 'POST' }).catch((error) => {
      console.warn('Oturum kapatma isteği başarısız:', error)
    })
    setStoredApiKey(null)
    setSessionMeta(null)
    setIsAuthenticated(false)
    setSimulationActive(false)
    setAuthError(message || '')
    setGlobalStatus(null)
    setLastUpdatedAt(null)
    setMetricsPhase('idle')
    setFirstMetricsLoaded(false)
    setSystemCheck(null)
    setSystemSummary(null)
    setChecksPhase('idle')
    pushActivity({
      severity: message ? 'warning' : 'info',
      title: 'Oturum kapatıldı',
      description: message || 'Kullanıcı isteğiyle çıkış yapıldı.',
      source: 'auth',
      meta: { manual: !message }
    })
  }, [pushActivity])

  const handleLogin = async ({ username, password, totp }) => {
    setAuthError('')
    if (!username || !password) {
      setAuthError('Kullanıcı adı ve parola gereklidir.')
      return
    }

    setAuthenticating(true)
    try {
      const response = await apiFetch('/auth/login', {
        method: 'POST',
        body: {
          username: username.trim(),
          password: password.trim(),
          totp: totp?.trim() || undefined
        }
      })
      const data = await response.json()
      setStoredApiKey(data.api_key)
      setSessionMeta({
        apiKey: data.api_key,
        role: data.role,
        sessionExpiresAt: data.session_expires_at
      })
      setIsAuthenticated(true)
      try {
        const meResponse = await apiFetch('/auth/me')
        const me = await meResponse.json()
        setSessionMeta((prev) => ({
          ...(prev || {}),
          username: me.username,
          role: me.role,
          apiKeyLastRotated: me.api_key_last_rotated
        }))
      } catch (infoError) {
        console.warn('Kullanıcı bilgileri alınamadı:', infoError)
      }
      pushActivity({
        severity: 'success',
        title: 'Giriş başarılı',
        description: `${username.trim()} oturumu açtı.`,
        source: 'auth',
        meta: { manual: true }
      })
    } catch (error) {
      setStoredApiKey(null)
      setSessionMeta(null)
      setIsAuthenticated(false)
      setAuthError(error?.message || 'Giriş başarısız oldu.')
      pushActivity({
        severity: 'error',
        title: 'Giriş başarısız',
        description: error?.message || 'Giriş sırasında beklenmeyen bir hata oluştu.',
        source: 'auth',
        meta: { manual: true }
      })
    } finally {
      setAuthenticating(false)
    }
  }

  const fetchSystemCheckData = useCallback(
    async () => {
      if (!isAuthenticated) {
        return
      }
      try {
        const [latestResult, summaryResult] = await Promise.allSettled([
          apiFetch('/system/checks/latest'),
          apiFetch('/system/checks/summary')
        ])

        if (latestResult.status === 'fulfilled') {
          const latestData = await latestResult.value.json()
          setSystemCheck(latestData)
        } else {
          setSystemCheck(null)
        }

        if (summaryResult.status === 'fulfilled') {
          const summaryData = await summaryResult.value.json()
          setSystemSummary(summaryData)
        } else {
          setSystemSummary(null)
        }
      } catch (error) {
        if ((isApiError(error) && error.status === 401) || error?.message?.includes('401')) {
          logout('Oturum doğrulaması başarısız oldu. Lütfen yeniden giriş yapın.')
        } else {
          console.warn('System check verileri alınamadı:', error)
        }
      }
    },
    [isAuthenticated, logout]
  )

  const fetchMetrics = useCallback(
    async ({ manual = false } = {}) => {
      try {
        if (!isAuthenticated) {
          return
        }

        if (!firstMetricsLoaded) {
          setMetricsPhase('loading')
        } else if (manual) {
          setMetricsPhase('manual')
          setManualRefreshing(true)
        } else {
          setMetricsPhase('refreshing')
        }

        const wasFirstLoad = !firstMetricsLoaded
        const response = await apiFetch('/metrics')
        const data = await response.json()
        setMetrics(data)
        setSimulationActive(data.simulation_active)
        setGlobalStatus(null)
        setLastUpdatedAt(new Date())
        if (!firstMetricsLoaded) {
          setFirstMetricsLoaded(true)
        }
        setMetricsPhase('ready')
        await fetchSystemCheckData()
        if (manual) {
          showToast({
            type: 'success',
            title: 'Dashboard yenilendi',
            description: 'Son metrikler başarıyla alındı.',
            source: 'metrics'
          })
          pushActivity({
            severity: 'success',
            title: 'Metrikler yenilendi',
            description: 'Manuel yenileme tamamlandı.',
            source: 'metrics',
            meta: { manual: true }
          })
        } else if (wasFirstLoad) {
          pushActivity({
            severity: 'info',
            title: 'Metrikler yüklendi',
            description: 'Dashboard başlangıç metrikleri alındı.',
            source: 'metrics'
          })
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error)
        setLastUpdatedAt(null)
        if ((isApiError(error) && error.status === 401) || error?.message?.includes('401') || !sessionMeta?.apiKey) {
          logout('Oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.')
          return
        }

        if (isApiError(error) && (error.code === 'offline' || error.code === 'network')) {
          setGlobalStatus((prev) =>
            prev?.code === 'offline'
              ? prev
              : {
                  type: 'warning',
                  message:
                    'İnternet bağlantısı kesilmiş görünüyor. Bağlantı geri geldiğinde veriler otomatik yenilenecek.',
                  code: 'offline',
                  actionLabel: 'Şimdi tekrar dene',
                  onAction: () => fetchMetrics({ manual: true })
                }
          )
          pushActivity({
            severity: 'warning',
            title: 'Ağ bağlantısı kesildi',
            description: 'Metrikler alınamadı. Bağlantı geri geldiğinde otomatik yenilenecek.',
            source: 'network',
            meta: { manual }
          })
        } else if (isApiError(error) && error.code === 'timeout') {
          setGlobalStatus({
            type: 'warning',
            message: 'API isteği zaman aşımına uğradı. Lütfen bağlantınızı kontrol ettikten sonra tekrar deneyin.',
            code: 'timeout',
            actionLabel: 'Tekrar dene',
            onAction: () => fetchMetrics({ manual: true })
          })
          pushActivity({
            severity: 'warning',
            title: 'Metrik isteği zaman aşımı',
            description: 'API isteği belirlenen sürede yanıt vermedi.',
            source: 'metrics',
            meta: { manual }
          })
        } else {
          setGlobalStatus({
            type: 'error',
            message:
              error?.message
                ? `Metrikler alınırken hata oluştu: ${error.message}`
                : 'Metrikler alınırken beklenmeyen bir hata oluştu.'
          })
          pushActivity({
            severity: 'error',
            title: 'Metrikler alınamadı',
            description: error?.message || 'Beklenmeyen bir hata oluştu.',
            source: 'metrics',
            meta: { manual }
          })
        }

        setMetricsPhase('error')
        if (manual) {
          showToast({
            type:
              isApiError(error) && (error.code === 'offline' || error.code === 'network' || error.code === 'timeout')
                ? 'warning'
                : 'error',
            title:
              isApiError(error) && error.code === 'timeout'
                ? 'İstek zaman aşımına uğradı'
                : isApiError(error) && (error.code === 'offline' || error.code === 'network')
                  ? 'Ağ bağlantısı yok'
                  : 'Yenileme başarısız',
            description:
              error?.message || 'Metrikler alınırken beklenmeyen bir hata oluştu.',
            source: 'metrics'
          })
        }
      } finally {
        if (manual) {
          setManualRefreshing(false)
        }
      }
    },
    [
      fetchSystemCheckData,
      firstMetricsLoaded,
      isAuthenticated,
      logout,
      sessionMeta?.apiKey,
      showToast,
      pushActivity
    ]
  )

  const handleRetryNow = useCallback(() => {
    fetchMetrics({ manual: true })
  }, [fetchMetrics])

  const toggleSimulation = async () => {
    try {
      if (!isAuthenticated) {
        return
      }
      const endpoint = simulationActive ? '/control/stop' : '/control/start'
      await apiFetch(endpoint, {
        method: 'POST'
      })

      setSimulationActive(!simulationActive)
      setTimeout(fetchMetrics, 1000)
      setGlobalStatus(null)
      const nextState = !simulationActive
      pushActivity({
        severity: nextState ? 'success' : 'warning',
        title: nextState ? 'Simülasyon başlatıldı' : 'Simülasyon durduruldu',
        description: nextState
          ? 'Botlar yeniden mesaj üretmeye başladı.'
          : 'Simülasyon isteğe bağlı olarak durduruldu.',
        source: 'control',
        meta: { manual: true }
      })
    } catch (error) {
      console.error('Failed to toggle simulation:', error)
      if ((isApiError(error) && error.status === 401) || error?.message?.includes('401') || !sessionMeta?.apiKey) {
        logout('Oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.')
        return
      }
      setGlobalStatus({
        type: 'error',
        message:
          error?.message
            ? `Simülasyon kontrol edilirken hata oluştu: ${error.message}`
            : 'Simülasyon kontrol edilirken beklenmeyen bir hata oluştu.'
      })
      pushActivity({
        severity: 'error',
        title: 'Simülasyon kontrol hatası',
        description: error?.message || 'Simülasyon komutu uygulanamadı.',
        source: 'control',
        meta: { manual: true }
      })
    }
  }

  const runSystemChecks = useCallback(
    async () => {
      if (!isAuthenticated || checksPhase === 'running') {
        return
      }
      setChecksPhase('running')
      try {
        const response = await apiFetch('/system/checks/run', { method: 'POST' })
        const data = await response.json()
        setSystemCheck(data)
        await fetchSystemCheckData()
        showToast({
          type: data.status === 'passed' ? 'success' : 'warning',
          title: 'Testler tamamlandı',
          description:
            data.status === 'passed'
              ? 'Tüm kontroller başarıyla geçti.'
              : 'Bazı adımlarda hata oluştu, detayları inceleyin.'
        })
        pushActivity({
          severity: data.status === 'passed' ? 'success' : 'warning',
          title: 'Otomasyon testleri tamamlandı',
          description:
            data.status === 'passed'
              ? 'Kontroller başarıyla tamamlandı.'
              : 'Bazı kontroller uyarı verdi, detayları inceleyin.',
          source: 'automation',
          meta: { manual: true, status: data.status }
        })
      } catch (error) {
        console.error('Testler çalıştırılırken hata:', error)
        if ((isApiError(error) && error.status === 401) || error?.message?.includes('401')) {
          logout('Oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.')
        } else {
          showToast({
            type: 'error',
            title: 'Testler başarısız',
            description: error?.message || 'Testler çalıştırılırken beklenmeyen bir hata oluştu.'
          })
          pushActivity({
            severity: 'error',
            title: 'Test çalıştırması başarısız',
            description: error?.message || 'Otomasyon testi beklenmeyen bir hata verdi.',
            source: 'automation',
            meta: { manual: true }
          })
        }
      } finally {
        setChecksPhase('idle')
      }
    },
    [checksPhase, fetchSystemCheckData, isAuthenticated, logout, showToast, pushActivity]
  )

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined
    }
    fetchMetrics()
    const interval = setInterval(() => {
      fetchMetrics()
    }, 5000)
    return () => clearInterval(interval)
  }, [fetchMetrics, isAuthenticated])

  const manualRefresh = () => {
    if (manualRefreshing) {
      return
    }
    fetchMetrics({ manual: true })
  }

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined
    }

    const handleOnline = () => {
      setGlobalStatus((prev) => (prev?.code === 'offline' ? null : prev))
      fetchMetrics()
      pushActivity({
        severity: 'success',
        title: 'Bağlantı geri geldi',
        description: 'Veriler otomatik olarak yenileniyor.',
        source: 'network'
      })
    }

    const handleOffline = () => {
      setGlobalStatus({
        type: 'warning',
        message: 'İnternet bağlantısı kesildi. Bağlantı geri geldiğinde veriler otomatik yenilenecek.',
        code: 'offline',
        actionLabel: 'Şimdi tekrar dene',
        onAction: handleRetryNow
      })
      pushActivity({
        severity: 'warning',
        title: 'İnternet bağlantısı kesildi',
        description: 'Dashboard çevrimdışı modda bekliyor.',
        source: 'network'
      })
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [fetchMetrics, handleRetryNow, isAuthenticated, pushActivity])

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined
    }

    const handleKeyDown = (event) => {
      if (event.defaultPrevented) {
        return
      }

      const target = event.target
      if (target) {
        const tagName = target.tagName ? target.tagName.toLowerCase() : ''
        if (['input', 'textarea', 'select'].includes(tagName) || target.isContentEditable) {
          return
        }
      }

      if (!(event.ctrlKey && event.altKey)) {
        return
      }

      const key = event.key.toLowerCase()
      if (key === 'r') {
        event.preventDefault()
        if (!manualRefreshing) {
          fetchMetrics({ manual: true })
        }
      } else if (key === 's') {
        event.preventDefault()
        toggleSimulation()
      } else if (key === 'c') {
        event.preventDefault()
        if (checksPhase !== 'running') {
          runSystemChecks()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    isAuthenticated,
    manualRefreshing,
    fetchMetrics,
    toggleSimulation,
    runSystemChecks,
    checksPhase
  ])

  const metricsStale = useMemo(() => {
    if (!firstMetricsLoaded || !lastUpdatedAt) {
      return false
    }
    return Date.now() - lastUpdatedAt.getTime() > 15000
  }, [firstMetricsLoaded, lastUpdatedAt])

  const isFetchingMetrics = metricsPhase === 'loading' || metricsPhase === 'refreshing' || metricsPhase === 'manual'

  const sidebarItems = [
    {
      title: 'Dashboard',
      url: '/',
      icon: BarChart3
    },
    {
      title: 'Kurulum (Wizard)',
      url: '/wizard',
      icon: Wand2
    },
    {
      title: 'Botlar',
      url: '/bots',
      icon: Bot
    },
    {
      title: 'Sohbetler',
      url: '/chats',
      icon: MessageSquare
    },
    {
      title: 'Ayarlar',
      url: '/settings',
      icon: Settings
    },
    {
      title: 'Loglar',
      url: '/logs',
      icon: FileText
    },
    {
      title: 'Yardım',
      url: '/help',
      icon: LifeBuoy
    }
  ]

  if (!isAuthenticated) {
    return (
      <LoginPanel
        onSubmit={handleLogin}
        submitting={authenticating}
        error={authError}
        defaultApiKey={sessionMeta?.apiKey || ''}
      />
    )
  }

  return (
    <Router>
      <div className="flex h-screen bg-background">
        {/* Sidebar */}
        <div className={`${sidebarOpen ? 'w-64' : 'w-16'} transition-all duration-300 border-r border-border`}>
          <div className="flex flex-col h-full">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Activity className="h-6 w-6 text-primary" />
                {sidebarOpen && (
                  <span className="font-semibold text-lg">Telegram Market Sim</span>
                )}
              </div>
            </div>

            <nav className="flex-1 p-4">
              <ul className="space-y-2">
                {sidebarItems.map((item) => (
                  <li key={item.url}>
                    <Link
                      to={item.url}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent hover:text-accent-foreground transition-colors"
                    >
                      <item.icon className="h-5 w-5" />
                      {sidebarOpen && <span>{item.title}</span>}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>

            <div className="p-4 border-t border-border">
              <Button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                variant="ghost"
                size="sm"
                className="w-full"
              >
                {sidebarOpen ? '←' : '→'}
              </Button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <header className="border-b border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <h1 className="text-2xl font-bold">Telegram Piyasa Simülasyonu</h1>
                <Badge variant={simulationActive ? 'default' : 'secondary'}>
                  {simulationActive ? 'Aktif' : 'Durduruldu'}
                </Badge>
              </div>

              <div className="flex flex-1 flex-wrap items-center justify-end gap-4">
                <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    {firstMetricsLoaded ? (
                      <span>{metrics.active_bots}/{metrics.total_bots} Bot</span>
                    ) : (
                      <span className="flex h-4 w-16 animate-pulse items-center rounded bg-muted/60" aria-hidden="true" />
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    {firstMetricsLoaded ? (
                      <span>{safeMessagesPerMinute.toFixed(1)} msg/dk</span>
                    ) : (
                      <span className="flex h-4 w-20 animate-pulse items-center rounded bg-muted/60" aria-hidden="true" />
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <span>
                      Son güncelleme{' '}
                      {lastUpdatedAt
                        ? lastUpdatedAt.toLocaleTimeString('tr-TR', {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                          })
                        : firstMetricsLoaded
                          ? '—'
                          : 'yükleniyor…'}
                    </span>
                    {isFetchingMetrics && (
                      <Badge variant="outline" className="flex items-center gap-1 text-xs">
                        <span className="relative flex h-2 w-2">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
                        </span>
                        Güncelleniyor
                      </Badge>
                    )}
                  </div>
                </div>

                {sessionMeta?.username && (
                  <div className="flex flex-col items-end text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">{sessionMeta.username}</span>
                    {sessionMeta?.role && <span className="text-xs uppercase tracking-wide">{sessionMeta.role}</span>}
                  </div>
                )}

                <div className="flex items-center gap-2 text-sm">
                  <Button
                    type="button"
                    onClick={handleOpenActivityCenter}
                    variant="ghost"
                    size="sm"
                    className="relative flex items-center gap-2"
                    aria-label="Etkinlik merkezini aç"
                  >
                    <BellRing className="h-4 w-4" />
                    <span className="hidden sm:inline">Etkinlikler</span>
                    {unreadCount > 0 ? (
                      <span className="absolute -right-2 -top-2 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary px-1 text-[11px] font-semibold text-primary-foreground">
                        {unreadCount > 99 ? '99+' : unreadCount}
                      </span>
                    ) : null}
                  </Button>

                  <Button
                    onClick={manualRefresh}
                    variant="outline"
                    size="sm"
                    disabled={manualRefreshing}
                    className="flex items-center gap-2"
                    title="Kısayol: Ctrl+Alt+R"
                    aria-label="Manuel yenile (Ctrl+Alt+R)"
                  >
                    {manualRefreshing ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RotateCw className="h-4 w-4" />
                    )}
                    Yenile
                  </Button>
                  <span className="hidden text-xs text-muted-foreground xl:inline">Ctrl+Alt+R</span>

                  <Button
                    onClick={toggleSimulation}
                    variant={simulationActive ? 'destructive' : 'default'}
                    size="sm"
                    title="Kısayol: Ctrl+Alt+S"
                    aria-label={
                      simulationActive
                        ? 'Simülasyonu durdur (Ctrl+Alt+S)'
                        : 'Simülasyonu başlat (Ctrl+Alt+S)'
                    }
                  >
                    {simulationActive ? (
                      <>
                        <Pause className="mr-2 h-4 w-4" />
                        Durdur
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Başlat
                      </>
                    )}
                  </Button>
                  <span className="hidden text-xs text-muted-foreground xl:inline">Ctrl+Alt+S</span>

                  <Button onClick={() => logout('')} variant="secondary" size="sm">
                    Çıkış
                  </Button>
                </div>
              </div>
            </div>
          </header>

          {(globalStatus?.message || metricsStale) && (
            <InlineNotice
              type={globalStatus?.type ?? 'warning'}
              message={
                globalStatus?.message ??
                'Veriler 15 saniyeden uzun süredir güncellenmedi. API bağlantınızı kontrol edin veya Yenile butonunu kullanın.'
              }
              className="mx-4 mt-4"
              actionLabel={globalStatus?.actionLabel}
              onAction={globalStatus?.onAction || (globalStatus?.code === 'offline' ? handleRetryNow : undefined)}
              actionVariant={globalStatus?.actionVariant}
              actionDisabled={
                globalStatus?.actionDisabled ?? (globalStatus?.code === 'offline' ? manualRefreshing : false)
              }
            />
          )}

          {/* Page Content */}
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route
                path="/"
                element={
                  <Dashboard
                    metrics={metrics}
                    lastUpdatedAt={lastUpdatedAt}
                    isLoading={!firstMetricsLoaded && metricsPhase === 'loading'}
                    isRefreshing={isFetchingMetrics}
                    systemCheck={systemCheck}
                    systemSummary={systemSummary}
                    onRunChecks={runSystemChecks}
                    isRunningChecks={checksPhase === 'running'}
                    sessionRole={sessionMeta?.role}
                    sessionMeta={sessionMeta}
                  />
                }
              />
              <Route path="/wizard" element={<Wizard onDone={fetchMetrics} />} />
              <Route path="/bots" element={<Bots />} />
              <Route path="/chats" element={<Chats />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/help" element={<QuickStart />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <ActivityCenter
            open={activityCenterOpen}
            onClose={handleCloseActivityCenter}
            events={activityFeed}
            onClearEvents={clearActivityFeed}
            toastHistory={toastHistory}
            onClearToastHistory={clearToastHistory}
          />
        </div>
      </div>
    </Router>
  )
}

function App() {
  return (
    <ToastProvider>
      <ThemeProvider>
        <AppShell />
      </ThemeProvider>
    </ToastProvider>
  )
}

export default App
