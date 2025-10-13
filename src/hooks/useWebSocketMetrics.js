import { useEffect, useRef, useCallback, useState } from 'react'

/**
 * WebSocket hook for real-time metrics with automatic fallback to REST polling
 *
 * @param {boolean} enabled - Whether WebSocket connection should be active
 * @param {Function} onMessage - Callback when message received
 * @param {Function} onError - Callback when error occurs
 * @param {Object} options - Configuration options
 * @returns {Object} Connection state and control functions
 */
export function useWebSocketMetrics(enabled, onMessage, onError, options = {}) {
  const {
    url = null,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    heartbeatInterval = 30000
  } = options

  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const heartbeatTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const [connectionState, setConnectionState] = useState('disconnected') // disconnected, connecting, connected, failed
  const [shouldUseWebSocket, setShouldUseWebSocket] = useState(true)
  const mountedRef = useRef(true)

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current)
      heartbeatTimeoutRef.current = null
    }
  }, [])

  const disconnect = useCallback(() => {
    clearTimers()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [clearTimers])

  const startHeartbeat = useCallback(() => {
    clearTimers()
    heartbeatTimeoutRef.current = setTimeout(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ type: 'ping' }))
          startHeartbeat()
        } catch (error) {
          console.warn('WebSocket heartbeat ping failed:', error)
        }
      }
    }, heartbeatInterval)
  }, [clearTimers, heartbeatInterval])

  const connect = useCallback(() => {
    if (!url || !enabled || !shouldUseWebSocket || !mountedRef.current) {
      return
    }

    if (wsRef.current?.readyState === WebSocket.CONNECTING || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    disconnect()

    try {
      setConnectionState('connecting')
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) {
          ws.close()
          return
        }
        console.log('WebSocket connected to', url)
        setConnectionState('connected')
        reconnectAttemptsRef.current = 0
        startHeartbeat()
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) {
          return
        }
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pong') {
            return
          }
          onMessage?.(data)
        } catch (error) {
          console.error('WebSocket message parse error:', error)
        }
      }

      ws.onerror = (error) => {
        if (!mountedRef.current) {
          return
        }
        console.error('WebSocket error:', error)
        setConnectionState('failed')
        onError?.(error)
      }

      ws.onclose = (event) => {
        if (!mountedRef.current) {
          return
        }
        console.log('WebSocket closed:', event.code, event.reason)
        clearTimers()
        wsRef.current = null

        if (event.code === 1000 || event.code === 1001) {
          setConnectionState('disconnected')
          return
        }

        setConnectionState('disconnected')

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1
          const delay = reconnectInterval * Math.min(reconnectAttemptsRef.current, 3)
          console.log(`WebSocket reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`)

          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current && shouldUseWebSocket) {
              connect()
            }
          }, delay)
        } else {
          console.warn('WebSocket max reconnect attempts reached, falling back to REST polling')
          setConnectionState('failed')
          setShouldUseWebSocket(false)
          onError?.(new Error('WebSocket connection failed after maximum retry attempts'))
        }
      }
    } catch (error) {
      console.error('WebSocket connection error:', error)
      setConnectionState('failed')
      setShouldUseWebSocket(false)
      onError?.(error)
    }
  }, [url, enabled, shouldUseWebSocket, disconnect, startHeartbeat, reconnectInterval, maxReconnectAttempts, onMessage, onError])

  const forceRestFallback = useCallback(() => {
    setShouldUseWebSocket(false)
    disconnect()
    setConnectionState('failed')
  }, [disconnect])

  const retryWebSocket = useCallback(() => {
    reconnectAttemptsRef.current = 0
    setShouldUseWebSocket(true)
    setConnectionState('disconnected')
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [disconnect])

  useEffect(() => {
    if (enabled && shouldUseWebSocket && url) {
      connect()
    } else {
      disconnect()
    }
  }, [enabled, shouldUseWebSocket, url, connect, disconnect])

  return {
    connectionState,
    shouldUseWebSocket,
    isConnected: connectionState === 'connected',
    isConnecting: connectionState === 'connecting',
    isFailed: connectionState === 'failed',
    forceRestFallback,
    retryWebSocket,
    reconnectAttempt: reconnectAttemptsRef.current
  }
}
