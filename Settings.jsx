import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Settings as SettingsIcon, 
  Clock, 
  MessageSquare, 
  Zap,
  Save,
  RotateCcw
} from 'lucide-react'

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:8000'

function Settings() {
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Fetch settings
  const fetchSettings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/settings`)
      if (response.ok) {
        const data = await response.json()
        const settingsObj = {}
        data.forEach(setting => {
          settingsObj[setting.key] = setting.value
        })
        setSettings(settingsObj)
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    } finally {
      setLoading(false)
    }
  }

  // Update setting
  const updateSetting = async (key, value) => {
    try {
      setSaving(true)
      const response = await fetch(`${API_BASE_URL}/settings/${key}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(value),
      })

      if (response.ok) {
        setSettings(prev => ({
          ...prev,
          [key]: value
        }))
      }
    } catch (error) {
      console.error('Failed to update setting:', error)
    } finally {
      setSaving(false)
    }
  }

  // Scale simulation
  const scaleSimulation = async (factor) => {
    try {
      const response = await fetch(`${API_BASE_URL}/control/scale?factor=${factor}`, {
        method: 'POST'
      })
      
      if (response.ok) {
        // Update will be reflected in next metrics fetch
      }
    } catch (error) {
      console.error('Failed to scale simulation:', error)
    }
  }

  useEffect(() => {
    fetchSettings()
  }, [])

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
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>Reply Olasılığı (%{((settings.reply_probability?.value || 0.65) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.reply_probability?.value || 0.65) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('reply_probability', { value: value / 100 })
                    }
                    max={100}
                    step={5}
                    className="w-full"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Mention Olasılığı (%{((settings.mention_probability?.value || 0.35) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.mention_probability?.value || 0.35) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('mention_probability', { value: value / 100 })
                    }
                    max={100}
                    step={5}
                    className="w-full"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Kısa Tepki Olasılığı (%{((settings.short_reaction_probability?.value || 0.12) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.short_reaction_probability?.value || 0.12) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('short_reaction_probability', { value: value / 100 })
                    }
                    max={50}
                    step={2}
                    className="w-full"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Yeni Mesaj Olasılığı (%{((settings.new_message_probability?.value || 0.35) * 100).toFixed(0)})</Label>
                  <Slider
                    value={[(settings.new_message_probability?.value || 0.35) * 100]}
                    onValueChange={([value]) => 
                      updateSetting('new_message_probability', { value: value / 100 })
                    }
                    max={100}
                    step={5}
                    className="w-full"
                  />
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Mesaj Uzunluk Profili</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Kısa (%{((settings.message_length_profile?.value?.short || 0.55) * 100).toFixed(0)})</Label>
                    <Slider
                      value={[(settings.message_length_profile?.value?.short || 0.55) * 100]}
                      onValueChange={([value]) => {
                        const current = settings.message_length_profile?.value || {}
                        updateSetting('message_length_profile', { 
                          value: { ...current, short: value / 100 }
                        })
                      }}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Orta (%{((settings.message_length_profile?.value?.medium || 0.35) * 100).toFixed(0)})</Label>
                    <Slider
                      value={[(settings.message_length_profile?.value?.medium || 0.35) * 100]}
                      onValueChange={([value]) => {
                        const current = settings.message_length_profile?.value || {}
                        updateSetting('message_length_profile', { 
                          value: { ...current, medium: value / 100 }
                        })
                      }}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Uzun (%{((settings.message_length_profile?.value?.long || 0.10) * 100).toFixed(0)})</Label>
                    <Slider
                      value={[(settings.message_length_profile?.value?.long || 0.10) * 100]}
                      onValueChange={([value]) => {
                        const current = settings.message_length_profile?.value || {}
                        updateSetting('message_length_profile', { 
                          value: { ...current, long: value / 100 }
                        })
                      }}
                      max={100}
                      step={5}
                      className="w-full"
                    />
                  </div>
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
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label>Dakikada Maksimum Mesaj</Label>
                  <Input
                    type="number"
                    value={settings.max_msgs_per_min?.value || 6}
                    onChange={(e) => 
                      updateSetting('max_msgs_per_min', { value: parseInt(e.target.value) })
                    }
                    min={1}
                    max={20}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Typing Simülasyonu</Label>
                  <Switch
                    checked={settings.typing_enabled?.value || true}
                    onCheckedChange={(checked) => 
                      updateSetting('typing_enabled', { value: checked })
                    }
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={settings.prime_hours_boost?.value || true}
                    onCheckedChange={(checked) => 
                      updateSetting('prime_hours_boost', { value: checked })
                    }
                  />
                  <Label>Prime Hours Boost</Label>
                </div>
                
                <div className="space-y-2">
                  <Label>Prime Hours (virgülle ayırın)</Label>
                  <Input
                    value={(settings.prime_hours?.value || []).join(', ')}
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
                      value={settings.bot_hourly_msg_limit?.value?.min || 6}
                      onChange={(e) => {
                        const current = settings.bot_hourly_msg_limit?.value || {}
                        updateSetting('bot_hourly_msg_limit', { 
                          value: { ...current, min: parseInt(e.target.value) }
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
                      value={settings.bot_hourly_msg_limit?.value?.max || 12}
                      onChange={(e) => {
                        const current = settings.bot_hourly_msg_limit?.value || {}
                        updateSetting('bot_hourly_msg_limit', { 
                          value: { ...current, max: parseInt(e.target.value) }
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
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Minimum WPM</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={settings.typing_speed_wpm?.value?.min || 2.5}
                      onChange={(e) => {
                        const current = settings.typing_speed_wpm?.value || {}
                        updateSetting('typing_speed_wpm', { 
                          value: { ...current, min: parseFloat(e.target.value) }
                        })
                      }}
                      min={1}
                      max={10}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Maksimum WPM</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={settings.typing_speed_wpm?.value?.max || 4.5}
                      onChange={(e) => {
                        const current = settings.typing_speed_wpm?.value || {}
                        updateSetting('typing_speed_wpm', { 
                          value: { ...current, max: parseFloat(e.target.value) }
                        })
                      }}
                      min={1}
                      max={10}
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
      </Tabs>
    </div>
  )
}

export default Settings

