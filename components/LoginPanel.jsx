import { useState } from 'react'

function LoginPanel({ onSubmit, submitting, error, requiresPassword, defaultApiKey }) {
  const [apiKey, setApiKey] = useState(defaultApiKey || '')
  const [password, setPassword] = useState('')
  const [apiKeyVisible, setApiKeyVisible] = useState(false)
  const [passwordVisible, setPasswordVisible] = useState(false)

  const handleSubmit = (event) => {
    event.preventDefault()
    onSubmit({ apiKey: apiKey.trim(), password: password.trim() })
  }

  return (
    <div className="min-h-screen bg-muted flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-xl border border-border bg-card shadow-sm p-8 space-y-6"
      >
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Yönetim Paneli Girişi</h1>
          <p className="text-sm text-muted-foreground">
            API anahtarını ve (tanımlıysa) panel şifresini girerek devam edin.
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="apiKey" className="text-sm font-medium text-foreground">
            API Anahtarı
          </label>
          <div className="flex items-center gap-2">
            <input
              id="apiKey"
              name="apiKey"
              type={apiKeyVisible ? 'text' : 'password'}
              autoComplete="off"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="XXXXXXXXXXXX"
              required
            />
            <button
              type="button"
              className="text-xs font-medium text-primary underline-offset-2 hover:underline"
              onClick={() => setApiKeyVisible((prev) => !prev)}
              aria-pressed={apiKeyVisible}
            >
              {apiKeyVisible ? 'Gizle' : 'Göster'}
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            API anahtarınızı yönetim paneli ayarları bölümünden edinebilirsiniz.
          </p>
        </div>

        {requiresPassword && (
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium text-foreground">
              Panel Şifresi
            </label>
            <div className="flex items-center gap-2">
              <input
                id="password"
                name="password"
                type={passwordVisible ? 'text' : 'password'}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                className="text-xs font-medium text-primary underline-offset-2 hover:underline"
                onClick={() => setPasswordVisible((prev) => !prev)}
                aria-pressed={passwordVisible}
              >
                {passwordVisible ? 'Gizle' : 'Göster'}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Panel şifresi, yetkili yöneticiler tarafından sağlanmaktadır.
            </p>
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <button
          type="submit"
          className="w-full inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60"
          disabled={submitting}
        >
          {submitting ? 'Doğrulanıyor…' : 'Giriş Yap'}
        </button>
      </form>
    </div>
  )
}

export default LoginPanel
