import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  Clock,
  MessageSquare,
  Zap,
  Palette,
  SunMedium,
  Moon,
  Contrast,
  Type,
  RefreshCcw
} from 'lucide-react'

import { apiFetch } from './apiClient'
import InlineNotice from './components/InlineNotice'
import { useThemePreferences } from './components/ThemeProvider'

const DEFAULT_MESSAGE_LENGTH_PROFILE = { short: 0.55, medium: 0.35, long: 0.10 }

function normalizeMessageLengthProfile(rawProfile) {
  const base = { ...DEFAULT_MESSAGE_LENGTH_PROFILE }
  if (rawProfile && typeof rawProfile === 'object') {
    Object.entries(rawProfile).forEach(([key, value]) => {
      if (!(key in base)) {
        return
      }
      const parsed = Number.parseFloat(value)
      if (Number.isFinite(parsed) && parsed >= 0) {
        base[key] = parsed
      }
    })
  }

  const total = Object.values(base).reduce((sum, val) => sum + val, 0)
  if (total <= 0) {
    return { ...DEFAULT_MESSAGE_LENGTH_PROFILE }
  }

  const normalized = Object.fromEntries(
    Object.entries(base).map(([key, val]) => [key, val / total])
  )
  const sumNormalized = Object.values(normalized).reduce((sum, val) => sum + val, 0)
  const residue = 1 - sumNormalized
  const keys = Object.keys(DEFAULT_MESSAGE_LENGTH_PROFILE)
  const lastKey = keys[keys.length - 1]
  normalized[lastKey] = Math.max(0, normalized[lastKey] + residue)
  return normalized
}

function Settings() {
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [newsFeedsText, setNewsFeedsText] = useState('')
  const {
    theme: uiTheme,
    contrast: uiContrast,
    fontScale,
    setTheme: setUiTheme,
    setContrast: setUiContrast,
    setFontScale: setUiFontScale,
    resetPreferences: resetThemePreferences
  } = useThemePreferences()

  // Fetch settings
  const fetchSettings = async () => {
    try {
      const response = await apiFetch('/settings')
      const data = await response.json()
      const settingsObj = {}
      let feedsValue = ''
      data.forEach(setting => {
        let nextValue = setting.value
        if (setting.key === 'message_length_profile' && setting.value?.value) {
          nextValue = { value: normalizeMessageLengthProfile(setting.value.value) }
        }
        settingsObj[setting.key] = nextValue
        if (setting.key === 'news_feed_urls') {
          const arr = Array.isArray(nextValue?.value) ? nextValue.value : []
          feedsValue = arr.join('\n')
        }
      })
      setSettings(settingsObj)
      setNewsFeedsText(feedsValue)
      setErrorMessage('')
      setSuccessMessage('')
    } catch (error) {
      console.error('Failed to fetch settings:', error)
      setErrorMessage(
        error?.message
          ? `Ayarlar yüklenirken hata oluştu: ${error.message}`
          : 'Ayarlar yüklenirken beklenmeyen bir hata oluştu.'
      )
      setSuccessMessage('')
    } finally {
      setLoading(false)
    }
  }

  // Update setting
  const updateSetting = async (key, value) => {
    try {
      setSaving(true)
      setErrorMessage('')
      setSuccessMessage('')
      let payload = value
      if (key === 'message_length_profile' && value?.value) {
        const normalized = normalizeMessageLengthProfile(value.value)
        payload = { value: normalized }
      }
      const response = await apiFetch(`/settings/${key}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })

      await response.json()
      setSettings(prev => ({
        ...prev,
        [key]: payload
      }))
      setSuccessMessage('Ayar başarıyla güncellendi.')
      return true
    } catch (error) {
      console.error('Failed to update setting:', error)
      setErrorMessage(
        error?.message
          ? `Ayar güncellenirken hata oluştu: ${error.message}`
          : 'Ayar güncellenirken beklenmeyen bir hata oluştu.'
      )
      setSuccessMessage('')
      return false
    } finally {
      setSaving(false)
    }
  }

  const handleNewsFeedsSave = async () => {
    const feeds = newsFeedsText
      .split(/\r?\n|,/)
      .map(item => item.trim())
      .filter(Boolean)
    const ok = await updateSetting('news_feed_urls', { value: feeds })
    if (ok) {
      setNewsFeedsText(feeds.join('\n'))
    }
  }

  // Scale simulation
  const scaleSimulation = async (factor) => {
    try {
      setErrorMessage('')
      setSuccessMessage('')
      await apiFetch(`/control/scale?factor=${factor}`, {
        method: 'POST'
      })
      setSuccessMessage('Simülasyon ölçeklendirme isteği gönderildi.')
    } catch (error) {
      console.error('Failed to scale simulation:', error)
      setErrorMessage(
        error?.message
          ? `Ölçek güncellenirken hata oluştu: ${error.message}`
          : 'Ölçek güncellenirken beklenmeyen bir hata oluştu.'
      )
      setSuccessMessage('')
    }
  }

  useEffect(() => {
    fetchSettings()
  }, [])

  const messageLengthProfile = settings.message_length_profile?.value || DEFAULT_MESSAGE_LENGTH_PROFILE
  const messageLengthTotal = Math.round(
    ((messageLengthProfile.short ?? 0) + (messageLengthProfile.medium ?? 0) + (messageLengthProfile.long ?? 0)) * 100
  )

  const handleMessageLengthChange = (field) => ([value]) => {
    const rawCurrent = settings.message_length_profile?.value || messageLengthProfile
    const normalizedCurrent = normalizeMessageLengthProfile(rawCurrent)
    const target = Math.min(1, Math.max(0, value / 100))
    const remainder = Math.max(0, 1 - target)
    const keys = Object.keys(DEFAULT_MESSAGE_LENGTH_PROFILE)
    const otherKeys = keys.filter(key => key !== field)
    const othersTotal = otherKeys.reduce((sum, key) => sum + (normalizedCurrent[key] ?? 0), 0)

    const next = { ...normalizedCurrent, [field]: target }
    if (otherKeys.length === 0) {
      updateSetting('message_length_profile', { value: next })
      return
    }

    if (othersTotal <= 0) {
      const share = remainder / otherKeys.length
      otherKeys.forEach(key => {
        next[key] = share
      })
    } else {
      otherKeys.forEach(key => {
        const weight = normalizedCurrent[key] ?? 0
        next[key] = remainder * (weight / othersTotal)
      })
    }

    updateSetting('message_length_profile', { value: next })
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64">Yükleniyor...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Ayarlar</h2>
        <p className="text-muted-foreground">
          Simülasyon davranışlarını ve parametrelerini yapılandırın
        </p>
      </div>

      <Tabs defaultValue="behavior" className="space-y-4">
        <TabsList>
          <TabsTrigger value="behavior">Davranış</TabsTrigger>
          <TabsTrigger value="timing">Zamanlama</TabsTrigger>
          <TabsTrigger value="performance">Performans</TabsTrigger>
          <TabsTrigger value="appearance">Görünüm</TabsTrigger>
        </TabsList>

        {/* Behavior Settings */}
        <TabsContent value="behavior" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Mesaj Davranışları
              </CardTitle>
              <CardDescription>
                Botların mesaj gönderme davranışlarını ayarlayın
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {(errorMessage || successMessage) && (
                <InlineNotice
                  type={errorMessage ? 'error' : 'success'}
                  message={errorMessage || successMessage}
                />
              )}
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>Reply Olasılığı (%{((settings.reply_probability?.value ?? 0.65) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.reply_probability?.value ?? 0.65) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('reply_probability', { value: value / 100 })
                    }
                    max={100}
                    step={5}
                    className="w-full"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Mention Olasılığı (%{((settings.mention_probability?.value ?? 0.35) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.mention_probability?.value ?? 0.35) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('mention_probability', { value: value / 100 })
                    }
                    max={100}
                    step={5}
                    className="w-full"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Kısa Tepki Olasılığı (%{((settings.short_reaction_probability?.value ?? 0.12) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.short_reaction_probability?.value ?? 0.12) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('short_reaction_probability', { value: value / 100 })
                    }
                    max={50}
                    step={2}
                    className="w-full"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Yeni Mesaj Olasılığı (%{((settings.new_message_probability?.value ?? 0.35) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.new_message_probability?.value ?? 0.35) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('new_message_probability', { value: value / 100 })
                    }
                    max={100}
                    step={5}
                    className="w-full"
                  />
                </div>
              </div>

              <div className="rounded-md bg-muted/40 p-3 text-sm text-muted-foreground">
                💡 Öneri: Reply olasılığını %50-%70, mention oranını %20-%40 aralığında tutmak Telegram spam filtreleri için
                güvenlidir. Kısa tepki ve yeni mesaj olasılıklarının toplamı %50’yi aşarsa botlar aynı anda çok sık mesaj
                gönderebilir.
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Mesaj Uzunluk Profili</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Kısa (%{((messageLengthProfile.short ?? 0.55) * 100).toFixed(0)})</Label>
                    <Slider
                      value={[(messageLengthProfile.short ?? 0.55) * 100]}
                      onValueChange={handleMessageLengthChange('short')}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Orta (%{((messageLengthProfile.medium ?? 0.35) * 100).toFixed(0)})</Label>
                    <Slider
                      value={[(messageLengthProfile.medium ?? 0.35) * 100]}
                      onValueChange={handleMessageLengthChange('medium')}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Uzun (%{((messageLengthProfile.long ?? 0.10) * 100).toFixed(0)})</Label>
                    <Slider
                      value={[(messageLengthProfile.long ?? 0.10) * 100]}
                      onValueChange={handleMessageLengthChange('long')}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  {`Toplam: %${messageLengthTotal}. Kaydırıcıları değiştirdiğinizde oranlar otomatik olarak %100’e normalize edilir; kısa mesaj ağırlığı yüksek olduğunda Telegram rate-limit’leri daha toleranslıdır.`}
                </p>
              </div>

              <div className="space-y-2">
                <Label>RSS Haber Kaynakları</Label>
                <p className="text-xs text-muted-foreground">
                  Her satıra bir RSS adresi yazabilir veya virgülle ayırabilirsiniz. Boş bırakılırsa varsayılan liste kullanılır.
                </p>
                <Textarea
                  value={newsFeedsText}
                  onChange={(e) => setNewsFeedsText(e.target.value)}
                  className="min-h-[120px]"
                  placeholder={'https://örnek.com/rss\nhttps://başka.com/feed'}
                />
                <div className="flex justify-end">
                  <Button onClick={handleNewsFeedsSave} disabled={saving}>
                    Kaydet
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Timing Settings */}
        <TabsContent value="timing" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Zamanlama Ayarları
              </CardTitle>
              <CardDescription>
                Mesaj gönderme zamanlaması ve hız ayarları
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {(errorMessage || successMessage) && (
                <InlineNotice
                  type={errorMessage ? 'error' : 'success'}
                  message={errorMessage || successMessage}
                />
              )}
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>Dakikada Maksimum Mesaj</Label>
                  <Input
                    type="number"
                    value={settings.max_msgs_per_min?.value ?? 6}
                    onChange={(e) => {
                      const parsed = Number.parseInt(e.target.value, 10)
                      if (Number.isNaN(parsed)) {
                        return
                      }
                      updateSetting('max_msgs_per_min', { value: parsed })
                    }}
                    min={1}
                    max={20}
                  />
                  <p className="text-xs text-muted-foreground">
                    6-8 aralığı doğal sohbet temposu sunar. 10+ değerleri Telegram limitlerine daha hızlı ulaşır.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>Typing Simülasyonu</Label>
                  <Switch
                    checked={settings.typing_enabled?.value ?? true}
                    onCheckedChange={(checked) =>
                      updateSetting('typing_enabled', { value: checked })
                    }
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={settings.prime_hours_boost?.value ?? true}
                    onCheckedChange={(checked) =>
                      updateSetting('prime_hours_boost', { value: checked })
                    }
                  />
                  <Label>Prime Hours Boost</Label>
                </div>
                
                <div className="space-y-2">
                  <Label>Prime Hours (virgülle ayırın)</Label>
                  <Input
                    value={(settings.prime_hours?.value ?? []).join(', ')}
                    onChange={(e) => {
                      const hours = e.target.value.split(',').map(h => h.trim()).filter(h => h)
                      updateSetting('prime_hours', { value: hours })
                    }}
                    placeholder="09:30-12:00, 14:00-18:00"
                  />
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Bot Saatlik Mesaj Limitleri</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Minimum</Label>
                    <Input
                      type="number"
                    value={settings.bot_hourly_msg_limit?.value?.min ?? 6}
                    onChange={(e) => {
                      const current = settings.bot_hourly_msg_limit?.value || {}
                      const parsed = Number.parseInt(e.target.value, 10)
                      if (Number.isNaN(parsed)) {
                        return
                      }
                      updateSetting('bot_hourly_msg_limit', {
                        value: { ...current, min: parsed }
                      })
                    }}
                    min={1}
                    max={50}
                  />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Maksimum</Label>
                    <Input
                      type="number"
                    value={settings.bot_hourly_msg_limit?.value?.max ?? 12}
                    onChange={(e) => {
                      const current = settings.bot_hourly_msg_limit?.value || {}
                      const parsed = Number.parseInt(e.target.value, 10)
                      if (Number.isNaN(parsed)) {
                        return
                      }
                      updateSetting('bot_hourly_msg_limit', {
                        value: { ...current, max: parsed }
                      })
                    }}
                    min={1}
                    max={50}
                  />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Performance Settings */}
        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                Performans Ayarları
              </CardTitle>
              <CardDescription>
                Simülasyon hızı ve ölçeklendirme ayarları
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {(errorMessage || successMessage) && (
                <InlineNotice
                  type={errorMessage ? 'error' : 'success'}
                  message={errorMessage || successMessage}
                />
              )}
              <div className="space-y-4">
                <h4 className="font-medium">Hız Ölçeklendirme</h4>
                <p className="text-sm text-muted-foreground">
                  Simülasyon hızını artırmak veya azaltmak için ölçek faktörünü ayarlayın.
                  1.0 = Normal hız, 2.0 = 2x hızlı, 0.5 = Yarı hız
                </p>
                
                <div className="flex items-center gap-4">
                  <Button
                    variant="outline"
                    onClick={() => scaleSimulation(0.5)}
                    disabled={saving}
                  >
                    0.5x
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => scaleSimulation(1.0)}
                    disabled={saving}
                  >
                    1.0x
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => scaleSimulation(1.5)}
                    disabled={saving}
                  >
                    1.5x
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => scaleSimulation(2.0)}
                    disabled={saving}
                  >
                    2.0x
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Typing Hızı (WPM)</h4>
                <p className="text-sm text-muted-foreground">
                  Ortalama kullanıcılar 2-6 WPM aralığında yazıyor. Daha yüksek değerler botların ani tepki vermesine neden
                  olup gerçekçilik algısını düşürebilir.
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Minimum WPM</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={settings.typing_speed_wpm?.value?.min ?? 2.5}
                      onChange={(e) => {
                        const parsed = Number.parseFloat(e.target.value)
                        if (Number.isNaN(parsed)) {
                          return
                        }
                        const clamped = Math.min(12, Math.max(0.5, parsed))
                        const current = settings.typing_speed_wpm?.value || {}
                        const next = { ...current, min: clamped }
                        if (typeof next.max === 'number' && next.max < clamped) {
                          next.max = clamped
                        }
                        updateSetting('typing_speed_wpm', { value: next })
                      }}
                      min={0.5}
                      max={12}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Maksimum WPM</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={settings.typing_speed_wpm?.value?.max ?? 4.5}
                      onChange={(e) => {
                        const parsed = Number.parseFloat(e.target.value)
                        if (Number.isNaN(parsed)) {
                          return
                        }
                        const clamped = Math.min(12, Math.max(0.5, parsed))
                        const current = settings.typing_speed_wpm?.value || {}
                        const next = { ...current, max: clamped }
                        if (typeof next.min === 'number' && next.min > clamped) {
                          next.min = clamped
                        }
                        updateSetting('typing_speed_wpm', { value: next })
                      }}
                      min={0.5}
                      max={12}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Önemli Notlar</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  ⚠️ Ayarları değiştirdikten sonra değişikliklerin etkili olması birkaç dakika sürebilir.
                </p>
              </div>
              
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  💡 Telegram rate limit'lerine takılmamak için mesaj hızını dikkatli ayarlayın.
                </p>
              </div>
              
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm text-green-800">
                  ✅ Tüm ayarlar gerçek zamanlı olarak worker'lara iletilir.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Palette className="h-5 w-5" />
                Tema ve Erişilebilirlik
              </CardTitle>
              <CardDescription>Kişiselleştirilmiş görünüm tercihlerini yapılandırın.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <p className="text-sm font-medium">Tema modu</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant={uiTheme === 'light' ? 'default' : 'outline'}
                    onClick={() => setUiTheme('light')}
                    className="flex items-center gap-2"
                  >
                    <SunMedium className="h-4 w-4" /> Aydınlık
                  </Button>
                  <Button
                    type="button"
                    variant={uiTheme === 'dark' ? 'default' : 'outline'}
                    onClick={() => setUiTheme('dark')}
                    className="flex items-center gap-2"
                  >
                    <Moon className="h-4 w-4" /> Karanlık
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Karanlık mod gece vardiyalarında göz yorgunluğunu azaltır; aydınlık mod ise gündüz kullanımlarında daha yüksek okunabilirlik sunar.
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border/70 bg-muted/30 p-4">
                <div>
                  <p className="text-sm font-medium">Yüksek kontrast</p>
                  <p className="text-xs text-muted-foreground">
                    Kontrastı artırarak metin ve ikonları daha belirgin hale getirir.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Contrast className="h-4 w-4 text-muted-foreground" />
                  <Switch
                    checked={uiContrast === 'high'}
                    onCheckedChange={(checked) => setUiContrast(checked ? 'high' : 'normal')}
                    aria-label="Yüksek kontrastı değiştir"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">Metin boyutu</p>
                    <p className="text-xs text-muted-foreground">
                      Panel yazıları {Math.round(fontScale * 100)}% ölçeğinde görüntüleniyor.
                    </p>
                  </div>
                  <Type className="h-4 w-4 text-muted-foreground" />
                </div>
                <Slider
                  min={90}
                  max={130}
                  step={5}
                  value={[Math.round(fontScale * 100)]}
                  onValueChange={([value]) => setUiFontScale(value / 100)}
                  aria-label="Metin boyutu ölçeği"
                />
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>90%</span>
                  <span>{Math.round(fontScale * 100)}%</span>
                  <span>130%</span>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed border-border/70 p-4">
                <p className="text-xs text-muted-foreground">
                  Varsayılan değerlere dönmek isterseniz aşağıdaki sıfırlama butonunu kullanabilirsiniz.
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={resetThemePreferences}
                  className="flex items-center gap-2"
                >
                  <RefreshCcw className="h-4 w-4" /> Varsayılanları Yükle
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Settings

