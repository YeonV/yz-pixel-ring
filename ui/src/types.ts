export type RGB = [number, number, number]

export interface ManualSpec {
  kind: string // off | solid | creative | assistant
  name: string
  style: string // echo | google
  color: RGB
  palette: RGB[] | null
  intensity: number
  doa_track: string // off | marker | rotate
  doa_color: RGB
  doa_intensity: number
}

export interface RingState {
  device_ok: boolean
  source: 'auto' | 'manual'
  jarvyz_connected: boolean
  jarvyz_mode: string
  doa: number | null
  doa_offset: number
  doa_flip: boolean
  gamma: number
  preview_rotation: number
  preview_mirror: boolean
  voice: number
  speech: number
  ledfx_active: boolean
  manual: ManualSpec
}

export interface TuningParam {
  name: string
  type: 'int' | 'float'
  min: number
  max: number
  access: 'rw' | 'ro'
  description: string
  value: number | null
}

export const MODES = ['boot', 'idle', 'listening', 'thinking', 'speaking'] as const
export const ASSISTANT = ['wakeup', 'listen', 'think', 'speak'] as const
export const CREATIVE = ['rainbow', 'comet', 'breathe', 'wipe', 'chase'] as const
