const DEFAULT_BASE_URL = import.meta.env?.PROD ? '/api' : 'http://localhost:8000'
const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || DEFAULT_BASE_URL
const SESSION_STORAGE_KEY = 'piyasa.session.apiKey'
const DEFAULT_TIMEOUT_MS = 15000

export class ApiError extends Error {
  constructor(message, { status, code, cause, response, body } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = typeof status === 'number' ? status : null
    this.code = code || (typeof status === 'number' ? `http_${status}` : 'unknown')
    if (cause) {
      this.cause = cause
    }
    if (response) {
      this.response = response
    }
    if (body !== undefined) {
      this.body = body
    }
  }
}

export function isApiError(error) {
  return error instanceof ApiError || error?.name === 'ApiError'
}

function buildHeaders(existingHeaders = {}) {
  if (existingHeaders instanceof Headers) {
    return existingHeaders
  }
  return new Headers(existingHeaders)
}

export async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`
  const { timeout = DEFAULT_TIMEOUT_MS, signal: externalSignal, ...restOptions } = options
  const opts = { ...restOptions }
  opts.credentials = restOptions.credentials ?? 'include'
  opts.headers = buildHeaders(restOptions.headers)
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

  const controller = new AbortController()
  let externalAbortHandler = null
  let timeoutId = null
  let timedOut = false

  if (externalSignal) {
    externalAbortHandler = () => {
      if (!controller.signal.aborted) {
        controller.abort(externalSignal.reason)
      }
    }
    if (externalSignal.aborted) {
      externalAbortHandler()
    } else {
      externalSignal.addEventListener('abort', externalAbortHandler, { once: true })
    }
  }

  const timeoutMs = Number.isFinite(timeout) ? Math.max(0, timeout) : DEFAULT_TIMEOUT_MS
  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      timedOut = true
      if (!controller.signal.aborted) {
        controller.abort()
      }
    }, timeoutMs)
  }

  opts.signal = controller.signal

  try {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      throw new ApiError('İnternet bağlantısı kesilmiş görünüyor. Lütfen bağlantınızı kontrol edin.', {
        code: 'offline'
      })
    }

    const response = await fetch(url, opts)
    if (!response.ok) {
      const text = await response.text()
      throw new ApiError(
        text ? `API isteği başarısız oldu (${response.status}): ${text}` : `API isteği başarısız oldu (${response.status}).`,
        {
          status: response.status,
          code: `http_${response.status}`,
          response,
          body: text
        }
      )
    }
    return response
  } catch (error) {
    if (timedOut || (error?.name === 'AbortError' && timedOut)) {
      throw new ApiError('API isteği zaman aşımına uğradı. Lütfen bağlantınızı kontrol edin ve tekrar deneyin.', {
        code: 'timeout',
        cause: error
      })
    }

    if (isApiError(error)) {
      throw error
    }

    if (error?.name === 'AbortError') {
      throw new ApiError('İstek iptal edildi.', { code: 'cancelled', cause: error })
    }

    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      throw new ApiError('İnternet bağlantısı kesilmiş görünüyor. Lütfen bağlantınızı kontrol edin.', {
        code: 'offline',
        cause: error
      })
    }

    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new ApiError('Sunucuya ulaşılamıyor veya ağ bağlantısı kesildi.', {
        code: 'network',
        cause: error
      })
    }

    throw new ApiError(error?.message || 'API isteği beklenmeyen bir hatayla başarısız oldu.', {
      cause: error
    })
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    if (externalSignal && externalAbortHandler) {
      externalSignal.removeEventListener('abort', externalAbortHandler)
    }
  }
}

export { API_BASE_URL }

export function getStoredApiKey() {
  if (typeof window === 'undefined') {
    return null
  }
  try {
    return window.sessionStorage?.getItem(SESSION_STORAGE_KEY)
  } catch (error) {
    console.warn('[apiClient] sessionStorage okunamadı:', error)
    return null
  }
}

export function setStoredApiKey(nextKey) {
  if (typeof window === 'undefined') {
    return
  }
  try {
    if (nextKey) {
      window.sessionStorage?.setItem(SESSION_STORAGE_KEY, nextKey)
    } else {
      window.sessionStorage?.removeItem(SESSION_STORAGE_KEY)
    }
  } catch (error) {
    console.warn('[apiClient] sessionStorage güncellenemedi:', error)
  }
}
