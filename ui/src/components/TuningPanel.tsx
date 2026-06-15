import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Dialog, DialogTitle, DialogContent, IconButton, Accordion, AccordionSummary, AccordionDetails,
  Typography, Switch, Slider, TextField, Stack, Chip, Tooltip, CircularProgress, Alert, Box,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RefreshIcon from '@mui/icons-material/Refresh'
import CloseIcon from '@mui/icons-material/Close'
import type { PixelRingApi } from '../lib/api'
import type { TuningParam } from '../types'

const CATEGORIES: { title: string; match: (n: string) => boolean }[] = [
  { title: 'Gain (AGC)', match: (n) => n.startsWith('AGC') },
  {
    title: 'Echo cancellation',
    match: (n) =>
      n.startsWith('AEC') || n.startsWith('ECHO') || n.startsWith('GAMMA_E') ||
      n.startsWith('NL') || n.startsWith('RT60') || n === 'CNIONOFF' || n === 'TRANSIENTONOFF',
  },
  { title: 'Noise suppression', match: (n) => n.includes('NOISE') || n.startsWith('GAMMA_N') || n.startsWith('MINN') },
  {
    title: 'Voice / DOA / beamformer',
    match: (n) =>
      n.startsWith('VOICE') || n.startsWith('SPEECH') || n.startsWith('GAMMAVAD') ||
      n.startsWith('DOA') || n.startsWith('FREEZE') || n.startsWith('FSB'),
  },
  { title: 'Filters & misc', match: () => true },
]

function categorize(params: TuningParam[]) {
  const groups = CATEGORIES.map((c) => ({ title: c.title, items: [] as TuningParam[] }))
  for (const p of params) groups[CATEGORIES.findIndex((c) => c.match(p.name))].items.push(p)
  return groups.filter((g) => g.items.length)
}

function Row({ name, desc, children }: { name: string; desc: string; children: ReactNode }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2} sx={{ py: 0.5 }}>
      <Tooltip title={desc} placement="top-start">
        <Typography variant="body2" sx={{ fontFamily: 'monospace', cursor: 'help' }}>{name}</Typography>
      </Tooltip>
      <Box sx={{ flexShrink: 0 }}>{children}</Box>
    </Stack>
  )
}

function TuningRow({ param, onWrite }: { param: TuningParam; onWrite: (name: string, value: number) => void }) {
  const [val, setVal] = useState<number>(param.value ?? param.min)
  useEffect(() => { setVal(param.value ?? param.min) }, [param.value])

  if (param.access === 'ro') {
    return <Row name={param.name} desc={param.description}><Chip size="small" label={String(param.value ?? '—')} /></Row>
  }
  if (param.type === 'int' && param.min === 0 && param.max === 1) {
    return (
      <Row name={param.name} desc={param.description}>
        <Switch size="small" checked={!!param.value} onChange={(e) => onWrite(param.name, e.target.checked ? 1 : 0)} />
      </Row>
    )
  }
  const step = param.type === 'int' ? 1 : (param.max - param.min) / 100 || 0.01
  return (
    <Row name={param.name} desc={param.description}>
      <Stack direction="row" spacing={1.5} alignItems="center">
        <Slider size="small" min={param.min} max={param.max} step={step} value={val}
                onChange={(_, v) => setVal(v as number)}
                onChangeCommitted={(_, v) => onWrite(param.name, v as number)} sx={{ width: 130 }} />
        <TextField size="small" type="number" value={val}
                   onChange={(e) => setVal(Number(e.target.value))}
                   onKeyDown={(e) => { if (e.key === 'Enter') onWrite(param.name, val) }}
                   onBlur={() => onWrite(param.name, val)} sx={{ width: 96 }} />
      </Stack>
    </Row>
  )
}

export function TuningPanel({ api, open, onClose }: { api: PixelRingApi; open: boolean; onClose: () => void }) {
  const [params, setParams] = useState<TuningParam[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try { setParams(await api.listTuning()); setErr(null) }
    catch (e) { setErr(String((e as Error).message)) }
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { if (open) load() }, [open, load])

  const write = useCallback(async (name: string, value: number) => {
    try {
      const updated = await api.setTuning(name, value)
      setParams((ps) => (ps ? ps.map((p) => (p.name === name ? updated : p)) : ps))
      setErr(null)
    } catch (e) { setErr(String((e as Error).message)) }
  }, [api])

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        DSP Tuning
        <Box sx={{ flex: 1 }} />
        <Tooltip title="Re-read all values"><IconButton size="small" onClick={load}><RefreshIcon fontSize="small" /></IconButton></Tooltip>
        <IconButton size="small" onClick={onClose}><CloseIcon fontSize="small" /></IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {err && <Alert severity="warning" sx={{ mb: 1 }}>{err}</Alert>}
        {loading && !params && <Stack alignItems="center" sx={{ py: 4 }}><CircularProgress /></Stack>}
        {params && categorize(params).map((g) => (
          <Accordion key={g.title} defaultExpanded={g.title.startsWith('Voice')} disableGutters>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">{g.title}</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>({g.items.length})</Typography>
            </AccordionSummary>
            <AccordionDetails>
              {g.items.map((p) => <TuningRow key={p.name} param={p} onWrite={write} />)}
            </AccordionDetails>
          </Accordion>
        ))}
      </DialogContent>
    </Dialog>
  )
}
