import { useState } from 'react'

function LoginPanel({ onSubmit, submitting, error, defaultApiKey }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [totpVisible, setTotpVisible] = useState(false)
  const [apiKeyVisible, setApiKeyVisible] = useState(false)

  const handleSubmit = (event) => {
    event.preventDefault()
    onSubmit({ username: username.trim(), password: password.trim(), totp: totp.trim() })
  }

  return (
    <div className="min-h-screen bg-muted flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-xl border border-border bg-card shadow-sm p-8 space-y-6"
      >
        <div className="space-y-3 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Yönetim Paneli Girişi</h1>
          <p className="text-sm text-muted-foreground">
            RBAC destekli yönetim paneline erişmek için kullanıcı adı, parola ve (tanımlıysa) MFA kodunuzu girin. Oturum, tarayıcı
            sekmesi kapatıldığında sona eren HttpOnly çerez + sessionStorage kombinasyonu ile korunur.
          </p>
          <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-left text-xs leading-relaxed text-blue-800">
            <p className="font-semibold text-blue-900">Güvenlik ipuçları</p>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              <li>Giriş sonrası API anahtarınız yalnızca oturum boyunca sessionStorage'da tutulur; pencereyi kapattığınızda temizlenir.</li>
              <li>HttpOnly oturum çerezi, komut dosyalarının anahtarınızı ele geçirmesini engeller; XSS durumda bile anahtar çerez olmadan kullanılamaz.</li>
              <li>Paylaşımlı cihazlarda işiniz bittiğinde "Çıkış" yaparak ve tarayıcıyı kapatarak oturumu sonlandırın.</li>
            </ul>
          </div>
        </div>

        <div className="space-y-1">
          <label htmlFor="username" className="text-sm font-medium text-foreground">
            Kullanıcı Adı
          </label>
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="admin"
            required
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium text-foreground">
            Parola
          </label>
          <div className="flex items-center gap-2">
            <input
              id="password"
              name="password"
              type={passwordVisible ? 'text' : 'password'}
              autoComplete="current-password"
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
            Parolanız PBKDF2 ile sunucuda saklanır; istemci tarafında yalnızca giriş sırasında kullanılır.
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="totp" className="text-sm font-medium text-foreground">
            MFA Kodu (varsa)
          </label>
          <div className="flex items-center gap-2">
            <input
              id="totp"
              name="totp"
              type={totpVisible ? 'text' : 'password'}
              inputMode="numeric"
              pattern="\d{6}"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={totp}
              onChange={(event) => setTotp(event.target.value)}
              placeholder="123456"
            />
            <button
              type="button"
              className="text-xs font-medium text-primary underline-offset-2 hover:underline"
              onClick={() => setTotpVisible((prev) => !prev)}
              aria-pressed={totpVisible}
            >
              {totpVisible ? 'Gizle' : 'Göster'}
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            Çok faktörlü doğrulama etkinse 6 haneli kodu girin; aksi halde bu alanı boş bırakabilirsiniz.
          </p>
        </div>

        {defaultApiKey && (
          <div className="space-y-1">
            <label htmlFor="currentApiKey" className="text-sm font-medium text-foreground">
              Mevcut API Anahtarınız
            </label>
            <div className="flex items-center gap-2">
              <input
                id="currentApiKey"
                name="currentApiKey"
                type={apiKeyVisible ? 'text' : 'password'}
                readOnly
                value={defaultApiKey}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
              API anahtarı yalnızca bu tarayıcı sekmesinin sessionStorage alanında tutulur ve oturum kapandığında otomatik silinir.
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
