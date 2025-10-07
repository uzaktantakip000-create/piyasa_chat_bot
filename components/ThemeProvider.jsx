import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const STORAGE_KEY = 'piyasa.theme.preferences'

const ThemeContext = createContext(null)

const clampFontScale = (value) => {
  const numeric = Number.parseFloat(value)
  if (!Number.isFinite(numeric)) {
    return 1
  }
  return Math.min(1.3, Math.max(0.9, numeric))
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState('light')
  const [contrast, setContrast] = useState('normal')
  const [fontScale, setFontScale] = useState(1)
  const [locale, setLocale] = useState('tr')
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY)
      if (!raw) {
        setLoaded(true)
        return
      }
      const parsed = JSON.parse(raw)
      if (parsed?.theme === 'dark' || parsed?.theme === 'light') {
        setTheme(parsed.theme)
      }
      if (parsed?.contrast === 'high' || parsed?.contrast === 'normal') {
        setContrast(parsed.contrast)
      }
      if (parsed?.fontScale) {
        setFontScale(clampFontScale(parsed.fontScale))
      }
      if (parsed?.locale && typeof parsed.locale === 'string') {
        setLocale(parsed.locale)
      }
    } catch (error) {
      console.warn('Tema tercihleri okunamadı:', error)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    if (!loaded) {
      return
    }
    if (typeof document !== 'undefined') {
      const root = document.documentElement
      root.classList.toggle('dark', theme === 'dark')
      root.classList.toggle('contrast-high', contrast === 'high')
      root.setAttribute('data-theme', theme)
      root.setAttribute('data-contrast', contrast)
      root.setAttribute('data-locale', locale)
      root.setAttribute('lang', locale)
      root.style.setProperty('--app-font-scale', clampFontScale(fontScale).toString())
    }
    if (typeof window !== 'undefined') {
      const payload = {
        theme,
        contrast,
        fontScale: clampFontScale(fontScale),
        locale
      }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
      } catch (error) {
        console.warn('Tema tercihleri kaydedilemedi:', error)
      }
    }
  }, [theme, contrast, fontScale, locale, loaded])

  const resetPreferences = () => {
    setTheme('light')
    setContrast('normal')
    setFontScale(1)
    setLocale('tr')
  }

  const value = useMemo(
    () => ({
      theme,
      contrast,
      fontScale,
      locale,
      setTheme,
      setContrast: (next) => setContrast(next === 'high' ? 'high' : 'normal'),
      setFontScale: (next) => setFontScale(clampFontScale(next)),
      setLocale: (next) => {
        if (typeof next !== 'string') {
          return
        }
        const normalized = next.toLowerCase()
        setLocale(normalized === 'en' ? 'en' : 'tr')
      },
      resetPreferences
    }),
    [theme, contrast, fontScale, locale]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useThemePreferences() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useThemePreferences yalnızca ThemeProvider içinde kullanılabilir.')
  }
  return context
}

