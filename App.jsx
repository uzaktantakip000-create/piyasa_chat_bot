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
  Loader2
} from 'lucide-react'
import Dashboard from './Dashboard'
import Bots from './Bots'
import Chats from './Chats'
import SettingsPage from './Settings'
import Logs from './Logs'
import Wizard from './components/Wizard'
import QuickStart from './QuickStart'
import { apiFetch, getApiKey, setApiKey, clearApiKey } from './apiClient'
import './App.css'
import LoginPanel from './components/LoginPanel'
import InlineNotice from './components/InlineNotice'
import { ToastProvider, useToast } from './components/ToastProvider'

function AppShell() {
  const { showToast } = useToast()
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


  const safeMessagesPerMinute = useMemo(() => {
    const value = Number(metrics?.messages_per_minute ?? 0)
    return Number.isFinite(value) ? value : 0
  }, [metrics])

  const expectedPassword = import.meta.env?.VITE_DASHBOARD_PASSWORD || ''
  const SESSION_FLAG_KEY = 'piyasa.dashboard.session'
  const passwordRequired = Boolean(expectedPassword)

  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    const key = getApiKey()
    if (!key) {
      return false
    }
    if (!passwordRequired) {
      return true
    }
    try {
      return window.localStorage?.getItem(SESSION_FLAG_KEY) === 'true'
    } catch (error) {
      console.warn('Session anahtarı okunamadı:', error)
      return false
    }
  })

  const persistSessionFlag = useCallback(
    (enabled) => {
      if (!passwordRequired) {
        return
      }
      try {
        if (enabled) {
          window.localStorage?.setItem(SESSION_FLAG_KEY, 'true')
        } else {
          window.localStorage?.removeItem(SESSION_FLAG_KEY)
        }
      } catch (error) {
        console.warn('Session anahtarı güncellenemedi:', error)
      }
    },
    [passwordRequired]
  )

  const logout = useCallback(
    (message = '') => {
      clearApiKey()
      persistSessionFlag(false)
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
    },
    [persistSessionFlag]
  )

  const handleLogin = async ({ apiKey, password }) => {
    setAuthError('')
    if (!apiKey) {
      setAuthError('API anahtarı gerekli.')
      return
    }
    if (passwordRequired && password !== expectedPassword) {
      setAuthError('Geçersiz panel şifresi.')
      return
    }

    setAuthenticating(true)
    try {
      setApiKey(apiKey)
      await apiFetch('/healthz')
      persistSessionFlag(true)
      setIsAuthenticated(true)
    } catch (error) {
      logout(error?.message || 'API anahtarı doğrulanamadı.')
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
        console.warn('System check verileri alınamadı:', error)
      }
    },
    [isAuthenticated]
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
            description: 'Son metrikler başarıyla alındı.'
          })
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error)
        setLastUpdatedAt(null)
        if (error?.message?.includes('401') || !getApiKey()) {
          logout('Oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.')
          return
        }
        setGlobalStatus({
          type: 'error',
          message:
            error?.message
              ? `Metrikler alınırken hata oluştu: ${error.message}`
              : 'Metrikler alınırken beklenmeyen bir hata oluştu.'
        })
        setMetricsPhase('error')
        if (manual) {
          showToast({
            type: 'error',
            title: 'Yenileme başarısız',
            description: error?.message || 'Metrikler alınırken beklenmeyen bir hata oluştu.'
          })
        }
      } finally {
        if (manual) {
          setManualRefreshing(false)
        }
      }
    },
    [fetchSystemCheckData, firstMetricsLoaded, isAuthenticated, logout, showToast]
  )

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
    } catch (error) {
      console.error('Failed to toggle simulation:', error)
      if (error?.message?.includes('401') || !getApiKey()) {
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
      } catch (error) {
        console.error('Testler çalıştırılırken hata:', error)
        showToast({
          type: 'error',
          title: 'Testler başarısız',
          description: error?.message || 'Testler çalıştırılırken beklenmeyen bir hata oluştu.'
        })
      } finally {
        setChecksPhase('idle')
      }
    },
    [checksPhase, fetchSystemCheckData, isAuthenticated, showToast]
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
        requiresPassword={passwordRequired}
        defaultApiKey={getApiKey()}
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
                      <Pause className="h-4 w-4 mr-2" />
                      Durdur
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Başlat
                    </>
                  )}
                </Button>
                <span className="hidden text-xs text-muted-foreground xl:inline">Ctrl+Alt+S</span>
                <Button
                  onClick={() => logout('')}
                  variant="secondary"
                  size="sm"
                >
                  Çıkış
                </Button>
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
        </div>
      </div>
    </Router>
  )
}

function App() {
  return (
    <ToastProvider>
      <AppShell />
    </ToastProvider>
  )
}

export default App
