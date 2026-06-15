import { useEffect, useRef, useState } from 'react'
import type { RGB } from '../types'

export interface RingStream {
  leds: RGB[]
  doa: number | null
  voice: number
  speech: number
  jarvyz_mode: string
  jarvyz_connected: boolean
  device_ok: boolean
  ledfx_active: boolean
  source: string
}

function wsUrlFor(apiBase: string): string {
  if (apiBase) return apiBase.replace(/^http/, 'ws') + '/ws'
  const proto = typeof location !== 'undefined' && location.protocol === 'https:' ? 'wss' : 'ws'
  const host = typeof location !== 'undefined' ? location.host : '127.0.0.1:9700'
  return `${proto}://${host}/ws`
}

/** Live ~20fps frame + state stream from the daemon's /ws. Auto-reconnects. */
export function useRingStream(apiBase: string): RingStream | null {
  const [data, setData] = useState<RingStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let closed = false
    let retry: ReturnType<typeof setTimeout> | undefined
    const url = wsUrlFor(apiBase)

    const connect = () => {
      if (closed) return
      const ws = new WebSocket(url)
      wsRef.current = ws
      ws.onmessage = (e) => {
        try { setData(JSON.parse(e.data)) } catch { /* ignore */ }
      }
      ws.onclose = () => { if (!closed) retry = setTimeout(connect, 1500) }
      ws.onerror = () => { try { ws.close() } catch { /* ignore */ } }
    }
    connect()

    return () => {
      closed = true
      if (retry) clearTimeout(retry)
      try { wsRef.current?.close() } catch { /* ignore */ }
    }
  }, [apiBase])

  return data
}
