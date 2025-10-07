import { useState, useEffect, useMemo, useCallback } from 'react'
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
  RefreshCcw,
  BellRing,
  Mail,
  Smartphone,
  Bell
} from 'lucide-react'

import { apiFetch } from './apiClient'
import InlineNotice from './components/InlineNotice'
import { useThemePreferences } from './components/ThemeProvider'
import { useTranslation } from './localization'
import {
  DEFAULT_MESSAGE_LENGTH_PROFILE,
  createAlertChannelOptions,
  createDefaultAlertMetrics,
  normalizeAlertPreferences,
  normalizeAlertDestinations,
  formatAlertDestinations,
  parseAlertDestinationsInput,
  normalizeMessageLengthProfile,
  toNumber,
  summarizeAlertChannels
} from './settings_alerts'






function Settings() {
  const { t, locale, setLocale, availableLocales } = useTranslation()
  const translateWithFallback = useCallback(
    (key, fallback = '') => {
      const result = t(key)
      return result || fallback
    },
    [t, locale]
  )
  const alertChannels = useMemo(
    () => createAlertChannelOptions(translateWithFallback),
    [translateWithFallback]
  )
  const defaultAlertMetrics = useMemo(
    () => createDefaultAlertMetrics(translateWithFallback, alertChannels),
    [translateWithFallback, alertChannels]
  )
  const {
    theme: uiTheme,
    contrast: uiContrast,
    fontScale,
    setTheme: setUiTheme,
    setContrast: setUiContrast,
    setFontScale: setUiFontScale,
    resetPreferences: resetThemePreferences
  } = useThemePreferences()
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [newsFeedsText, setNewsFeedsText] = useState('')
  const [alertDraft, setAlertDraft] = useState(() =>
    normalizeAlertPreferences(undefined, defaultAlertMetrics, alertChannels)
  )
  const [alertDestinations, setAlertDestinations] = useState(() => formatAlertDestinations())

  // Fetch settings
  const fetchSettings = async () => {
    try {
      const response = await apiFetch('/settings')
      const data = await response.json()
      const settingsObj = {}
      let feedsValue = ''
      let alertPreferencesValue = null
      let alertDestinationsValue = null
      data.forEach(setting => {
        let nextValue = setting.value
        if (setting.key === 'message_length_profile' && setting.value?.value) {
          nextValue = { value: normalizeMessageLengthProfile(setting.value.value) }
        }
        if (setting.key === 'alert_preferences') {
          const normalizedAlerts = normalizeAlertPreferences(
            setting.value?.value,
            defaultAlertMetrics,
            alertChannels
          )
          nextValue = { value: normalizedAlerts }
          alertPreferencesValue = normalizedAlerts
        }
        if (setting.key === 'alert_destinations') {
          const normalizedDestinations = normalizeAlertDestinations(setting.value?.value)
          nextValue = { value: normalizedDestinations }
          alertDestinationsValue = formatAlertDestinations(normalizedDestinations)
        }
        settingsObj[setting.key] = nextValue
        if (setting.key === 'news_feed_urls') {
          const arr = Array.isArray(nextValue?.value) ? nextValue.value : []
          feedsValue = arr.join('\n')
        }
      })
      setSettings(settingsObj)
      setNewsFeedsText(feedsValue)
      setAlertDraft(
        alertPreferencesValue ?? normalizeAlertPreferences(undefined, defaultAlertMetrics, alertChannels)
      )
      setAlertDestinations(alertDestinationsValue ?? formatAlertDestinations())
      setErrorMessage('')
      setSuccessMessage('')
    } catch (error) {
      console.error('Failed to fetch settings:', error)
      setErrorMessage(
        error?.message
          ? `${translateWithFallback('settings.messages.fetchErrorPrefix', 'Ayarlar yüklenirken hata oluştu:')} ${error.message}`
          : translateWithFallback(
              'settings.messages.fetchErrorGeneric',
              'Ayarlar yüklenirken beklenmeyen bir hata oluştu.'
            )
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
      setSuccessMessage(translateWithFallback('settings.messages.updateSuccess', 'Ayar başarıyla güncellendi.'))
      return true
    } catch (error) {
      console.error('Failed to update setting:', error)
      setErrorMessage(
        error?.message
          ? `${translateWithFallback('settings.messages.updateErrorPrefix', 'Ayar güncellenirken hata oluştu:')} ${error.message}`
          : translateWithFallback(
              'settings.messages.updateErrorGeneric',
              'Ayar güncellenirken beklenmeyen bir hata oluştu.'
            )
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

  const handleAlertThresholdChange = (metricId, field, rawValue) => {
    setAlertDraft(prev =>
      prev.map(metric => (metric.id === metricId ? { ...metric, [field]: rawValue } : metric))
    )
  }

  const handleAlertChannelToggle = (metricId, channelId, enabled) => {
    setAlertDraft(prev =>
      prev.map(metric => {
        if (metric.id !== metricId) {
          return metric
        }
        const existing = new Set(metric.channels || [])
        if (enabled) {
          existing.add(channelId)
        } else {
          existing.delete(channelId)
        }
        const nextChannels = Array.from(existing)
        if (!nextChannels.length) {
          return { ...metric, channels: [] }
        }
        return { ...metric, channels: nextChannels }
      })
    )
  }

  const handleAlertPreferencesSave = async () => {
    const sanitized = alertDraft.map(metric => {
      const defaultMetric = defaultAlertMetrics.find(item => item.id === metric.id) ?? metric
      const warningValue = toNumber(metric.warning, defaultMetric.warningDefault)
      const criticalValue = toNumber(metric.critical, defaultMetric.criticalDefault)
      const channels = (metric.channels || []).filter(channel =>
        alertChannels.some(option => option.id === channel)
      )
      const ensuredChannels = channels.length > 0 ? channels : [...(defaultMetric.recommendedChannels || ['email'])]
      return {
        id: metric.id,
        label: metric.label,
        description: metric.description,
        unit: metric.unit,
        warning: warningValue,
        critical: criticalValue,
        channels: ensuredChannels
      }
    })

    const ok = await updateSetting('alert_preferences', { value: sanitized })
    if (ok) {
      setAlertDraft(normalizeAlertPreferences(sanitized, defaultAlertMetrics, alertChannels))
    }
  }

  const handleAlertDestinationsSave = async () => {
    const parsed = parseAlertDestinationsInput(alertDestinations)
    const ok = await updateSetting('alert_destinations', { value: parsed })
    if (ok) {
      setAlertDestinations(formatAlertDestinations(parsed))
    }
  }

  useEffect(() => {
    setAlertDraft(prev => normalizeAlertPreferences(prev, defaultAlertMetrics, alertChannels))
  }, [defaultAlertMetrics, alertChannels])

  const channelSummaries = useMemo(
    () => summarizeAlertChannels(alertDraft, alertChannels, translateWithFallback),
    [alertDraft, alertChannels, translateWithFallback]
  )

  // Scale simulation
  const scaleSimulation = async (factor) => {
    try {
      setErrorMessage('')
      setSuccessMessage('')
      await apiFetch(`/control/scale?factor=${factor}`, {
        method: 'POST'
      })
      setSuccessMessage(
        translateWithFallback('settings.messages.scaleSuccess', 'Simülasyon ölçeklendirme isteği gönderildi.')
      )
    } catch (error) {
      console.error('Failed to scale simulation:', error)
      setErrorMessage(
        error?.message
          ? `${translateWithFallback('settings.messages.scaleErrorPrefix', 'Ölçek güncellenirken hata oluştu:')} ${error.message}`
          : translateWithFallback(
              'settings.messages.scaleErrorGeneric',
              'Ölçek güncellenirken beklenmeyen bir hata oluştu.'
            )
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
    return (
      <div className="flex items-center justify-center h-64">
        {translateWithFallback('common.loading', 'Yükleniyor...')}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">
          {translateWithFallback('settings.title', 'Ayarlar')}
        </h2>
        <p className="text-muted-foreground">
          {translateWithFallback(
            'settings.subtitle',
            'Simülasyon davranışlarını ve parametrelerini yapılandırın'
          )}
        </p>
      </div>

      <Tabs defaultValue="behavior" className="space-y-4">
        <TabsList>
          <TabsTrigger value="behavior">
            {translateWithFallback('settings.tabs.behavior', 'Davranış')}
          </TabsTrigger>
          <TabsTrigger value="timing">
            {translateWithFallback('settings.tabs.timing', 'Zamanlama')}
          </TabsTrigger>
          <TabsTrigger value="alerts">{t('settings.alerts.tab') || 'Bildirimler'}</TabsTrigger>
          <TabsTrigger value="performance">
            {translateWithFallback('settings.tabs.performance', 'Performans')}
          </TabsTrigger>
          <TabsTrigger value="appearance">
            {translateWithFallback('settings.tabs.appearance', 'Görünüm')}
          </TabsTrigger>
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

        {/* Alert Preferences */}
        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BellRing className="h-5 w-5" />
                {t('settings.alerts.thresholds.title') || 'Kritik Eşik Uyarıları'}
              </CardTitle>
              <CardDescription>
                {t('settings.alerts.thresholds.description') || 'Metrik eşiklerini tanımlayın ve tetiklenen uyarıların hangi kanala yönleneceğini belirleyin.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {(errorMessage || successMessage) && (
                <InlineNotice
                  type={errorMessage ? 'error' : 'success'}
                  message={errorMessage || successMessage}
                />
              )}
              {alertDraft.map(metric => {
                const hasChannels = metric.channels && metric.channels.length > 0
                return (
                  <div
                    key={metric.id}
                    className="space-y-4 rounded-lg border border-border/60 bg-muted/20 p-4"
                  >
                    <div className="space-y-1">
                      <h4 className="text-sm font-semibold text-foreground">{metric.label}</h4>
                      <p className="text-xs text-muted-foreground">{metric.description}</p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Uyarı eşiği ({metric.unit})</Label>
                        <Input
                          type="number"
                          step="0.1"
                          value={metric.warning}
                          onChange={e => handleAlertThresholdChange(metric.id, 'warning', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Kritik eşiği ({metric.unit})</Label>
                        <Input
                          type="number"
                          step="0.1"
                          value={metric.critical}
                          onChange={e => handleAlertThresholdChange(metric.id, 'critical', e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>Bildirim kanalları</Label>
                      <div className="flex flex-wrap gap-3">
                        {alertChannels.map(channel => (
                          <label
                            key={channel.id}
                            className="flex items-center gap-2 rounded-md border border-border/60 bg-background px-3 py-2 text-sm"
                          >
                            <Switch
                              checked={metric.channels?.includes(channel.id)}
                              onCheckedChange={checked => handleAlertChannelToggle(metric.id, channel.id, checked)}
                            />
                            <span>{channel.label}</span>
                          </label>
                        ))}
                      </div>
                      {!hasChannels && (
                        <p className="text-xs text-amber-600">
                          {t('settings.alerts.metricWarning') || 'En az bir kanal seçin; boş bırakılırsa varsayılan rota uygulanır.'}
                        </p>
                      )}
                    </div>
                  </div>
                )
              })}
              <div className="flex justify-end">
                <Button onClick={handleAlertPreferencesSave} disabled={saving}>
                  {t('settings.alerts.saveThresholds') || 'Eşikleri Kaydet'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                {t('settings.alerts.channels.title') || 'Kanal Temas Noktaları'}
              </CardTitle>
              <CardDescription>
                {t('settings.alerts.channels.description') || 'Uyarı alıcı listelerini satır satır veya virgülle ayırarak güncelleyin.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label>E-posta</Label>
                  <Textarea
                    className="min-h-[100px]"
                    value={alertDestinations.email}
                    onChange={e => setAlertDestinations(prev => ({ ...prev, email: e.target.value }))}
                    placeholder={'ops-team@firma.com\nincidents@firma.com'}
                  />
                  <p className="text-xs text-muted-foreground">Dağıtım listeleri dahil olmak üzere birden fazla adres ekleyin.</p>
                </div>
                <div className="space-y-2">
                  <Label>SMS</Label>
                  <Textarea
                    className="min-h-[100px]"
                    value={alertDestinations.sms}
                    onChange={e => setAlertDestinations(prev => ({ ...prev, sms: e.target.value }))}
                    placeholder={'+905321234567\n+905551112233'}
                  />
                  <p className="text-xs text-muted-foreground">E164 formatını kullanın. Operasyon ekibi üyelerini ekleyin.</p>
                </div>
                <div className="space-y-2">
                  <Label>Push / Kanal</Label>
                  <Textarea
                    className="min-h-[100px]"
                    value={alertDestinations.push}
                    onChange={e => setAlertDestinations(prev => ({ ...prev, push: e.target.value }))}
                    placeholder={'incident-war-room\nobservability-feed'}
                  />
                  <p className="text-xs text-muted-foreground">Panel bildirimi ve entegrasyon webhook etiketlerini belirtin.</p>
                </div>
              </div>
              <div className="flex justify-end">
                <Button onClick={handleAlertDestinationsSave} disabled={saving}>
                  {t('settings.alerts.saveDestinations') || 'Kanalları Kaydet'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                {t('settings.alerts.summary.title') || 'Kanal Özetleri'}
              </CardTitle>
              <CardDescription>
                {t('settings.alerts.summary.description') || 'Hangi metriklerin hangi kanalda bildirim tetikleyeceğini hızlıca görün.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              {channelSummaries.map(summary => {
                const ChannelIcon = summary.icon
                return (
                  <div
                    key={summary.id}
                    className="rounded-lg border border-border/60 bg-muted/20 p-4"
                  >
                    <div className="flex items-center gap-2">
                      <ChannelIcon className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{summary.label}</span>
                    </div>
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {summary.metrics.length ? (
                        summary.metrics.map(metric => (
                          <li key={metric.id} className="space-y-0.5">
                            <div className="font-medium text-foreground">{metric.label}</div>
                            <div className="text-[11px] text-muted-foreground/80">{metric.summary}</div>
                          </li>
                        ))
                      ) : (
                        <li>{t('settings.alerts.noMetrics') || 'Henüz bu kanal için eşlenmiş metrik yok.'}</li>
                      )}
                    </ul>
                  </div>
                )
              })}
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

              <div className="space-y-2">
                <p className="text-sm font-medium">{t('settings.appearance.language') || 'Dil ve ikonografi'}</p>
                <div className="flex flex-wrap items-center gap-2">
                  {availableLocales.map((code) => (
                    <Button
                      key={code}
                      type="button"
                      variant={locale === code ? 'default' : 'outline'}
                      onClick={() => setLocale(code)}
                    >
                      {t(`settings.appearance.locale.${code}`) || code.toUpperCase()}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('settings.appearance.languageHint') || 'Dil değişikliği metinleri ve ikon tercihlerini günceller.'}
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

