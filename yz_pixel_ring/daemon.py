#!/usr/bin/env python
"""Headless ReSpeaker ring daemon.

Owns the USB ring (0x2886:0x0018) and drives it from two input sources at once:

  • JarvYZ mode  — connects to the assistant's WebSocket (ws://127.0.0.1:8765/ws),
                   reads `mode` frames (idle/listening/thinking/speaking/boot),
                   and animates the ring to match. Reconnects forever; just
                   shows idle / manual when JarvYZ is down.
  • REST API     — manual control + state readout (color, effect, override,
                   live DOA/VAD). Always available, JarvYZ or not.

Independent of JarvYZ: the assistant needs zero changes; this is purely a
consumer of its public `mode` broadcast. Run it as a login/startup task so the
ring is an always-on ambient indicator.

Usage:
    uv run yz-pixel-ring                 # follow JarvYZ + serve REST
    uv run yz-pixel-ring --no-jarvyz     # manual/REST only
    RING_DAEMON_PORT=9700 JARVYZ_WS_URL=ws://host:8765/ws uv run yz-pixel-ring
    # equivalently: python -m yz_pixel_ring

Only ONE process may own the ring's control interface.
"""

import argparse
import asyncio
import dataclasses
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

import usb.core

from yz_pixel_ring import animations as fx
from yz_pixel_ring.led import PixelRing
from yz_pixel_ring.tuning import Tuning, PARAMETERS

VID, PID = 0x2886, 0x0018

# Per-mode customizations + daemon config persist here (survive restarts + updates).
CONFIG_DIR = Path.home() / ".yz-pixel-ring"
MODES_FILE = CONFIG_DIR / "modes.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default JarvYZ logical mode → ring animation (a dim-red ambient theme).
DEFAULT_MODE_SPECS = {
    "boot":      fx.RingSpec(kind="assistant", name="think",  style="echo", color=(251, 188, 36), intensity=0.7),
    "idle":      fx.RingSpec(kind="assistant", name="wakeup", style="echo", color=(255, 0, 0), intensity=0.0,
                             doa_track="marker", doa_color=(31, 0, 0), doa_intensity=0.05),
    "listening": fx.RingSpec(kind="creative", name="breathe", style="echo", color=(224, 0, 0), intensity=0.15,
                             doa_track="marker", doa_color=(255, 0, 0), doa_intensity=1.0),
    "thinking":  fx.RingSpec(kind="assistant", name="think",  style="echo", color=(255, 0, 0), intensity=0.1,
                             doa_track="off", doa_color=(255, 0, 0), doa_intensity=0.35),
    "speaking":  fx.RingSpec(kind="assistant", name="speak",  style="echo", color=(255, 0, 0), intensity=0.85),
}


def spec_from_dict(d: dict) -> fx.RingSpec:
    return fx.RingSpec(
        kind=d.get("kind", "off"),
        name=d.get("name", ""),
        style=d.get("style", "echo"),
        color=tuple(d["color"]) if d.get("color") else (0, 200, 255),
        palette=[tuple(c) for c in d["palette"]] if d.get("palette") else None,
        intensity=float(d.get("intensity", 0.6)),
        doa_track=d.get("doa_track", "off"),
        doa_color=tuple(d["doa_color"]) if d.get("doa_color") else (255, 255, 255),
        doa_intensity=float(d.get("doa_intensity", 1.0)),
        leds=[tuple(c) for c in d["leds"]] if d.get("leds") else None,
    )


def spec_to_dict(spec: fx.RingSpec) -> dict:
    return dataclasses.asdict(spec)


class RingController:
    """Owns the USB device and runs the frame loop. The ONLY thread that touches
    USB — other threads just mutate desired state, which this loop reads."""

    FRAME_MS = 50          # ~20 fps
    DOA_EVERY = 4          # read DOA/VAD every N frames (~200 ms)
    REOPEN_EVERY_S = 2.0
    LEDFX_TIMEOUT = 1.0    # treat LedFx as inactive this long after last DDP frame

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usb_lock = threading.Lock()          # serializes all USB access
        # desired state
        self.source = "auto"                       # auto = follow JarvYZ, manual = manual_spec
        self.jarvyz_mode = "idle"
        self.jarvyz_connected = False
        self.manual_spec = fx.RingSpec(kind="off")
        self._mode_specs = self._load_modes()      # JarvYZ mode -> RingSpec (customizable)
        (self.doa_offset, self.doa_flip, self.gamma,
         self.preview_rotation, self.preview_mirror) = self._load_config()
        # live state
        self.device_ok = False
        self.doa: Optional[int] = None
        self.voice = 0
        self.speech = 0
        self.last_frame = [(0, 0, 0)] * fx.N_LEDS   # most recent rendered frame (pre-gamma)
        self.last_source = "auto"                    # source that produced last_frame
        # LedFx (DDP) input source — highest priority while frames are arriving
        self.ledfx_frame: Optional[list] = None
        self.ledfx_ts = 0.0
        # internals
        self._ring: Optional[PixelRing] = None
        self._tuning: Optional[Tuning] = None
        self._t = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ---- device ----------------------------------------------------------
    def _open(self) -> bool:
        try:
            dev = usb.core.find(idVendor=VID, idProduct=PID)
            if dev is None:
                return False
            self._ring = PixelRing(dev)
            self._tuning = Tuning(dev)
            self.device_ok = True
            return True
        except Exception:
            self.device_ok = False
            return False

    def _close(self) -> None:
        try:
            if self._ring is not None:
                self._ring.off()
                self._ring.close()
        except Exception:
            pass
        self._ring = None
        self._tuning = None
        self.device_ok = False

    # ---- desired-state mutation (thread-safe) ----------------------------
    def set_jarvyz_mode(self, state: str) -> None:
        with self._lock:
            self.jarvyz_mode = state

    def set_jarvyz_connected(self, ok: bool) -> None:
        with self._lock:
            self.jarvyz_connected = ok

    def set_source(self, src: str) -> None:
        with self._lock:
            self.source = src

    def set_manual(self, spec: fx.RingSpec) -> None:
        with self._lock:
            self.manual_spec = spec
            self.source = "manual"

    def _current_spec(self) -> fx.RingSpec:
        with self._lock:
            if self.source == "manual":
                return self.manual_spec
            return self._mode_specs.get(self.jarvyz_mode, fx.RingSpec(kind="off"))

    # ---- per-mode animation config (persisted to MODES_FILE) -------------
    def _load_modes(self) -> dict:
        specs = dict(DEFAULT_MODE_SPECS)
        try:
            if MODES_FILE.is_file():
                data = json.loads(MODES_FILE.read_text("utf-8"))
                for mode, d in data.items():
                    if mode in specs:
                        specs[mode] = spec_from_dict(d)
        except Exception:
            pass
        return specs

    def _persist_modes(self, data: dict) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            MODES_FILE.write_text(json.dumps(data, indent=2), "utf-8")
        except Exception:
            pass

    def get_modes(self) -> dict:
        with self._lock:
            return {m: spec_to_dict(s) for m, s in self._mode_specs.items()}

    def set_mode_spec(self, mode: str, spec: fx.RingSpec):
        if mode not in self._mode_specs:
            return None
        with self._lock:
            self._mode_specs[mode] = spec
            data = {m: spec_to_dict(s) for m, s in self._mode_specs.items()}
        self._persist_modes(data)
        return spec_to_dict(spec)

    def reset_modes(self) -> dict:
        with self._lock:
            self._mode_specs = dict(DEFAULT_MODE_SPECS)
            data = {m: spec_to_dict(s) for m, s in self._mode_specs.items()}
        self._persist_modes(data)
        return data

    # ---- persisted config: DOA calibration, gamma, preview orientation --
    def _load_config(self):
        # Defaults for this ring: index runs counterclockwise (flip) with LED 0
        # at ~7 o'clock (offset 51°); gamma off; preview orientation neutral.
        off, flip, gamma, prot, pmir = 51, True, 1.0, 0, False
        try:
            if CONFIG_FILE.is_file():
                d = json.loads(CONFIG_FILE.read_text("utf-8"))
                off = int(d.get("doa_offset", off)) % 360
                flip = bool(d.get("doa_flip", flip))
                gamma = float(d.get("gamma", gamma))
                prot = int(d.get("preview_rotation", prot)) % 360
                pmir = bool(d.get("preview_mirror", pmir))
        except Exception:
            pass
        return off, flip, gamma, prot, pmir

    def _save_config(self) -> None:
        with self._lock:
            data = {
                "doa_offset": self.doa_offset,
                "doa_flip": self.doa_flip,
                "gamma": self.gamma,
                "preview_rotation": self.preview_rotation,
                "preview_mirror": self.preview_mirror,
            }
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(data, indent=2), "utf-8")
        except Exception:
            pass

    def set_doa_offset(self, value: int, flip: bool = False):
        with self._lock:
            self.doa_offset = int(value) % 360
            self.doa_flip = bool(flip)
        self._save_config()
        return self.doa_offset

    def set_gamma(self, value: float) -> float:
        with self._lock:
            self.gamma = max(0.1, min(4.0, float(value)))
        self._save_config()
        return self.gamma

    def set_preview(self, rotation: int, mirror: bool):
        with self._lock:
            self.preview_rotation = int(rotation) % 360
            self.preview_mirror = bool(mirror)
        self._save_config()
        return self.preview_rotation

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "device_ok": self.device_ok,
                "source": self.source,
                "jarvyz_connected": self.jarvyz_connected,
                "jarvyz_mode": self.jarvyz_mode,
                "doa": self.doa,
                "doa_offset": self.doa_offset,
                "doa_flip": self.doa_flip,
                "gamma": self.gamma,
                "preview_rotation": self.preview_rotation,
                "preview_mirror": self.preview_mirror,
                "voice": self.voice,
                "speech": self.speech,
                "ledfx_active": self._ledfx_active(),
                "manual": dataclasses.asdict(self.manual_spec),
            }

    # ---- LedFx (DDP) input source ---------------------------------------
    def feed_ledfx(self, frame: list) -> None:
        """Called by the DDP listener with a fresh 12-LED frame."""
        self.ledfx_frame = frame
        self.ledfx_ts = time.monotonic()

    def _ledfx_active(self) -> bool:
        return self.ledfx_frame is not None and (time.monotonic() - self.ledfx_ts) < self.LEDFX_TIMEOUT

    def stream_message(self) -> dict:
        """Compact live snapshot pushed over the /ws frame stream (~20 fps)."""
        with self._lock:
            return {
                "type": "frame",
                "leds": self.last_frame,
                "doa": self.doa,
                "voice": self.voice,
                "speech": self.speech,
                "jarvyz_mode": self.jarvyz_mode,
                "jarvyz_connected": self.jarvyz_connected,
                "device_ok": self.device_ok,
                "ledfx_active": self.last_source == "ledfx",
                "source": self.last_source,
            }

    # ---- DSP tuning (serialized with the frame loop via _usb_lock) -------
    @staticmethod
    def _param_dict(name: str, meta: tuple, value) -> dict:
        # meta = (id, offset, type, max, min, access, description)
        return {
            "name": name,
            "type": meta[2],
            "min": meta[4],
            "max": meta[3],
            "access": meta[5],
            "description": meta[6],
            "value": value,
        }

    def list_tuning(self) -> Optional[list]:
        """All DSP parameters with metadata + current values, or None if no device."""
        if not self.device_ok or self._tuning is None:
            return None
        out = []
        with self._usb_lock:
            for name in sorted(PARAMETERS):
                try:
                    value = self._tuning.read(name)
                except Exception:
                    value = None
                out.append(self._param_dict(name, PARAMETERS[name], value))
        return out

    def read_tuning(self, name: str):
        if name not in PARAMETERS:
            return None
        if not self.device_ok or self._tuning is None:
            return False
        with self._usb_lock:
            try:
                value = self._tuning.read(name)
            except Exception:
                value = None
        return self._param_dict(name, PARAMETERS[name], value)

    def write_tuning(self, name: str, value):
        if name not in PARAMETERS:
            return None
        meta = PARAMETERS[name]
        if meta[5] == "ro":
            return "ro"
        if not self.device_ok or self._tuning is None:
            return False
        # coerce to the parameter's type and clamp to [min, max]
        value = int(value) if meta[2] == "int" else float(value)
        value = max(meta[4], min(meta[3], value))
        with self._usb_lock:
            self._tuning.write(name, value)
            try:
                value = self._tuning.read(name)
            except Exception:
                pass
        return self._param_dict(name, meta, value)

    # ---- loop ------------------------------------------------------------
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ring-frames", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._close()

    def _loop(self) -> None:
        last_open = 0.0
        while self._running:
            if not self.device_ok:
                now = time.monotonic()
                if now - last_open >= self.REOPEN_EVERY_S:
                    last_open = now
                    self._open()
                if not self.device_ok:
                    time.sleep(0.2)
                    continue
            try:
                if self._t % self.DOA_EVERY == 0 and self._tuning is not None:
                    with self._usb_lock:
                        try:
                            self.doa = self._tuning.direction
                            self.voice = self._tuning.is_voice()
                            self.speech = self._tuning.read("SPEECHDETECTED")
                        except Exception:
                            pass
                if self._ledfx_active():
                    frame = self.ledfx_frame
                    self.last_source = "ledfx"
                else:
                    angle = self.doa
                    if angle is not None:
                        if self.doa_flip:
                            angle = -angle
                        angle = (angle + self.doa_offset) % 360
                    frame = fx.render(self._current_spec(), self._t, doa=angle)
                    self.last_source = self.source
                self.last_frame = frame
                with self._usb_lock:
                    self._ring.show(fx.to_show_data(frame, self.gamma))
            except Exception:
                # USB write/read failed — drop the handle and let the loop reopen.
                self._close()
                continue
            self._t += 1
            time.sleep(self.FRAME_MS / 1000.0)


class JarvyzLink:
    """Background thread: subscribe to JarvYZ's /ws and mirror `mode` frames.

    `mode` is delivered by default (not an opt-in channel), so no subscribe
    handshake is needed — just read frames and reconnect on drop.
    """

    def __init__(self, url: str, controller: RingController) -> None:
        self.url = url
        self.c = controller
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, name="jarvyz-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        import websocket  # websocket-client

        while self._running:
            try:
                ws = websocket.create_connection(self.url, timeout=5)
                ws.settimeout(1.0)
                self.c.set_jarvyz_connected(True)
                while self._running:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        break
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("event_type") == "mode":
                        state = msg.get("state")
                        if state:
                            self.c.set_jarvyz_mode(state)
                try:
                    ws.close()
                except Exception:
                    pass
            except Exception:
                pass
            self.c.set_jarvyz_connected(False)
            if self._running:
                time.sleep(2.0)


class DdpListener:
    """Receive DDP frames (e.g. from LedFx) over UDP and feed them to the ring.

    DDP packet = 10-byte header + raw RGB bytes. We ignore the header and take
    the first 12 pixels. Add a DDP device in LedFx pointing at this host:port
    with pixel_count=12 and the ring becomes a LedFx output — no LedFx changes.
    """

    def __init__(self, controller: RingController, host: str = "0.0.0.0", port: int = 4048) -> None:
        self.controller = controller
        self.host = host
        self.port = port
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, name="ddp-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.settimeout(1.0)
            print(f"DDP/LedFx listener on udp://{self.host}:{self.port}")
        except OSError as exc:
            print(f"DDP listener disabled (cannot bind {self.host}:{self.port}: {exc})")
            return
        n = fx.N_LEDS
        while self._running:
            try:
                pkt, _ = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(pkt) <= 10:
                continue
            rgb = pkt[10:]
            count = min(n, len(rgb) // 3)
            frame = [(rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]) for i in range(count)]
            if len(frame) < n:
                frame += [(0, 0, 0)] * (n - len(frame))
            self.controller.feed_ledfx(frame)


def build_app(controller: RingController):
    from fastapi import FastAPI, HTTPException, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="pixel-ring daemon")
    # Local device daemon — let a browser UI on any origin (standalone SPA,
    # Tauri, or the JarvYZ frontend) call the REST API directly.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class ModeIn(BaseModel):
        state: str

    class FollowIn(BaseModel):
        enabled: bool

    class EffectIn(BaseModel):
        kind: str = "creative"          # creative | assistant | solid | off
        name: str = ""                  # rainbow/comet/… or wakeup/listen/think/speak
        style: str = "echo"             # echo | google
        color: Optional[List[int]] = None
        palette: Optional[List[List[int]]] = None
        intensity: float = 0.6
        doa_track: str = "off"          # off | marker | rotate
        doa_color: Optional[List[int]] = None
        doa_intensity: float = 1.0

    class ColorIn(BaseModel):
        r: int
        g: int
        b: int
        intensity: float = 1.0

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/state")
    def state() -> dict:
        return controller.snapshot()

    @app.post("/mode")
    def set_mode(body: ModeIn) -> dict:
        # Inject a mode (works even in auto — handy for testing without JarvYZ).
        controller.set_jarvyz_mode(body.state)
        return controller.snapshot()

    @app.post("/follow")
    def follow(body: FollowIn) -> dict:
        controller.set_source("auto" if body.enabled else "manual")
        return controller.snapshot()

    @app.post("/effect")
    def effect(body: EffectIn) -> dict:
        controller.set_manual(spec_from_dict(body.model_dump()))
        return controller.snapshot()

    @app.post("/color")
    def color(body: ColorIn) -> dict:
        controller.set_manual(fx.RingSpec(kind="solid", color=(body.r, body.g, body.b), intensity=body.intensity))
        return controller.snapshot()

    @app.post("/off")
    def off() -> dict:
        controller.set_manual(fx.RingSpec(kind="off"))
        return controller.snapshot()

    class LedsIn(BaseModel):
        leds: List[List[int]]           # up to 12 [r,g,b]; missing LEDs default off

    @app.post("/leds")
    def leds(body: LedsIn) -> dict:
        frame = [tuple(c[:3]) for c in body.leds][:12]
        controller.set_manual(fx.RingSpec(kind="custom", leds=frame))
        return controller.snapshot()

    class OffsetIn(BaseModel):
        value: int                      # degrees added to DOA before LED mapping
        flip: bool = False              # reverse direction (index runs opposite to DOA)

    @app.post("/doa_offset")
    def doa_offset(body: OffsetIn) -> dict:
        controller.set_doa_offset(body.value, body.flip)
        return controller.snapshot()

    class GammaIn(BaseModel):
        value: float                    # 1.0 = linear/off; >1 corrects low-end fades

    @app.post("/gamma")
    def gamma(body: GammaIn) -> dict:
        controller.set_gamma(body.value)
        return controller.snapshot()

    class PreviewIn(BaseModel):
        rotation: int = 0               # display-only: rotate the on-screen ring
        mirror: bool = False            # display-only: reverse the on-screen index direction

    @app.post("/preview")
    def preview(body: PreviewIn) -> dict:
        controller.set_preview(body.rotation, body.mirror)
        return controller.snapshot()

    # ---- per-mode animation config --------------------------------------
    @app.get("/modes")
    def modes_list() -> dict:
        return controller.get_modes()

    @app.put("/modes/{mode}")
    def mode_set(mode: str, body: EffectIn) -> dict:
        r = controller.set_mode_spec(mode, spec_from_dict(body.model_dump()))
        if r is None:
            raise HTTPException(404, f"unknown mode '{mode}'")
        return r

    @app.post("/modes/reset")
    def modes_reset() -> dict:
        return controller.reset_modes()

    # ---- DSP tuning ------------------------------------------------------
    class TuneIn(BaseModel):
        value: float

    @app.get("/tuning")
    def tuning_list() -> dict:
        params = controller.list_tuning()
        if params is None:
            raise HTTPException(503, "device not available")
        return {"params": params}

    @app.get("/tuning/{name}")
    def tuning_get(name: str) -> dict:
        r = controller.read_tuning(name)
        if r is None:
            raise HTTPException(404, f"unknown parameter '{name}'")
        if r is False:
            raise HTTPException(503, "device not available")
        return r

    @app.post("/tuning/{name}")
    def tuning_set(name: str, body: TuneIn) -> dict:
        r = controller.write_tuning(name, body.value)
        if r is None:
            raise HTTPException(404, f"unknown parameter '{name}'")
        if r == "ro":
            raise HTTPException(400, f"parameter '{name}' is read-only")
        if r is False:
            raise HTTPException(503, "device not available")
        return r

    # ---- live frame stream over WebSocket (replaces high-rate polling) ---
    app.state.clients = set()
    app.state.broadcaster = None

    async def _broadcast_loop():
        while True:
            await asyncio.sleep(0.05)   # ~20 fps
            clients = list(app.state.clients)
            if not clients:
                continue
            text = json.dumps(controller.stream_message())
            for ws in clients:
                try:
                    await ws.send_text(text)
                except Exception:
                    app.state.clients.discard(ws)

    @app.websocket("/ws")
    async def ws_stream(websocket: WebSocket):
        await websocket.accept()
        app.state.clients.add(websocket)
        if app.state.broadcaster is None:
            app.state.broadcaster = asyncio.create_task(_broadcast_loop())
        try:
            while True:
                await websocket.receive_text()   # only used to detect disconnect
        except Exception:
            pass
        finally:
            app.state.clients.discard(websocket)

    # Serve the built standalone SPA (ui/dist) from the daemon if present, so
    # `http://127.0.0.1:<port>/` shows the control UI with no extra server.
    # Mounted last so it never shadows the API routes above.
    ui_dist = _ui_dist_dir()
    if ui_dist.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


def _ui_dist_dir() -> Path:
    """Locate the built UI (the web control panel).

    It is built into the package (``yz_pixel_ring/_ui``) so it ships in the wheel
    AND the PyInstaller bundle. ``__file__`` resolves correctly in all three cases
    — source checkout, pip/uv install, and frozen exe (``sys._MEIPASS``)."""
    here = Path(__file__).resolve().parent
    in_pkg = here / "_ui"
    if in_pkg.is_dir():
        return in_pkg
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", here)) / "yz_pixel_ring" / "_ui"
    return in_pkg


def _redirect_output_if_headless() -> None:
    """Under pythonw / Task Scheduler there's no console, so sys.stdout/stderr
    are None and uvicorn's logging crashes. Send output to a log file instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        logf = open(CONFIG_DIR / "daemon.log", "a", buffering=1, encoding="utf-8")
    except Exception:
        import io
        logf = io.StringIO()
    sys.stdout = logf
    sys.stderr = logf


def main() -> None:
    _redirect_output_if_headless()
    ap = argparse.ArgumentParser(description="ReSpeaker ring daemon")
    ap.add_argument("--ws-url", default=os.environ.get("JARVYZ_WS_URL", "ws://127.0.0.1:8765/ws"))
    ap.add_argument("--host", default=os.environ.get("RING_DAEMON_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("RING_DAEMON_PORT", "9700")))
    ap.add_argument("--no-jarvyz", action="store_true", help="don't connect to JarvYZ's WebSocket")
    ap.add_argument("--ddp-port", type=int, default=int(os.environ.get("RING_DDP_PORT", "4048")))
    ap.add_argument("--no-ledfx", action="store_true", help="don't listen for LedFx DDP frames")
    args = ap.parse_args()

    controller = RingController()
    controller.start()

    link = None
    if not args.no_jarvyz:
        link = JarvyzLink(args.ws_url, controller)
        link.start()

    ddp = None
    if not args.no_ledfx:
        ddp = DdpListener(controller, port=args.ddp_port)
        ddp.start()

    import uvicorn

    app = build_app(controller)
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        if link is not None:
            link.stop()
        if ddp is not None:
            ddp.stop()
        controller.stop()


if __name__ == "__main__":
    main()
