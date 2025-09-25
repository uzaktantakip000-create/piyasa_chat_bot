const DEFAULT_BASE_URL = import.meta.env?.PROD ? '/api' : 'http://localhost:8000'
const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || DEFAULT_BASE_URL
const API_KEY = import.meta.env?.VITE_API_KEY || window?.__API_KEY__

if (!API_KEY) {
  console.warn('[apiClient] API anahtarı bulunamadı. .env dosyanıza VITE_API_KEY ekleyin.')
}

function buildHeaders(existingHeaders = {}) {
  const headers = new Headers(existingHeaders)
  if (API_KEY) {
    headers.set('X-API-Key', API_KEY)
  }
  return headers
}

export async function apiFetch(path, options = {}) {
  if (!API_KEY) {
    throw new Error('API anahtarı yapılandırılmadı. VITE_API_KEY env değişkenini ayarlayın.')
  }

  const url = `${API_BASE_URL}${path}`
  const opts = { ...options }
  opts.headers = buildHeaders(options.headers)
  if (opts.body && !(opts.headers instanceof Headers && opts.headers.has('Content-Type'))) {
    opts.headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(url, opts)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API isteği başarısız oldu (${response.status}): ${text}`)
  }
  return response
}

export { API_BASE_URL }
