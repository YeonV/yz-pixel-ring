import type { RGB, RingState, TuningParam, ManualSpec } from '../types'

export interface EffectSpec {
  kind: string
  name?: string
  style?: string
  color?: RGB
  palette?: RGB[] | null
  intensity?: number
  doa_track?: string
  doa_color?: RGB
  doa_intensity?: number
}

export interface PixelRingApi {
  getState(): Promise<RingState>
  setMode(state: string): Promise<RingState>
  setFollow(enabled: boolean): Promise<RingState>
  setEffect(spec: EffectSpec): Promise<RingState>
  setColor(r: number, g: number, b: number, intensity?: number): Promise<RingState>
  off(): Promise<RingState>
  setLeds(leds: RGB[]): Promise<RingState>
  listTuning(): Promise<TuningParam[]>
  setTuning(name: string, value: number): Promise<TuningParam>
  getModes(): Promise<Record<string, ManualSpec>>
  setModeSpec(mode: string, spec: EffectSpec): Promise<ManualSpec>
  resetModes(): Promise<Record<string, ManualSpec>>
  setDoaOffset(value: number, flip?: boolean): Promise<RingState>
  setGamma(value: number): Promise<RingState>
  setPreview(rotation: number, mirror: boolean): Promise<RingState>
}

/**
 * REST client for the pixel-ring daemon.
 * apiBase: '' for same-origin (served by the daemon), or e.g.
 * 'http://127.0.0.1:9700' for dev / JarvYZ-embedded use.
 */
export function createPixelRingApi({ apiBase = '' }: { apiBase?: string } = {}): PixelRingApi {
  async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${apiBase}${path}`, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail ?? detail
      } catch {
        /* ignore */
      }
      throw new Error(`${res.status}: ${detail}`)
    }
    return res.json() as Promise<T>
  }

  return {
    getState: () => req<RingState>('GET', '/state'),
    setMode: (state) => req<RingState>('POST', '/mode', { state }),
    setFollow: (enabled) => req<RingState>('POST', '/follow', { enabled }),
    setEffect: (spec) => req<RingState>('POST', '/effect', spec),
    setColor: (r, g, b, intensity = 1.0) => req<RingState>('POST', '/color', { r, g, b, intensity }),
    off: () => req<RingState>('POST', '/off'),
    setLeds: (leds) => req<RingState>('POST', '/leds', { leds }),
    listTuning: () => req<{ params: TuningParam[] }>('GET', '/tuning').then((d) => d.params),
    setTuning: (name, value) => req<TuningParam>('POST', `/tuning/${name}`, { value }),
    getModes: () => req<Record<string, ManualSpec>>('GET', '/modes'),
    setModeSpec: (mode, spec) => req<ManualSpec>('PUT', `/modes/${mode}`, spec),
    resetModes: () => req<Record<string, ManualSpec>>('POST', '/modes/reset'),
    setDoaOffset: (value, flip = false) => req<RingState>('POST', '/doa_offset', { value, flip }),
    setGamma: (value) => req<RingState>('POST', '/gamma', { value }),
    setPreview: (rotation, mirror) => req<RingState>('POST', '/preview', { rotation, mirror }),
  }
}
