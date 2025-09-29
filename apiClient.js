const DEFAULT_BASE_URL = import.meta.env?.PROD ? '/api' : 'http://localhost:8000'
const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || DEFAULT_BASE_URL
const STORAGE_KEY = 'piyasa.dashboard.apiKey'

let apiKey = null

function resolveInitialApiKey() {
  if (typeof window !== 'undefined') {
    try {
      const persisted = window.localStorage?.getItem(STORAGE_KEY)
      if (persisted) {
        return persisted
      }
    } catch (error) {
      console.warn('[apiClient] localStorage erişilemedi:', error)
    }

    if (window?.__API_KEY__) {
      return window.__API_KEY__
    }
  }

  return import.meta.env?.VITE_API_KEY || null
}

apiKey = resolveInitialApiKey()

if (!apiKey) {
  console.warn('[apiClient] API anahtarı bulunamadı. .env dosyanıza VITE_API_KEY ekleyin veya giriş ekranından girin.')
}

function buildHeaders(existingHeaders = {}) {
  const headers = new Headers(existingHeaders)
  if (apiKey) {
    headers.set('X-API-Key', apiKey)
  }
  return headers
}

export async function apiFetch(path, options = {}) {
  if (!apiKey) {
    throw new Error('API anahtarı yapılandırılmadı. Giriş ekranından anahtar girin veya VITE_API_KEY env değişkenini ayarlayın.')
  }

  const url = `${API_BASE_URL}${path}`
  const opts = { ...options }
  opts.headers = buildHeaders(options.headers)
  const body = opts.body
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const isBlob = typeof Blob !== 'undefined' && body instanceof Blob
  const isArrayBuffer = body instanceof ArrayBuffer || ArrayBuffer.isView?.(body)
  const isURLSearchParams = typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams
  const isReadableStream = typeof ReadableStream !== 'undefined' && body instanceof ReadableStream

  const shouldStringify = body != null && typeof body === 'object' && !isFormData && !isBlob && !isArrayBuffer && !isURLSearchParams && !isReadableStream
  if (shouldStringify) {
    opts.body = JSON.stringify(body)
  }

  if (opts.body != null && opts.headers instanceof Headers && !opts.headers.has('Content-Type') && (shouldStringify || typeof opts.body === 'string')) {
    opts.headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(url, opts)
  if (!response.ok) {
    if (response.status === 401) {
      clearApiKey()
    }
    const text = await response.text()
    throw new Error(`API isteği başarısız oldu (${response.status}): ${text}`)
  }
  return response
}

export { API_BASE_URL }

export function getApiKey() {
  return apiKey
}

export function setApiKey(nextKey, { persist = true } = {}) {
  apiKey = nextKey || null

  if (typeof window !== 'undefined') {
    try {
      if (apiKey && persist) {
        window.localStorage?.setItem(STORAGE_KEY, apiKey)
      } else {
        window.localStorage?.removeItem(STORAGE_KEY)
      }
    } catch (error) {
      console.warn('[apiClient] API anahtarı depolanamadı:', error)
    }
  }
}

export function clearApiKey() {
  setApiKey(null)
}
