import type { RGB } from '../types'

/** Live 12-LED preview filled from the daemon's actual current frame, with a
 *  center needle showing the live DOA direction. rotation + mirror are
 *  display-only, to orient the drawing to match the physical device. The needle
 *  uses the same orientation so it points at the lit direction LED. The dashed
 *  ring marks LED index 0. `doaAngle` is the offset/flip-adjusted angle. */
export function RingPreview({
  leds, rotation = 0, mirror = false, doaAngle = null, showIndexMarker = false, size = 184, onLedClick,
}: {
  leds?: RGB[] | null; rotation?: number; mirror?: boolean; doaAngle?: number | null
  showIndexMarker?: boolean; size?: number
  onLedClick?: (index: number, e: { clientX: number; clientY: number }) => void
}) {
  const n = 12
  const c = size / 2
  const radius = size / 2 - 18
  const dotR = 11
  const rot = (rotation * Math.PI) / 180
  const dir = mirror ? -1 : 1
  const needleAng = doaAngle == null ? null : -Math.PI / 2 + rot + dir * (doaAngle * Math.PI) / 180
  const needleLen = radius * 0.55   // stays well clear of the LED dots
  return (
    <svg width={size} height={size}>
      <circle cx={c} cy={c} r={size / 2 - 3} fill="#0a0a0a" stroke="#222" />
      {Array.from({ length: n }, (_, i) => {
        const ang = -Math.PI / 2 + rot + dir * (i / n) * 2 * Math.PI
        const x = c + radius * Math.cos(ang)
        const y = c + radius * Math.sin(ang)
        const px = leds?.[i] ?? [0, 0, 0]
        const fill = `rgb(${px[0]},${px[1]},${px[2]})`
        const lit = px[0] + px[1] + px[2] > 8
        return (
          <g key={i}
             onClick={onLedClick ? (e) => onLedClick(i, e) : undefined}
             style={{ cursor: onLedClick ? 'pointer' : 'default' }}>
            {onLedClick && <circle cx={x} cy={y} r={dotR + 5} fill="transparent" />}
            <circle cx={x} cy={y} r={dotR} fill={fill}
                    stroke={lit ? fill : 'none'} strokeWidth={1}
                    style={{ filter: lit ? `drop-shadow(0 0 6px ${fill})` : 'none' }} />
            {i === 0 && showIndexMarker && <circle cx={x} cy={y} r={dotR + 3} fill="none" stroke="#888" strokeWidth={1} strokeDasharray="2 2" />}
          </g>
        )
      })}
      {needleAng != null && (
        <line x1={c} y1={c}
              x2={c + needleLen * Math.cos(needleAng)} y2={c + needleLen * Math.sin(needleAng)}
              stroke="#2e8b57" strokeWidth={3} strokeLinecap="round" />
      )}
      <circle cx={c} cy={c} r={3.5} fill="#2e8b57" opacity={needleAng != null ? 1 : 0.3} />
    </svg>
  )
}
