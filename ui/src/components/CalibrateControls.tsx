import { useState } from 'react'
import { Slider, Stack, Switch, FormControlLabel, Typography } from '@mui/material'
import type { PixelRingApi } from '../lib/api'
import type { RingState } from '../types'

/** DOA→LED calibration: offset + reverse. A live white aim-dot is lit by the
 *  parent while this panel is open. Persisted in the daemon. */
export function CalibrateControls({ api, state, act }: {
  api: PixelRingApi
  state: RingState | null
  act: (p: Promise<RingState>) => void
}) {
  const [local, setLocal] = useState<number | null>(null)
  const offset = local ?? state?.doa_offset ?? 0
  const flip = state?.doa_flip ?? false
  const send = (o: number, f: boolean) => act(api.setDoaOffset(o, f))

  return (
    <Stack spacing={0.5} sx={{ pt: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Talk from a known spot, then dial until the white dot points at you.</Typography>
      <Typography variant="caption">Offset {offset}°</Typography>
      <Slider size="small" min={0} max={359} value={offset}
              onChange={(_, v) => setLocal(v as number)}
              onChangeCommitted={(_, v) => send(v as number, flip)} />
      <FormControlLabel
        control={<Switch size="small" checked={flip} onChange={(e) => send(offset, e.target.checked)} />}
        label={<Typography variant="caption">reverse direction</Typography>} />
    </Stack>
  )
}
