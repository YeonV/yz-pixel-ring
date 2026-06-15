import { useState } from 'react'
import { Slider, Stack, Switch, FormControlLabel, Typography } from '@mui/material'
import type { PixelRingApi } from '../lib/api'
import type { RingState } from '../types'

/** Appearance controls: preview orientation (rotate/mirror the on-screen ring to
 *  match the real device — display-only) + gamma (output brightness curve). */
export function DisplayControls({ api, state, act }: {
  api: PixelRingApi
  state: RingState | null
  act: (p: Promise<RingState>) => void
}) {
  const [rotLocal, setRotLocal] = useState<number | null>(null)
  const [gamLocal, setGamLocal] = useState<number | null>(null)
  const rotation = rotLocal ?? state?.preview_rotation ?? 0
  const mirror = state?.preview_mirror ?? false
  const gamma = gamLocal ?? state?.gamma ?? 1

  return (
    <Stack spacing={0.5} sx={{ pt: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Rotate/mirror the preview to match the real device.</Typography>
      <Typography variant="caption">Rotation {rotation}°</Typography>
      <Slider size="small" min={0} max={359} value={rotation}
              onChange={(_, v) => setRotLocal(v as number)}
              onChangeCommitted={(_, v) => act(api.setPreview(v as number, mirror))} />
      <FormControlLabel
        control={<Switch size="small" checked={mirror} onChange={(e) => act(api.setPreview(rotation, e.target.checked))} />}
        label={<Typography variant="caption">mirror direction</Typography>} />

      <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
        Gamma {gamma.toFixed(1)}{gamma === 1 ? ' (off)' : ''}
      </Typography>
      <Slider size="small" min={1} max={3} step={0.1} value={gamma}
              onChange={(_, v) => setGamLocal(v as number)}
              onChangeCommitted={(_, v) => act(api.setGamma(v as number))} />
    </Stack>
  )
}
