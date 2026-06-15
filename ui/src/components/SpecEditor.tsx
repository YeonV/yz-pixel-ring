import {
  ToggleButton, ToggleButtonGroup, Select, MenuItem, Slider, Stack, Typography, Box,
} from '@mui/material'
import type { ManualSpec, RGB } from '../types'
import { ASSISTANT, CREATIVE } from '../types'
import { hexToRgb, rgbToHex } from '../lib/color'

const DEFAULT_PALETTE: RGB[] = [[234, 67, 53], [251, 188, 5], [52, 168, 83], [66, 133, 244]]

function Swatch({ rgb, onChange }: { rgb: RGB; onChange: (v: RGB) => void }) {
  return (
    <input type="color" value={rgbToHex(rgb)} onChange={(e) => onChange(hexToRgb(e.target.value))}
           style={{ width: 34, height: 28, border: 'none', background: 'none', cursor: 'pointer' }} />
  )
}

/** Edits a ManualSpec (kind/style/name/color/palette/intensity). */
export function SpecEditor({ spec, onChange }: { spec: ManualSpec; onChange: (s: ManualSpec) => void }) {
  const up = (p: Partial<ManualSpec>) => onChange({ ...spec, ...p })
  const palette = spec.palette ?? DEFAULT_PALETTE

  return (
    <Stack spacing={1.5}>
      <ToggleButtonGroup size="small" exclusive value={spec.kind} onChange={(_, v) => v && up({ kind: v })}>
        <ToggleButton value="off">off</ToggleButton>
        <ToggleButton value="solid">solid</ToggleButton>
        <ToggleButton value="creative">creative</ToggleButton>
        <ToggleButton value="assistant">assistant</ToggleButton>
      </ToggleButtonGroup>

      {spec.kind === 'assistant' && (
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <ToggleButtonGroup size="small" exclusive value={spec.style}
            onChange={(_, v) => v && up(v === 'google' && !spec.palette ? { style: v, palette } : { style: v })}>
            <ToggleButton value="echo">Echo</ToggleButton>
            <ToggleButton value="google">Google</ToggleButton>
          </ToggleButtonGroup>
          <Select size="small" value={(ASSISTANT as readonly string[]).includes(spec.name) ? spec.name : 'wakeup'}
                  onChange={(e) => up({ name: e.target.value })}>
            {ASSISTANT.map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
          </Select>
          {spec.style === 'google'
            ? <Stack direction="row" spacing={0.5}>{palette.map((c, i) => (
                <Swatch key={i} rgb={c} onChange={(v) => up({ palette: palette.map((x, j) => (j === i ? v : x)) })} />))}
              </Stack>
            : <Swatch rgb={spec.color} onChange={(v) => up({ color: v })} />}
        </Stack>
      )}

      {spec.kind === 'creative' && (
        <Stack direction="row" spacing={1} alignItems="center">
          <Select size="small" value={(CREATIVE as readonly string[]).includes(spec.name) ? spec.name : 'rainbow'}
                  onChange={(e) => up({ name: e.target.value })}>
            {CREATIVE.map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
          </Select>
          <Swatch rgb={spec.color} onChange={(v) => up({ color: v })} />
        </Stack>
      )}

      {spec.kind === 'solid' && <Swatch rgb={spec.color} onChange={(v) => up({ color: v })} />}

      {spec.kind !== 'off' && (
        <>
          <Box>
            <Typography variant="caption" color="text.secondary">Intensity</Typography>
            <Slider size="small" min={0} max={1} step={0.05} value={spec.intensity}
                    onChange={(_, v) => up({ intensity: v as number })} />
          </Box>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Typography variant="caption" color="text.secondary">Point at speaker</Typography>
            <ToggleButtonGroup size="small" exclusive value={spec.doa_track ?? 'off'}
              onChange={(_, v) => v && up({ doa_track: v })}>
              <ToggleButton value="off">off</ToggleButton>
              <ToggleButton value="marker">dot</ToggleButton>
              <ToggleButton value="rotate">rotate</ToggleButton>
            </ToggleButtonGroup>
            {spec.doa_track === 'marker' && (
              <Swatch rgb={spec.doa_color ?? [255, 255, 255]} onChange={(v) => up({ doa_color: v })} />
            )}
          </Stack>
          {spec.doa_track === 'marker' && (
            <Box>
              <Typography variant="caption" color="text.secondary">Dot intensity</Typography>
              <Slider size="small" min={0} max={1} step={0.05} value={spec.doa_intensity ?? 1}
                      onChange={(_, v) => up({ doa_intensity: v as number })} />
            </Box>
          )}
        </>
      )}
    </Stack>
  )
}
