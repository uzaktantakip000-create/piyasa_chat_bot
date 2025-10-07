import { useEffect, useMemo, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { BookOpen, ClipboardCheck, LifeBuoy, PlayCircle, Rocket, TestTube, Zap, Loader2, CheckCircle2, Circle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { apiFetch, getStoredApiKey } from './apiClient'
import InlineNotice from './components/InlineNotice'
import dashboardLogin from './docs/dashboard-login.svg'

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
      setTimeout(() => setCopied(false), 3000)
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
          {copied ? 'Tekrar Kopyala' : label}
        </Button>
      </div>
      <div className="min-h-[1.25rem]" aria-live="polite">
        {copied && !error && (
          <p className="flex items-center gap-1 text-xs text-emerald-600">
            <CheckCircle2 className="h-3 w-3" /> Panoya kopyalandı.
          </p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
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

const QUICKSTART_PROGRESS_BASE_KEY = 'piyasa.quickstart.progress'

const defaultProgressState = {
  overrides: {},
  lastDialog: null
}

function resolveProgressStorageKey() {
  const apiKey = typeof getStoredApiKey === 'function' ? getStoredApiKey() : null
  if (!apiKey) {
    return QUICKSTART_PROGRESS_BASE_KEY
  }

  try {
    const encoder = typeof btoa === 'function' ? btoa : null
    if (encoder) {
      const encoded = encoder(apiKey)
      const suffix = encoded.replace(/=+$/, '').slice(-12)
      return `${QUICKSTART_PROGRESS_BASE_KEY}.${suffix}`
    }
  } catch (error) {
    console.warn('QuickStart ilerleme anahtarı kodlanamadı:', error)
  }

  return `${QUICKSTART_PROGRESS_BASE_KEY}.${apiKey.slice(-12)}`
}

function loadProgressState(storageKey) {
  if (typeof window === 'undefined') {
    return { ...defaultProgressState }
  }

  try {
    const raw = window.localStorage?.getItem(storageKey)
    if (!raw) {
      return { ...defaultProgressState }
    }

    const parsed = JSON.parse(raw)
    return {
      overrides: parsed?.overrides && typeof parsed.overrides === 'object' ? parsed.overrides : {},
      lastDialog: parsed?.lastDialog || null
    }
  } catch (error) {
    console.warn('QuickStart ilerleme durumu okunamadı:', error)
    return { ...defaultProgressState }
  }
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
  const progressStorageKey = useMemo(() => resolveProgressStorageKey(), [])
  const [progressState, setProgressState] = useState(() => loadProgressState(progressStorageKey))

  const openDialog = useCallback((key) => {
    setDialogKey(key)
    setDialogOpen(true)
    setProgressState((prev) => ({ ...prev, lastDialog: key }))
  }, [])

  const closeDialog = useCallback(() => {
    setDialogOpen(false)
    setDialogKey(null)
  }, [])

  const toggleManualCompletion = useCallback((key, nextValue) => {
    setProgressState((prev) => {
      const nextOverrides = { ...(prev?.overrides || {}) }
      if (nextValue) {
        nextOverrides[key] = true
      } else {
        delete nextOverrides[key]
      }
      return { ...prev, overrides: nextOverrides }
    })
  }, [])

  const refreshMetrics = useCallback(async () => {
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
  }, [])

  useEffect(() => {
    refreshMetrics()
  }, [refreshMetrics])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      window.localStorage?.setItem(progressStorageKey, JSON.stringify(progressState))
    } catch (error) {
      console.warn('QuickStart ilerleme durumu kaydedilemedi:', error)
    }
  }, [progressStorageKey, progressState])

  const metricsCompletion = useMemo(
    () => ({
      bots: metrics.total_bots > 0,
      chats: metrics.total_chats > 0,
      simulation: metrics.simulation_active
    }),
    [metrics.total_bots, metrics.total_chats, metrics.simulation_active]
  )

  useEffect(() => {
    setProgressState((prev) => {
      const prevOverrides = prev?.overrides || {}
      let changed = false
      const nextOverrides = { ...prevOverrides }

      Object.entries(metricsCompletion).forEach(([key, done]) => {
        if (done && nextOverrides[key]) {
          delete nextOverrides[key]
          changed = true
        }
      })

      if (!changed) {
        return prev
      }

      return { ...prev, overrides: nextOverrides }
    })
  }, [metricsCompletion])

  const runSimulationAction = useCallback(
    async (action) => {
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
    },
    [refreshMetrics]
  )

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
            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => navigate('/settings')}>
                Ayarlar sayfasını aç
              </Button>
            </div>
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
            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => navigate('/logs')}>
                Logları Görüntüle
              </Button>
            </div>
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
            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => navigate('/bots')}>
                Bot listesine git
              </Button>
              <Button size="sm" variant="outline" onClick={() => navigate('/chats')}>
                Sohbet listesine git
              </Button>
            </div>
          </div>
        )
      },
      {
        key: 'support',
        icon: LifeBuoy,
        title: 'Sorun Giderme Akışı',
        description: 'Kurulumda takılırsan görsel rehber ve destek bağlantıları burada.',
        actionLabel: 'Destek adımlarını aç',
        content: (
          <div className="space-y-4 text-sm text-muted-foreground">
            <p>
              Kurulum veya giriş ekranında hata alırsan aşağıdaki akışı takip et. Her adımın yanında ilgili ekran
              görüntülerini ve kontrol etmen gereken ayarları bulacaksın.
            </p>
            <div className="rounded-lg border border-border/60 bg-card/40 p-3">
              <img
                src={dashboardLogin}
                alt="Dashboard giriş ekranı"
                className="w-full rounded-md border border-border/40"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Giriş formunda API anahtarı ve isteğe bağlı panel şifresinin doğru olduğundan emin ol.
              </p>
            </div>
            <ol className="list-decimal space-y-2 pl-5">
              <li>
                <strong>API anahtarı 401 döndürüyorsa:</strong> `.env` dosyasındaki <code>API_KEY</code> ve{' '}
                <code>VITE_API_KEY</code> değerlerinin eşleştiğini kontrol et.
              </li>
              <li>
                <strong>Panel yüklenmiyorsa:</strong> Terminalde <code>npm run dev</code> çıktısında hata var mı bak; gerekirse{' '}
                <code>npm install</code> komutunu tekrar çalıştır.
              </li>
              <li>
                <strong>Metrikler boşsa:</strong> `python preflight.py` ve <code>pytest</code> komutlarını çalıştırıp sonuçları
                Dashboard&apos;daki "Son test" kartıyla karşılaştır.
              </li>
            </ol>
            <InlineNotice
              type="info"
              message="Ek rehber için README içindeki 'Log ve alarm yönetimi' bölümünü ziyaret edebilir veya destek ekibine ulaşabilirsin."
              withSupportLinks
              supportHref="/help"
              supportLabel="QuickStart rehberini aç"
              contactHref="mailto:destek@piyasa-sim.dev"
              contactLabel="destek ekibine e-posta gönder"
            />
          </div>
        )
      }
    ],
    []
  )

  const checklistItems = useMemo(() => {
    const overrides = progressState?.overrides || {}

    const baseItems = [
      {
        key: 'bots',
        label: 'En az bir bot ekle',
        metricsComplete: metricsCompletion.bots,
        cta: 'Botlara Git',
        onAction: () => navigate('/bots'),
        disabled: false
      },
      {
        key: 'chats',
        label: 'Sohbet grubu bağla',
        metricsComplete: metricsCompletion.chats,
        cta: 'Sohbetlere Git',
        onAction: () => navigate('/chats'),
        disabled: false
      },
      {
        key: 'simulation',
        label: 'Simülasyonu başlat',
        metricsComplete: metricsCompletion.simulation,
        cta: metricsCompletion.simulation ? 'Simülasyon Açık' : 'Simülasyonu Başlat',
        onAction: () => runSimulationAction('start'),
        disabled: metricsCompletion.simulation || loadingAction !== ''
      }
    ]

    return baseItems.map((item) => {
      const overrideComplete = Boolean(overrides[item.key])
      return {
        ...item,
        overrideComplete,
        completed: item.metricsComplete || overrideComplete
      }
    })
  }, [
    metricsCompletion,
    navigate,
    runSimulationAction,
    loadingAction,
    progressState.overrides
  ])

  const nextStep = useMemo(() => {
    const pending = checklistItems.find((item) => !item.completed)
    if (!pending) {
      return null
    }
    return { key: pending.key, label: pending.label }
  }, [checklistItems])

  const handleResume = useCallback(() => {
    if (nextStep) {
      openDialog(nextStep.key)
    }
  }, [nextStep, openDialog])

  const completedSteps = checklistItems.filter((item) => item.completed).length
  const progressValue = Math.round((completedSteps / checklistItems.length) * 100)

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

      {nextStep && (
        <InlineNotice type="info" className="text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span>Kaldığınız yer: {nextStep.label}</span>
            <Button size="xs" variant="outline" onClick={handleResume}>
              Devam Et
            </Button>
          </div>
        </InlineNotice>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-primary" />
            Onboarding İlerlemesi
          </CardTitle>
          <CardDescription>
            {completedSteps} / {checklistItems.length} adım tamamlandı
            {nextStep ? (
              <span className="mt-1 block text-xs text-muted-foreground">
                Sıradaki önerilen adım: {nextStep.label}
              </span>
            ) : (
              <span className="mt-1 block text-xs text-emerald-600">Harika! Tüm adımlar tamamlandı.</span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
            <span>Kurulum ilerleme seviyesi</span>
            <Badge variant={progressValue === 100 ? 'default' : 'secondary'}>{progressValue}%</Badge>
          </div>
          <Progress value={progressValue} className="h-2" />
          <ul className="mt-4 space-y-3">
            {checklistItems.map((item) => (
              <li
                key={item.key}
                className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <div className="flex items-start gap-2 text-sm">
                  {item.completed ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground" />
                  )}
                  <div>
                    <span className={`block ${item.completed ? 'text-emerald-700' : 'text-foreground'}`}>
                      {item.label}
                    </span>
                    {item.overrideComplete && !item.metricsComplete ? (
                      <span className="text-[0.7rem] uppercase tracking-wide text-amber-600">
                        Manuel tamamlandı
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  {!item.completed && (
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={item.onAction}
                      disabled={item.disabled}
                    >
                      {item.cta}
                    </Button>
                  )}
                  {!item.metricsComplete && (
                    <Button
                      size="xs"
                      variant={item.overrideComplete ? 'secondary' : 'ghost'}
                      onClick={() => toggleManualCompletion(item.key, !item.overrideComplete)}
                    >
                      {item.overrideComplete ? 'İşareti kaldır' : 'Tamamlandı işaretle'}
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

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
            <InlineNotice
              type={statusMessage.type}
              message={statusMessage.text}
              className="text-sm"
            />
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
