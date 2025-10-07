import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { X } from 'lucide-react'

const ToastContext = createContext(null)

const typeStyles = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  error: 'border-destructive/40 bg-destructive/10 text-destructive',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  info: 'border-border bg-background/90 text-foreground'
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timeoutsRef = useRef({})
  const [history, setHistory] = useState([])

  const dismissToast = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
    if (timeoutsRef.current[id]) {
      clearTimeout(timeoutsRef.current[id])
      delete timeoutsRef.current[id]
    }
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
  }, [])

  const showToast = useCallback(
    ({ title, description, type = 'info', duration = 4000, source = 'ui' }) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      setToasts((current) => [
        ...current,
        {
          id,
          title,
          description,
          type
        }
      ])

      setHistory((current) => {
        const record = {
          id,
          title: title ?? '',
          description: description ?? '',
          type,
          source,
          timestamp: new Date().toISOString()
        }
        return [record, ...current].slice(0, 60)
      })

      if (duration > 0 && typeof window !== 'undefined') {
        timeoutsRef.current[id] = window.setTimeout(() => {
          dismissToast(id)
        }, duration)
      }

      return id
    },
    [dismissToast]
  )

  const value = useMemo(
    () => ({
      showToast,
      dismissToast,
      history,
      clearHistory
    }),
    [showToast, dismissToast, history, clearHistory]
  )

  useEffect(() => {
    return () => {
      Object.values(timeoutsRef.current).forEach((timeoutId) => {
        if (typeof window !== 'undefined') {
          window.clearTimeout(timeoutId)
        } else {
          clearTimeout(timeoutId)
        }
      })
      timeoutsRef.current = {}
    }
  }, [])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-3">
        {toasts.map((toast) => {
          const variant = typeStyles[toast.type] ?? typeStyles.info
          return (
            <div
              key={toast.id}
              className={`pointer-events-auto overflow-hidden rounded-md border shadow-lg backdrop-blur-sm ${variant}`}
            >
              <div className="flex items-start justify-between gap-3 p-4">
                <div>
                  {toast.title && <p className="text-sm font-semibold">{toast.title}</p>}
                  {toast.description && <p className="mt-1 text-sm leading-relaxed">{toast.description}</p>}
                </div>
                <button
                  type="button"
                  onClick={() => dismissToast(toast.id)}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md text-sm text-muted-foreground transition hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                  <span className="sr-only">Kapat</span>
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast, ToastProvider içinde kullanılmalıdır.')
  }
  return context
}
