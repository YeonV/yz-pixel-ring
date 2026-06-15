import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Card, CardContent, IconButton, Accordion, AccordionSummary, AccordionDetails,
  Typography, Stack, Box, Alert, Tooltip, Switch, FormControlLabel, Divider,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RestartAltIcon from '@mui/icons-material/RestartAlt'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import type { PixelRingApi } from '../lib/api'
import type { ManualSpec, RingState } from '../types'
import { MODES } from '../types'
import { SpecEditor } from './SpecEditor'

const MODE_COLORS: Record<string, string> = {
  boot: '#fbbf24', idle: '#475569', listening: '#7dd3fc', thinking: '#f0abfc', speaking: '#86efac',
}

export function ModeAnimationsPanel({ api, state, act, jarvyzConnected, activeMode }: {
  api: PixelRingApi
  state: RingState | null
  act: (p: Promise<RingState>) => void
  jarvyzConnected: boolean
  activeMode: string | null
}) {
  const [specs, setSpecs] = useState<Record<string, ManualSpec> | null>(null)
  const [manual, setManual] = useState<ManualSpec | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | false>(false)
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const load = useCallback(async () => {
    try { setSpecs(await api.getModes()); setErr(null) } catch (e) { setErr(String((e as Error).message)) }
  }, [api])
  useEffect(() => { load() }, [load])

  useEffect(() => { if (!manual && state?.manual) setManual(state.manual) }, [manual, state])

  const saveMode = useCallback((mode: string, spec: ManualSpec) => {
    setSpecs((s) => (s ? { ...s, [mode]: spec } : s))
    clearTimeout(timers.current[mode])
    timers.current[mode] = setTimeout(async () => {
      try { await api.setModeSpec(mode, spec); setErr(null) } catch (e) { setErr(String((e as Error).message)) }
    }, 350)
  }, [api])

  const saveManual = useCallback((spec: ManualSpec) => {
    setManual(spec)
    clearTimeout(timers.current.__manual)
    timers.current.__manual = setTimeout(() => act(api.setEffect(spec)), 250)
  }, [api, act])

  const preview = useCallback(async (mode: string) => {
    try { await api.setFollow(true); await api.setMode(mode); setErr(null) } catch (e) { setErr(String((e as Error).message)) }
  }, [api])

  const resetAll = useCallback(async () => {
    try { setSpecs(await api.resetModes()); setErr(null) } catch (e) { setErr(String((e as Error).message)) }
  }, [api])

  const rowSx = (live: boolean) => ({
    borderRadius: 1.5, mb: 0.5,
    bgcolor: live ? 'action.selected' : 'action.hover',
    '&:before': { display: 'none' },
  })
  const summarySx = { minHeight: 44, '& .MuiAccordionSummary-content': { alignItems: 'center', my: 0 } }

  return (
    <Card sx={{ flex: 1, minWidth: 0, width: '100%' }}>
      <CardContent>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
          <Typography variant="subtitle2">Mode animations</Typography>
          <Box sx={{ flex: 1 }} />
          {jarvyzConnected && (
            <FormControlLabel sx={{ mr: 0 }}
              control={<Switch size="small" checked={state?.source === 'auto'} onChange={(e) => act(api.setFollow(e.target.checked))} />}
              label={<Typography variant="caption">Follow JarvYZ</Typography>} />
          )}
          <Tooltip title="Reset all modes to defaults">
            <IconButton size="small" onClick={resetAll}><RestartAltIcon fontSize="small" /></IconButton>
          </Tooltip>
        </Stack>
        {err && <Alert severity="warning" sx={{ mb: 1 }}>{err}</Alert>}

        {specs && MODES.map((m) => {
          const live = activeMode === m
          const color = MODE_COLORS[m]
          return (
            <Accordion key={m} disableGutters elevation={0} expanded={expanded === m}
                       onChange={(_, x) => setExpanded(x ? m : false)} sx={rowSx(live)}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={summarySx}>
                <Box sx={{ width: 11, height: 11, borderRadius: '50%', bgcolor: color, mr: 1.5,
                           boxShadow: live ? `0 0 8px ${color}` : 'none' }} />
                <Typography variant="body2" sx={{ textTransform: 'capitalize', fontWeight: live ? 600 : 400 }}>{m}</Typography>
                {live && <Typography variant="caption" sx={{ ml: 1, color }}>live</Typography>}
                <Box sx={{ flex: 1 }} />
                <Tooltip title="Preview on ring">
                  <IconButton component="span" size="small" sx={{ mr: 0.5 }}
                              onClick={(e) => { e.stopPropagation(); preview(m) }}>
                    <PlayArrowIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0 }}>
                <SpecEditor spec={specs[m]} onChange={(s) => saveMode(m, s)} />
              </AccordionDetails>
            </Accordion>
          )
        })}

        <Divider sx={{ my: 1 }} />
        <Accordion disableGutters elevation={0} expanded={expanded === '__manual'}
                   onChange={(_, x) => setExpanded(x ? '__manual' : false)}
                   sx={{ bgcolor: 'transparent', '&:before': { display: 'none' } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={summarySx}>
            <Typography variant="body2">Manual override</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Stack spacing={1}>
              {manual && <SpecEditor spec={manual} onChange={saveManual} />}
              <Typography variant="caption" color="text.secondary">
                Editing here switches the ring to manual until you re-enable Follow.
              </Typography>
            </Stack>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  )
}
