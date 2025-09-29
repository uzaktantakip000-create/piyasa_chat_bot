import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom'
import { Sidebar } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  LifeBuoy
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

function App() {
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
  const [authenticating, setAuthenticating] = useState(false)
  const [authError, setAuthError] = useState('')

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

  const persistSessionFlag = (enabled) => {
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
  }

  const logout = (message = '') => {
    clearApiKey()
    persistSessionFlag(false)
    setIsAuthenticated(false)
    setSimulationActive(false)
    setAuthError(message || '')
  }

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

  // Fetch metrics
  const fetchMetrics = async () => {
    try {
      if (!isAuthenticated) {
        return
      }
      const response = await apiFetch('/metrics')
      const data = await response.json()
      setMetrics(data)
      setSimulationActive(data.simulation_active)
    } catch (error) {
      console.error('Failed to fetch metrics:', error)
      if (error?.message?.includes('401') || !getApiKey()) {
        logout('Oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.')
      }
    }
  }

  // Control simulation
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
    } catch (error) {
      console.error('Failed to toggle simulation:', error)
      if (error?.message?.includes('401') || !getApiKey()) {
        logout('Oturumunuz sonlandırıldı. Lütfen tekrar giriş yapın.')
      }
    }
  }

  useEffect(() => {
    if (!isAuthenticated) {
      return undefined
    }
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 5000) // Update every 5 seconds
    return () => clearInterval(interval)
  }, [isAuthenticated])

  const sidebarItems = [
    {
      title: "Dashboard",
      url: "/",
      icon: BarChart3,
    },
    {
      title: "Kurulum (Wizard)",
      url: "/wizard",
      icon: Wand2,
    },
    {
      title: "Botlar",
      url: "/bots",
      icon: Bot,
    },
    {
      title: "Sohbetler",
      url: "/chats",
      icon: MessageSquare,
    },
    {
      title: "Ayarlar",
      url: "/settings",
      icon: Settings,
    },
    {
      title: "Loglar",
      url: "/logs",
      icon: FileText,
    },
    {
      title: "Yardım",
      url: "/help",
      icon: LifeBuoy,
    },
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
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h1 className="text-2xl font-bold">Telegram Piyasa Simülasyonu</h1>
                <Badge variant={simulationActive ? "default" : "secondary"}>
                  {simulationActive ? "Aktif" : "Durduruldu"}
                </Badge>
              </div>
              
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Users className="h-4 w-4" />
                  <span>{metrics.active_bots}/{metrics.total_bots} Bot</span>
                </div>
                
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <TrendingUp className="h-4 w-4" />
                  <span>{metrics.messages_per_minute.toFixed(1)} msg/dk</span>
                </div>
                
                <Button
                  onClick={toggleSimulation}
                  variant={simulationActive ? "destructive" : "default"}
                  size="sm"
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

          {/* Page Content */}
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route path="/" element={<Dashboard metrics={metrics} />} />
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

export default App
