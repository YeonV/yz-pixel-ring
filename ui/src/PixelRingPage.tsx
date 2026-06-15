import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  Box, Button, Card, CardContent, Chip, Collapse, Stack, Typography, Alert, ThemeProvider, IconButton, Tooltip, Popover,
} from '@mui/material'
import TuneIcon from '@mui/icons-material/Tune'
import type { Theme } from '@mui/material/styles'
import type { PixelRingApi } from './lib/api'
import type { RingState, RGB } from './types'
import { hexToRgb, rgbToHex } from './lib/color'
import { useRingStream } from './lib/useRingStream'
import { TuningPanel } from './components/TuningPanel'
import { ModeAnimationsPanel } from './components/ModeAnimationsPanel'
import { DisplayControls } from './components/DisplayControls'
import { CalibrateControls } from './components/CalibrateControls'
import { RingPreview } from './components/RingPreview'

export interface WSApi {
  subscribe?: (event: string, cb: (data: unknown) => void) => () => void
}

export interface PixelRingPageProps {
  api: PixelRingApi
  theme?: Theme
  wsApi?: WSApi
  capabilities?: { apiBase?: string }
  /** Hide the logo + title row. Defaults to true in the embeddable IIFE build,
   *  false in the standalone SPA. Pass explicitly to override. */
  embedded?: boolean
}

const MODE_COLORS: Record<string, string> = {
  boot: '#fbbf24', idle: '#475569', listening: '#7dd3fc', thinking: '#f0abfc', speaking: '#86efac',
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      {children}
    </Stack>
  )
}

function Dot({ on, color }: { on: boolean; color: string }) {
  return (
    <Box sx={{
      width: 11, height: 11, borderRadius: '50%',
      bgcolor: on ? color : 'transparent',
      border: `1.5px solid ${on ? color : '#555'}`,
      boxShadow: on ? `0 0 6px ${color}` : 'none',
    }} />
  )
}

export function PixelRingPage({ api, theme, capabilities, embedded }: PixelRingPageProps) {
  const isEmbedded = embedded ?? __YZPR_EMBEDDED__
  const [state, setState] = useState<RingState | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tuningOpen, setTuningOpen] = useState(false)
  const [panel, setPanel] = useState<'display' | 'calibrate' | null>(null)
  const [editLed, setEditLed] = useState<{ index: number; left: number; top: number } | null>(null)

  const live = useRingStream(capabilities?.apiBase ?? '')

  const refresh = useCallback(async () => {
    try { setState(await api.getState()); setErr(null) } catch (e) { setErr(String((e as Error).message)) }
  }, [api])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 1000)   // slow poll for full state; live bits come over /ws
    return () => clearInterval(id)
  }, [refresh])

  const act = useCallback(async (p: Promise<RingState>) => {
    try { setState(await p); setErr(null) } catch (e) { setErr(String((e as Error).message)) }
  }, [])

  // prefer the fast /ws stream for live fields, fall back to the REST snapshot
  const deviceOk = live?.device_ok ?? state?.device_ok ?? false
  const jarvyzConnected = live?.jarvyz_connected ?? state?.jarvyz_connected ?? false
  const ledfxActive = live?.ledfx_active ?? state?.ledfx_active ?? false
  const mode = live?.jarvyz_mode ?? state?.jarvyz_mode
  const doa = live?.doa ?? state?.doa ?? null
  const voice = !!(live?.voice ?? state?.voice)
  const speech = !!(live?.speech ?? state?.speech)
  const effSource = live?.source ?? state?.source
  const activeMode = effSource === 'auto' ? (mode ?? null) : null

  const flip = state?.doa_flip ?? false
  const offset = state?.doa_offset ?? 0
  const doaAngle = doa == null ? null : ((((flip ? -doa : doa) + offset) % 360) + 360) % 360

  const manualActive = (live?.source ?? state?.source) === 'manual'

  // per-LED manual override: edit one LED, keeping the rest of the current frame
  const setLed = (index: number, rgb: RGB) => {
    const cur = live?.leds ?? []
    const frame: RGB[] = Array.from({ length: 12 }, (_, i) => cur[i] ?? [0, 0, 0])
    frame[index] = rgb
    act(api.setLeds(frame))
  }

  // segmented panel: opening "calibrate" lights the aim-dot; leaving it resumes
  const togglePanel = useCallback((p: 'display' | 'calibrate') => {
    const next = panel === p ? null : p
    if (next === 'calibrate') {
      act(api.setEffect({ kind: 'off', doa_track: 'marker', doa_color: [255, 255, 255], doa_intensity: 1 }))
    } else if (panel === 'calibrate') {
      act(api.setFollow(true))
    }
    setPanel(next)
  }, [panel, act, api])

  const inner = (
    <Box sx={{ p: 2, maxWidth: 880, mx: 'auto' }}>
      <Tooltip title="DSP tuning">
        <IconButton
          onClick={() => setTuningOpen(true)}
          sx={{
            position: 'fixed', top: 8, right: 8, zIndex: 1100,
            bgcolor: 'background.paper',
            border: '1px solid', borderColor: 'divider',
            '&:hover': { bgcolor: 'background.paper' },
          }}
        ><TuneIcon /></IconButton>
      </Tooltip>
      {!isEmbedded && (
        <Stack direction="row" alignItems="center" spacing={1.25} sx={{ mb: 1, pr: 5 }}>
          <Box component="img" src="/logo.svg" alt=""
               sx={{ height: 30, width: 'auto', display: 'block' }} />
          <Typography variant="h5">Pixel Ring</Typography>
        </Stack>
      )}
      {err && <Alert severity="warning" sx={{ mb: 1 }}>{err}</Alert>}

      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <Chip size="small" label={deviceOk ? 'ring connected' : 'no ring'} color={deviceOk ? 'success' : 'error'} />
        {ledfxActive && <Chip size="small" label="LedFx streaming" color="secondary" />}
        {jarvyzConnected && <Chip size="small" label="JarvYZ linked" color="success" />}
        {jarvyzConnected && (
          <Chip size="small" label={`mode: ${mode ?? '—'}`}
                sx={{ bgcolor: MODE_COLORS[mode ?? ''] ?? undefined, color: '#000' }} />
        )}
      </Stack>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
        <Card sx={{ width: { xs: '100%', sm: 320 }, flexShrink: 0 }}>
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>Live</Typography>

            <Stack direction="row" spacing={2} alignItems="center">
              <RingPreview leds={live?.leds}
                           rotation={state?.preview_rotation ?? 0}
                           mirror={state?.preview_mirror ?? false}
                           doaAngle={doaAngle}
                           showIndexMarker={panel === 'display'}
                           onLedClick={(i, e) => setEditLed({ index: i, left: e.clientX, top: e.clientY })} />
              <Stack spacing={1.25} sx={{ flex: 1, minWidth: 88 }}>
                <Stat label="DOA">
                  <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                    {doa != null ? `${doa}°` : '—'}
                  </Typography>
                </Stat>
                <Stat label="VOICE"><Dot on={voice} color="#2ecc71" /></Stat>
                <Stat label="SPEECH"><Dot on={speech} color="#3498db" /></Stat>
              </Stack>
            </Stack>

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Tap an LED to recolor it{manualActive ? '' : ' (freezes the ring)'}.
            </Typography>
            {manualActive && (
              <Button size="small" fullWidth variant="text" sx={{ mt: 0.5 }} onClick={() => act(api.setFollow(true))}>
                Resume animations
              </Button>
            )}

            <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
              <Button sx={{ flex: 1 }} size="small" variant={panel === 'display' ? 'contained' : 'outlined'}
                      onClick={() => togglePanel('display')}>Display</Button>
              <Button sx={{ flex: 1 }} size="small" variant={panel === 'calibrate' ? 'contained' : 'outlined'}
                      onClick={() => togglePanel('calibrate')}>Calibrate</Button>
            </Stack>
            <Collapse in={panel === 'display'}><DisplayControls api={api} state={state} act={act} /></Collapse>
            <Collapse in={panel === 'calibrate'}><CalibrateControls api={api} state={state} act={act} /></Collapse>
          </CardContent>
        </Card>

        <ModeAnimationsPanel api={api} state={state} act={act}
                             jarvyzConnected={jarvyzConnected} activeMode={activeMode} />
      </Stack>

      <TuningPanel api={api} open={tuningOpen} onClose={() => setTuningOpen(false)} />

      <Popover open={!!editLed} onClose={() => setEditLed(null)}
               anchorReference="anchorPosition"
               anchorPosition={editLed ? { top: editLed.top, left: editLed.left } : undefined}
               anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        {editLed && (
          <Box sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">LED {editLed.index}</Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
              <input type="color" value={rgbToHex(live?.leds?.[editLed.index] ?? [0, 0, 0])}
                     onChange={(e) => setLed(editLed.index, hexToRgb(e.target.value))}
                     style={{ width: 44, height: 32, border: 'none', background: 'none', cursor: 'pointer' }} />
              <Button size="small" onClick={() => setLed(editLed.index, [0, 0, 0])}>Off</Button>
            </Stack>
          </Box>
        )}
      </Popover>
    </Box>
  )

  return theme ? <ThemeProvider theme={theme}>{inner}</ThemeProvider> : inner
}
