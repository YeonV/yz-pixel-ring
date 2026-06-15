"""USB LED control for the ReSpeaker USB Mic Array v2.0 (XVSR3000), 0x2886:0x0018.

Every LED command is a single USB vendor control-OUT transfer:

    ctrl_transfer(CTRL_OUT | VENDOR | DEVICE, 0, <command>, 0x1C, <payload>, timeout)

Command set (documented in docs/respeaker-usb-mic-array.md):

    0     trace            [0]
    1     solid colour     [r, g, b, 0]
    2     listen           [0]              (alias: wakeup)
    3     speak            [0]
    4     think            [0]              (alias: wait)
    5     spin             [0]
    6     per-LED frame    [r, g, b, 0] x 12
    0x20  brightness       [0..31]
    0x21  palette          [r, g, b, 0, r, g, b, 0]
    0x22  centre VAD LED   [state]
    0x23  volume / VU      [0..12]

Implemented from the published protocol; no upstream source is reused.
"""
from __future__ import annotations

import usb.core
import usb.util

VID = 0x2886
PID = 0x0018

# command codes
_TRACE, _SOLID, _LISTEN, _SPEAK, _THINK, _SPIN, _SHOW = 0, 1, 2, 3, 4, 5, 6
_BRIGHTNESS, _PALETTE, _VAD_LED, _VOLUME = 0x20, 0x21, 0x22, 0x23


def _rgb_bytes(color: int) -> list:
    """0xRRGGBB int -> the device's [r, g, b, 0] payload."""
    return [(color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF, 0]


class PixelRing:
    """Drives the 12-LED ring over the device's vendor control interface."""

    TIMEOUT = 8000

    def __init__(self, dev):
        self.dev = dev

    def _send(self, command: int, payload=(0,)) -> None:
        self.dev.ctrl_transfer(
            usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
            0, command, 0x1C, list(payload), self.TIMEOUT,
        )

    # ── firmware animations ──────────────────────────────────────────────
    def trace(self) -> None:
        self._send(_TRACE)

    def listen(self, direction=None) -> None:
        self._send(_LISTEN)

    wakeup = listen

    def speak(self) -> None:
        self._send(_SPEAK)

    def think(self) -> None:
        self._send(_THINK)

    wait = think

    def spin(self) -> None:
        self._send(_SPIN)

    # ── colours ──────────────────────────────────────────────────────────
    def mono(self, color: int) -> None:
        self._send(_SOLID, _rgb_bytes(color))

    def set_color(self, rgb: int | None = None, r: int = 0, g: int = 0, b: int = 0) -> None:
        self._send(_SOLID, _rgb_bytes(rgb) if rgb else [r, g, b, 0])

    def off(self) -> None:
        self.mono(0)

    def show(self, data) -> None:
        """Set every LED individually; data is a flat [r, g, b, 0] x 12 list."""
        self._send(_SHOW, data)

    customize = show

    def set_palette(self, a: int, b: int) -> None:
        self._send(_PALETTE, _rgb_bytes(a) + _rgb_bytes(b))

    set_color_palette = set_palette

    # ── levels ───────────────────────────────────────────────────────────
    def set_brightness(self, brightness: int) -> None:
        self._send(_BRIGHTNESS, [brightness])

    def set_volume(self, volume: int) -> None:
        self._send(_VOLUME, [volume])

    def set_vad_led(self, state: int) -> None:
        self._send(_VAD_LED, [state])

    def write(self, command: int, data=(0,)) -> None:
        """Raw command escape hatch."""
        self._send(command, data)

    def close(self) -> None:
        usb.util.dispose_resources(self.dev)


def find(vid: int = VID, pid: int = PID):
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    return PixelRing(dev) if dev is not None else None
