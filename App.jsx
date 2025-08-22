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
  Wand2
} from 'lucide-react'
import Dashboard from './components/Dashboard'
import Bots from './components/Bots'
import Chats from './components/Chats'
import SettingsPage from './components/Settings'
import Logs from './components/Logs'
import Wizard from './components/Wizard'
import './App.css'

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:8000'

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

  // Fetch metrics
  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/metrics`)
      if (response.ok) {
        const data = await response.json()
        setMetrics(data)
        setSimulationActive(data.simulation_active)
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error)
    }
  }

  // Control simulation
  const toggleSimulation = async () => {
    try {
      const endpoint = simulationActive ? '/control/stop' : '/control/start'
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST'
      })
      
      if (response.ok) {
        setSimulationActive(!simulationActive)
        // Refresh metrics after a short delay
        setTimeout(fetchMetrics, 1000)
      }
    } catch (error) {
      console.error('Failed to toggle simulation:', error)
    }
  }

  useEffect(() => {
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 5000) // Update every 5 seconds
    return () => clearInterval(interval)
  }, [])

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
  ]

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
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route path="/" element={<Dashboard metrics={metrics} />} />
              <Route path="/wizard" element={<Wizard apiBase={API_BASE_URL} onDone={fetchMetrics} />} />
              <Route path="/bots" element={<Bots />} />
              <Route path="/chats" element={<Chats />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  )
}

export default App
