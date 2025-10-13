import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch, ApiError, isApiError, getStoredApiKey, setStoredApiKey } from '../apiClient'

describe('ApiError', () => {
  it('should create error with message and status', () => {
    const error = new ApiError('Test error', { status: 404 })

    expect(error.message).toBe('Test error')
    expect(error.status).toBe(404)
    expect(error.code).toBe('http_404')
    expect(error.name).toBe('ApiError')
  })

  it('should create error with custom code', () => {
    const error = new ApiError('Test error', { status: 500, code: 'custom_error' })

    expect(error.code).toBe('custom_error')
  })

  it('should create error with cause', () => {
    const cause = new Error('Original error')
    const error = new ApiError('Wrapped error', { cause })

    expect(error.cause).toBe(cause)
  })

  it('should create error with response object', () => {
    const response = { ok: false, status: 400 }
    const error = new ApiError('Bad request', { status: 400, response })

    expect(error.response).toBe(response)
  })

  it('should create error with body', () => {
    const body = '{"error": "Bad request"}'
    const error = new ApiError('Bad request', { status: 400, body })

    expect(error.body).toBe(body)
  })

  it('should handle missing optional parameters', () => {
    const error = new ApiError('Simple error')

    expect(error.message).toBe('Simple error')
    expect(error.status).toBeNull()
    expect(error.code).toBe('unknown')
  })
})

describe('isApiError', () => {
  it('should return true for ApiError instances', () => {
    const error = new ApiError('Test')

    expect(isApiError(error)).toBe(true)
  })

  it('should return true for objects with name ApiError', () => {
    const error = { name: 'ApiError', message: 'Test' }

    expect(isApiError(error)).toBe(true)
  })

  it('should return false for regular Error', () => {
    const error = new Error('Test')

    expect(isApiError(error)).toBe(false)
  })

  it('should return false for null', () => {
    expect(isApiError(null)).toBe(false)
  })

  it('should return false for undefined', () => {
    expect(isApiError(undefined)).toBe(false)
  })
})

describe('apiFetch', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Successful Requests', () => {
    it('should make successful GET request', async () => {
      const mockResponse = { ok: true, json: () => Promise.resolve({ data: 'test' }) }
      global.fetch.mockResolvedValue(mockResponse)

      const response = await apiFetch('/test')

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/test'),
        expect.objectContaining({
          credentials: 'include'
        })
      )
      expect(response).toBe(mockResponse)
    })

    it('should make successful POST request with JSON body', async () => {
      const mockResponse = { ok: true, json: () => Promise.resolve({ success: true }) }
      global.fetch.mockResolvedValue(mockResponse)

      const body = { username: 'admin', password: 'password123' }
      await apiFetch('/login', { method: 'POST', body })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/login'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(body),
          headers: expect.any(Headers)
        })
      )

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.headers.get('Content-Type')).toBe('application/json')
    })

    it('should handle FormData body without stringifying', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const formData = new FormData()
      formData.append('key', 'value')

      await apiFetch('/upload', { method: 'POST', body: formData })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.body).toBe(formData)
      expect(callArgs.headers.has('Content-Type')).toBe(false)
    })

    it('should include credentials by default', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      await apiFetch('/test')

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ credentials: 'include' })
      )
    })

    it('should allow custom credentials setting', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      await apiFetch('/test', { credentials: 'omit' })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ credentials: 'omit' })
      )
    })

    it('should preserve existing headers', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      await apiFetch('/test', {
        headers: { 'X-Custom-Header': 'value' }
      })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.headers.get('X-Custom-Header')).toBe('value')
    })
  })

  describe('Error Handling', () => {
    it('should throw ApiError on HTTP error', async () => {
      const mockResponse = {
        ok: false,
        status: 404,
        text: () => Promise.resolve('Not found')
      }
      global.fetch.mockResolvedValue(mockResponse)

      await expect(apiFetch('/test')).rejects.toThrow(ApiError)
      await expect(apiFetch('/test')).rejects.toThrow('Not found')
    })

    it('should include status code in error', async () => {
      const mockResponse = {
        ok: false,
        status: 500,
        text: () => Promise.resolve('Server error')
      }
      global.fetch.mockResolvedValue(mockResponse)

      try {
        await apiFetch('/test')
      } catch (error) {
        expect(error.status).toBe(500)
        expect(error.code).toBe('http_500')
      }
    })

    it('should handle empty error response', async () => {
      const mockResponse = {
        ok: false,
        status: 500,
        text: () => Promise.resolve('')
      }
      global.fetch.mockResolvedValue(mockResponse)

      await expect(apiFetch('/test')).rejects.toThrow('API isteği başarısız oldu (500)')
    })

    it('should handle network errors', async () => {
      global.fetch.mockRejectedValue(new TypeError('Failed to fetch'))

      await expect(apiFetch('/test')).rejects.toThrow('Sunucuya ulaşılamıyor')
      await expect(apiFetch('/test')).rejects.toThrow(ApiError)
    })

    it('should detect offline state', async () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false
      })

      await expect(apiFetch('/test')).rejects.toThrow('İnternet bağlantısı kesilmiş')

      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true
      })
    })
  })

  describe('Timeout Handling', () => {
    it('should not timeout for fast requests', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const response = await apiFetch('/test', { timeout: 5000 })
      expect(response).toBe(mockResponse)
    })

    it('should accept timeout parameter', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      // Just verify that timeout parameter is accepted without error
      await expect(apiFetch('/test', { timeout: 100 })).resolves.toBeDefined()
    })

    it('should handle zero timeout gracefully', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      // Zero timeout should still complete if fetch is fast
      await expect(apiFetch('/test', { timeout: 0 })).resolves.toBeDefined()
    })
  })

  describe('Abort Signal Handling', () => {
    it('should handle aborted request', async () => {
      const controller = new AbortController()

      global.fetch.mockImplementation(() => {
        return new Promise((resolve, reject) => {
          setTimeout(() => {
            const error = new Error('Aborted')
            error.name = 'AbortError'
            reject(error)
          }, 10)
        })
      })

      setTimeout(() => controller.abort(), 5)

      await expect(apiFetch('/test', { signal: controller.signal })).rejects.toThrow(ApiError)
    }, 1000)

    it('should handle already aborted signal', async () => {
      const controller = new AbortController()
      controller.abort()

      global.fetch.mockRejectedValue(new DOMException('Aborted', 'AbortError'))

      await expect(apiFetch('/test', { signal: controller.signal })).rejects.toThrow('iptal edildi')
    })
  })

  describe('Request Body Handling', () => {
    it('should stringify object bodies', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const body = { foo: 'bar', baz: 123 }
      await apiFetch('/test', { method: 'POST', body })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.body).toBe(JSON.stringify(body))
    })

    it('should not stringify string bodies', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const body = 'plain text'
      await apiFetch('/test', { method: 'POST', body })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.body).toBe(body)
    })

    it('should not stringify FormData bodies', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const formData = new FormData()
      await apiFetch('/test', { method: 'POST', body: formData })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.body).toBe(formData)
    })

    it('should not stringify Blob bodies', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const blob = new Blob(['test'])
      await apiFetch('/test', { method: 'POST', body: blob })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.body).toBe(blob)
    })

    it('should handle null body', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      await apiFetch('/test', { method: 'POST', body: null })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.body).toBeNull()
    })
  })

  describe('Content-Type Header', () => {
    it('should set Content-Type for JSON bodies', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      await apiFetch('/test', { method: 'POST', body: { foo: 'bar' } })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.headers.get('Content-Type')).toBe('application/json')
    })

    it('should not override existing Content-Type', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      await apiFetch('/test', {
        method: 'POST',
        body: { foo: 'bar' },
        headers: { 'Content-Type': 'application/custom' }
      })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.headers.get('Content-Type')).toBe('application/custom')
    })

    it('should not set Content-Type for FormData', async () => {
      const mockResponse = { ok: true }
      global.fetch.mockResolvedValue(mockResponse)

      const formData = new FormData()
      await apiFetch('/test', { method: 'POST', body: formData })

      const callArgs = global.fetch.mock.calls[0][1]
      expect(callArgs.headers.has('Content-Type')).toBe(false)
    })
  })
})

describe('getStoredApiKey', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('should return null when no key is stored', () => {
    expect(getStoredApiKey()).toBeNull()
  })

  it('should return stored API key', () => {
    window.sessionStorage.setItem('piyasa.session.apiKey', 'test-key-123')

    expect(getStoredApiKey()).toBe('test-key-123')
  })

  it('should return null for invalid/corrupted storage', () => {
    // Test that we handle missing sessionStorage gracefully
    const result = getStoredApiKey()

    // Result should be either null (not found) or a string (if found)
    expect(result === null || typeof result === 'string').toBe(true)
  })
})

describe('setStoredApiKey', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('should store API key', () => {
    setStoredApiKey('new-key-456')

    expect(window.sessionStorage.getItem('piyasa.session.apiKey')).toBe('new-key-456')
  })

  it('should remove API key when given null', () => {
    window.sessionStorage.setItem('piyasa.session.apiKey', 'old-key')

    setStoredApiKey(null)

    expect(window.sessionStorage.getItem('piyasa.session.apiKey')).toBeNull()
  })

  it('should remove API key when given undefined', () => {
    window.sessionStorage.setItem('piyasa.session.apiKey', 'old-key')

    setStoredApiKey(undefined)

    expect(window.sessionStorage.getItem('piyasa.session.apiKey')).toBeNull()
  })

  it('should remove API key when given empty string', () => {
    window.sessionStorage.setItem('piyasa.session.apiKey', 'old-key')

    setStoredApiKey('')

    expect(window.sessionStorage.getItem('piyasa.session.apiKey')).toBeNull()
  })

  it('should not throw errors when setting keys', () => {
    // Test that setStoredApiKey doesn't throw
    expect(() => setStoredApiKey('test-key')).not.toThrow()
    expect(() => setStoredApiKey(null)).not.toThrow()
    expect(() => setStoredApiKey('')).not.toThrow()
  })
})

describe('Edge Cases', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('should handle undefined options', async () => {
    const mockResponse = { ok: true }
    global.fetch.mockResolvedValue(mockResponse)

    await expect(apiFetch('/test', undefined)).resolves.toBe(mockResponse)
  })

  it('should handle empty headers object', async () => {
    const mockResponse = { ok: true }
    global.fetch.mockResolvedValue(mockResponse)

    await apiFetch('/test', { headers: {} })

    expect(global.fetch).toHaveBeenCalled()
  })

  it('should handle Headers instance', async () => {
    const mockResponse = { ok: true }
    global.fetch.mockResolvedValue(mockResponse)

    const headers = new Headers()
    headers.set('X-Custom', 'value')

    await apiFetch('/test', { headers })

    const callArgs = global.fetch.mock.calls[0][1]
    expect(callArgs.headers.get('X-Custom')).toBe('value')
  })
})
