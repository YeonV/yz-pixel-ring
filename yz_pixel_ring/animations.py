"""Pure LED animation engine for the ReSpeaker USB ring (no UI, no USB).

Each function returns a list of 12 ``(r, g, b)`` tuples (0-255). The caller
flattens that to the ring's ``show()`` payload via :func:`to_show_data`.

This is the single source of truth for ring visuals, used by the daemon
(``yz_pixel_ring.daemon``) and the tests.
"""

import math
import colorsys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

N_LEDS = 12
Color = Tuple[int, int, int]

# Classic Google-Assistant arc colors (red / yellow / green / blue).
DEFAULT_PALETTE: List[Color] = [(234, 67, 53), (251, 188, 5), (52, 168, 83), (66, 133, 244)]

CREATIVE = ("rainbow", "comet", "breathe", "wipe", "chase")
ASSISTANT = ("wakeup", "listen", "think", "speak")


def scaled(color: Sequence[float], k: float) -> Color:
    """Scale a color's brightness by k in [0, 1]."""
    k = max(0.0, min(1.0, k))
    return (min(255, int(color[0] * k)), min(255, int(color[1] * k)), min(255, int(color[2] * k)))


def _doa(doa: Optional[float], t: int) -> float:
    """Return the live DOA angle, or a slow sweep when unavailable."""
    return doa if doa is not None else (t * 6) % 360


# ── creative effects ────────────────────────────────────────────────────
def rainbow(t: int, intensity: float) -> List[Color]:
    leds = []
    for i in range(N_LEDS):
        h = ((i / float(N_LEDS)) + t * 0.02) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        leds.append((int(r * 255 * intensity), int(g * 255 * intensity), int(b * 255 * intensity)))
    return leds


def comet(t: int, color: Color, intensity: float) -> List[Color]:
    head = t % N_LEDS
    return [scaled(color, intensity * max(0.0, 1.0 - ((head - i) % N_LEDS) * 0.35)) for i in range(N_LEDS)]


def breathe(t: int, color: Color, intensity: float) -> List[Color]:
    k = (math.sin(t * 0.2) * 0.5 + 0.5) * intensity
    return [scaled(color, k)] * N_LEDS


def wipe(t: int, color: Color, intensity: float) -> List[Color]:
    count = t % (N_LEDS + 1)
    on = scaled(color, intensity)
    return [on if i < count else (0, 0, 0) for i in range(N_LEDS)]


def chase(t: int, color: Color, intensity: float) -> List[Color]:
    on = scaled(color, intensity)
    return [on if (i + t) % 3 == 0 else (0, 0, 0) for i in range(N_LEDS)]


# ── assistant animations (Echo / Google styles, recolorable) ────────────
def echo(name: str, t: int, color: Color, intensity: float, doa: Optional[float] = None) -> List[Color]:
    """Single-color Echo style (cf. the original pattern.Echo)."""
    if name == "wakeup":
        pos = int((_doa(doa, t) + 15) / 30) % N_LEDS
        leds = [scaled(color, 0.12 * intensity)] * N_LEDS
        leds[pos] = scaled(color, intensity)
        leds[(pos + 1) % N_LEDS] = scaled(color, 0.4 * intensity)
        leds[(pos - 1) % N_LEDS] = scaled(color, 0.4 * intensity)
        return leds
    if name == "listen":
        return [scaled(color, 0.6 * intensity)] * N_LEDS
    if name == "think":
        head = t % N_LEDS
        leds = [scaled(color, 0.12 * intensity)] * N_LEDS
        leds[head] = scaled(color, intensity)
        leds[(head - 1) % N_LEDS] = scaled(color, 0.5 * intensity)
        return leds
    # speak: breathing brightness
    k = math.sin(t * 0.25) * 0.5 + 0.5
    return [scaled(color, (0.1 + 0.9 * k) * intensity)] * N_LEDS


def google(name: str, t: int, palette: Sequence[Color], intensity: float, doa: Optional[float] = None) -> List[Color]:
    """Multi-arc Google style (cf. the original pattern.GoogleHome)."""
    anchors = (0, 3, 6, 9)

    def arcs(rot: int, scale: float) -> List[Color]:
        leds = [(0, 0, 0)] * N_LEDS
        for k, a in enumerate(anchors):
            idx = (a + rot) % N_LEDS
            leds[idx] = scaled(palette[k], scale * intensity)
            for off in (1, -1):  # soft glow on neighbours
                j = (idx + off) % N_LEDS
                if leds[j] == (0, 0, 0):
                    leds[j] = scaled(palette[k], scale * intensity * 0.3)
        return leds

    if name == "wakeup":
        return arcs(int((_doa(doa, t) + 90 + 15) / 30) % N_LEDS, 1.0)
    if name == "listen":
        return arcs(0, 0.3 + 0.7 * min(1.0, t / 15.0))  # fade in, then hold
    if name == "think":
        return arcs(t % N_LEDS, 1.0)
    # speak: brightness pulse
    k = math.sin(t * 0.25) * 0.5 + 0.5
    return arcs(0, 0.2 + 0.8 * k)


# ── spec + top-level render ─────────────────────────────────────────────
@dataclass
class RingSpec:
    """What to draw. ``kind`` selects the family; the rest parameterize it."""
    kind: str = "off"            # off | solid | creative | assistant | custom
    name: str = ""               # effect name or assistant state
    style: str = "echo"          # echo | google  (assistant only)
    color: Color = (0, 200, 255)
    palette: Optional[List[Color]] = None
    intensity: float = 0.6       # 0..1
    leds: Optional[List[Color]] = None   # explicit per-LED frame (kind == "custom")
    doa_track: str = "off"       # off | marker | rotate  — point at the speaker
    doa_color: Color = (255, 255, 255)   # marker color when doa_track == "marker"
    doa_intensity: float = 1.0           # marker brightness when doa_track == "marker"


def doa_index(angle: float) -> int:
    """LED index (0..11) nearest the given direction-of-arrival angle."""
    return int((angle + 15) / 30) % N_LEDS


def render(spec: RingSpec, t: int, doa: Optional[float] = None) -> List[Color]:
    """Resolve a spec at frame ``t`` to 12 (r,g,b) tuples, applying any DOA overlay."""
    frame = _base_render(spec, t, doa)
    track = getattr(spec, "doa_track", "off")
    if track != "off" and doa is not None:
        idx = doa_index(doa)
        if track == "rotate":
            # shift the whole pattern so its start aligns with the speaker
            frame = frame[-idx:] + frame[:-idx] if idx else frame
        elif track == "marker":
            # overlay one bright LED at the speaker's angle on top of the base
            frame = list(frame)
            frame[idx] = scaled(spec.doa_color, getattr(spec, "doa_intensity", 1.0))
    return frame


def _base_render(spec: RingSpec, t: int, doa: Optional[float] = None) -> List[Color]:
    """Resolve a spec to a frame, ignoring DOA overlay (handled by render())."""
    if spec.kind == "off":
        return [(0, 0, 0)] * N_LEDS
    if spec.kind == "solid":
        return [scaled(spec.color, spec.intensity)] * N_LEDS
    if spec.kind == "custom":
        leds = list(spec.leds or [])[:N_LEDS]
        return leds + [(0, 0, 0)] * (N_LEDS - len(leds))
    if spec.kind == "creative":
        if spec.name == "rainbow":
            return rainbow(t, spec.intensity)
        if spec.name == "comet":
            return comet(t, spec.color, spec.intensity)
        if spec.name == "breathe":
            return breathe(t, spec.color, spec.intensity)
        if spec.name == "wipe":
            return wipe(t, spec.color, spec.intensity)
        if spec.name == "chase":
            return chase(t, spec.color, spec.intensity)
        return [(0, 0, 0)] * N_LEDS
    if spec.kind == "assistant":
        if spec.style == "google":
            return google(spec.name, t, spec.palette or DEFAULT_PALETTE, spec.intensity, doa)
        return echo(spec.name, t, spec.color, spec.intensity, doa)
    return [(0, 0, 0)] * N_LEDS


def to_show_data(frame: Sequence[Color], gamma: float = 1.0) -> List[int]:
    """Flatten 12 (r,g,b) tuples to the ring's show() payload [r,g,b,0]*12.

    gamma > 1.0 applies perceptual gamma correction (out = (in/255)**gamma * 255),
    smoothing low-brightness fades. gamma == 1.0 is linear (no change).
    """
    data: List[int] = []
    for r, g, b in frame:
        if gamma != 1.0:
            r = round((max(0, min(255, r)) / 255.0) ** gamma * 255)
            g = round((max(0, min(255, g)) / 255.0) ** gamma * 255)
            b = round((max(0, min(255, b)) / 255.0) ** gamma * 255)
        data += [int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF, 0]
    return data
