import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { BookOpen, ClipboardCheck, LifeBuoy, PlayCircle, Rocket, TestTube, Zap, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { apiFetch } from './apiClient'

function CommandRow({ label, command }) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  const copyToClipboard = async () => {
    setError('')
    if (typeof navigator === 'undefined' || !navigator?.clipboard?.writeText) {
      setError('Kopyalayamadım. Komutu elle seçip kopyalayın.')
      return
    }

    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Kopyalama başarısız oldu:', err)
      setError('Kopyalama başarısız. Lütfen komutu elle kopyalayın.')
    }
  }

  return (
    <div className="mb-3 space-y-1">
      <div className="flex items-center justify-between gap-3">
        <code className="flex-1 rounded bg-muted px-3 py-2 text-sm">{command}</code>
        <Button onClick={copyToClipboard} size="sm" variant="secondary">
          {copied ? 'Kopyalandı!' : label}
        </Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

function SectionCard({ icon: Icon, title, description, actionLabel, onAction }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-primary" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={onAction} className="w-full">
          {actionLabel}
        </Button>
      </CardContent>
    </Card>
  )
}

export default function QuickStart() {
  const navigate = useNavigate()
  const [dialogKey, setDialogKey] = useState(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [loadingAction, setLoadingAction] = useState('')
  const [statusMessage, setStatusMessage] = useState(null)
  const [metrics, setMetrics] = useState({
    simulation_active: false,
    total_bots: 0,
    total_chats: 0,
    messages_per_minute: 0,
    scale_factor: 1
  })

  const openDialog = (key) => {
    setDialogKey(key)
    setDialogOpen(true)
  }

  const closeDialog = () => {
    setDialogOpen(false)
    setDialogKey(null)
  }

  const refreshMetrics = async () => {
    try {
      const response = await apiFetch('/metrics')
      const data = await response.json()
      setMetrics({
        simulation_active: Boolean(data.simulation_active),
        total_bots: data.total_bots || 0,
        total_chats: data.total_chats || 0,
        messages_per_minute: data.messages_per_minute || 0,
        scale_factor: data.scale_factor || 1
      })
    } catch (error) {
      console.error('Metrikler alınamadı:', error)
      setStatusMessage({ type: 'error', text: 'Metrikler alınamadı. API anahtarınızı kontrol edin.' })
    }
  }

  useEffect(() => {
    refreshMetrics()
  }, [])

  const runSimulationAction = async (action) => {
    setLoadingAction(action)
    setStatusMessage(null)
    try {
      const endpoint = action === 'start' ? '/control/start' : '/control/stop'
      await apiFetch(endpoint, { method: 'POST' })
      await refreshMetrics()
      setStatusMessage({
        type: 'success',
        text: action === 'start' ? 'Simülasyon başlatıldı.' : 'Simülasyon durduruldu.'
      })
    } catch (error) {
      console.error('Simülasyon eylemi başarısız oldu:', error)
      setStatusMessage({ type: 'error', text: error.message || 'İşlem başarısız oldu.' })
    } finally {
      setLoadingAction('')
    }
  }

  const sections = useMemo(
    () => [
      {
        key: 'setup',
        icon: Rocket,
        title: 'Kuruluma Başla',
        description: 'Hangi sistemi kullanırsan kullan, kurulum adımlarını tek ekranda gör.',
        actionLabel: 'Kurulum rehberini aç',
        content: (
          <div className="space-y-4 text-sm text-muted-foreground">
            <p>
              <strong>Windows:</strong> Klasördeki <code>setup_all.cmd</code> dosyasına çift tıkla. Betik senden OpenAI anahtarını ve isteğe
              bağlı Redis/PostgreSQL adreslerini ister; ardından API, worker ve paneli ayrı pencerelerde açar.
            </p>
            <p>
              <strong>macOS / Linux:</strong> Terminalde proje klasörüne geçip aşağıdaki komutları sırasıyla çalıştır.
            </p>
            <CommandRow label="Kopyala" command="python3 -m venv .venv && source .venv/bin/activate" />
            <CommandRow label="Kopyala" command="pip install -r requirements.txt" />
            <CommandRow label="Kopyala" command="npm install" />
            <CommandRow label="Kopyala" command="cp .env.example .env" />
            <p>
              <strong>.env dosyası:</strong> <code>API_KEY</code> ve <code>VITE_API_KEY</code> için aynı güçlü şifreyi yaz,{' '}
              <code>TOKEN_ENCRYPTION_KEY</code> satırındaki komutu çalıştırarak yeni anahtar üret, OpenAI hesabından aldığın anahtarı
              <code>OPENAI_API_KEY</code> satırına ekle.
            </p>
            <p>
              <strong>Servisleri başlat:</strong>
            </p>
            <CommandRow label="Kopyala" command="uvicorn main:app --reload" />
            <CommandRow label="Kopyala" command="python worker.py" />
            <CommandRow label="Kopyala" command="npm run dev" />
          </div>
        )
      },
      {
        key: 'tests',
        icon: TestTube,
        title: 'Sistemi Test Et',
        description: 'Kurulumdan sonra her şeyin çalıştığını iki komutla doğrula.',
        actionLabel: 'Test komutlarını göster',
        content: (
          <div className="space-y-4 text-sm text-muted-foreground">
            <p>
              <strong>1. Otomatik testler:</strong> Tüm bot ve sohbet akışlarının çalıştığını görmek için <code>pytest</code> komutunu çalıştır.
            </p>
            <CommandRow label="Kopyala" command="pytest" />
            <p>
              <strong>2. Sağlık kontrolü:</strong> API, veritabanı, OpenAI ve Telegram bağlantısını doğrulamak için <code>python preflight.py</code>
              komutunu kullan.
            </p>
            <CommandRow label="Kopyala" command="python preflight.py" />
            <p>
              Bir komut hata verirse mesajı aynen not et; paneldeki Loglar sekmesiyle aynı hatayı takip edebilirsin.
            </p>
          </div>
        )
      },
      {
        key: 'usage',
        icon: BookOpen,
        title: 'Günlük Kullanım',
        description: 'Paneldeki temel adımlar: bot ekle, sohbet seç, simülasyonu yönet.',
        actionLabel: 'Adımları gör',
        content: (
          <div className="space-y-4 text-sm text-muted-foreground">
            <p>
              <strong>1. Giriş yap:</strong> Panel girişinde <code>API_KEY</code> değerini yaz, panel şifresi belirlediysen onu da ekle.
            </p>
            <p>
              <strong>2. Kurulum Sihirbazı:</strong> Wizard ekranında bot adı, token, chat ID ve istersen persona/tutum bilgilerini girip "Kurulumu
              bitir" tuşuna bas.
            </p>
            <p>
              <strong>3. Simülasyonu yönet:</strong> Hızlı başlat/durdur butonunu kullanarak sohbet üretimini kontrol et. Ölçeği değiştirmek için Wizard’daki
              "Hız / Ölçek" bölümünden faktörü güncelle.
            </p>
            <p>
              <strong>4. Durumu izle:</strong> Dashboard kartları bot sayısı, mesaj hızı ve hata oranlarını gösterir. Loglar sekmesinden
              olası uyarıları takip edebilirsin.
            </p>
          </div>
        )
      }
    ],
    []
  )

  const activeSection = sections.find((section) => section.key === dialogKey)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <LifeBuoy className="h-6 w-6 text-primary" />
            Hızlı Yardım Merkezi
          </h1>
          <p className="text-muted-foreground text-sm">
            Kurulum, test ve günlük kullanım için tek tuşluk rehberler. Her karttaki butona basarak ayrıntıları hemen gör.
          </p>
        </div>
        <Badge variant={metrics.simulation_active ? 'default' : 'secondary'}>
          Simülasyon {metrics.simulation_active ? 'Aktif' : 'Kapalı'}
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5" />
            Hızlı Eylemler
          </CardTitle>
          <CardDescription>Tek tıkla simülasyonu kontrol et ve önemli ekranlara geç.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Button
              onClick={() => runSimulationAction(metrics.simulation_active ? 'stop' : 'start')}
              disabled={loadingAction !== ''}
              className="flex items-center justify-center gap-2"
            >
              {loadingAction ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : metrics.simulation_active ? (
                <>
                  <Zap className="h-4 w-4" />
                  Simülasyonu Durdur
                </>
              ) : (
                <>
                  <PlayCircle className="h-4 w-4" />
                  Simülasyonu Başlat
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                navigate('/wizard')
              }}
            >
              <Rocket className="mr-2 h-4 w-4" /> Kurulum Sihirbazına Git
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                navigate('/logs')
              }}
            >
              <BookOpen className="mr-2 h-4 w-4" /> Logları Aç
            </Button>
            <Button variant="secondary" onClick={refreshMetrics} disabled={loadingAction !== ''}>
              Durumu Güncelle
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 text-sm text-muted-foreground">
            <div className="rounded border border-border p-3">
              <span className="block text-xs uppercase text-muted-foreground">Bot Sayısı</span>
              <span className="text-lg font-semibold">{metrics.total_bots}</span>
            </div>
            <div className="rounded border border-border p-3">
              <span className="block text-xs uppercase text-muted-foreground">Sohbet Sayısı</span>
              <span className="text-lg font-semibold">{metrics.total_chats}</span>
            </div>
            <div className="rounded border border-border p-3">
              <span className="block text-xs uppercase text-muted-foreground">Mesaj Hızı</span>
              <span className="text-lg font-semibold">{metrics.messages_per_minute.toFixed(1)} msg/dk</span>
            </div>
          </div>

          {statusMessage && (
            <div
              className={`rounded-md border p-3 text-sm ${
                statusMessage.type === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-destructive/40 bg-destructive/10 text-destructive'
              }`}
            >
              {statusMessage.text}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {sections.map((section) => (
          <SectionCard
            key={section.key}
            icon={section.icon}
            title={section.title}
            description={section.description}
            actionLabel={section.actionLabel}
            onAction={() => openDialog(section.key)}
          />
        ))}
      </div>

      <Dialog open={dialogOpen} onOpenChange={(open) => (open ? setDialogOpen(true) : closeDialog())}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{activeSection?.title}</DialogTitle>
            <DialogDescription>{activeSection?.description}</DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto pt-2 text-sm leading-relaxed text-muted-foreground">
            {activeSection?.content}
          </div>
          <DialogFooter>
            <Button onClick={closeDialog} variant="secondary">
              Kapat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
