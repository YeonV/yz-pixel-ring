# ReSpeaker USB Mic Array (v2.0) — Control Reference

Distilled from the [Seeed Studio wiki](https://wiki.seeedstudio.com/ReSpeaker-USB-Mic-Array/)
and cross-checked against the source in this repo ([led.py](../yz_pixel_ring/led.py)).

> **Device:** ReSpeaker USB Mic Array v2.0 — USB **VID `0x2886`**, **PID `0x0018`**.
> Onboard XVSR3000 DSP (4-mic beamforming, AEC, noise suppression, VAD, DOA) + 12× APA102 RGB LED ring.
> Product is **EOL**; firmware/tools below are the final released versions.

---

## 1. LED / Pixel Ring control

All LED control is a single USB **vendor control-OUT transfer**, needing only `pyusb`
(plus a libusb backend).

**Transfer signature** (see [`PixelRing.write`](../yz_pixel_ring/led.py)):

```python
dev.ctrl_transfer(
    usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
    0,        # bRequest
    cmd,      # wValue  -> the command code below
    0x1C,     # wIndex
    data,     # payload bytes
    8000)     # timeout (ms)
```

### Command table (authoritative — from this repo's source)

| `cmd` | Method | Payload | Effect |
|------|--------|---------|--------|
| `0`    | `trace()`              | `[0]`                       | Trace mode — ring reacts to VAD + DOA automatically |
| `1`    | `mono(color)` / `set_color(rgb)` | `[r, g, b, 0]`   | All LEDs one color. `off()` = `mono(0)` |
| `2`    | `listen()` (alias `wakeup()`) | `[0]`                | Listen mode (like trace but never blanks). `wakeup(direction)` arg is ignored |
| `3`    | `speak()`              | `[0]`                       | Speak animation |
| `4`    | `think()` (alias `wait()`) | `[0]`                  | Think/wait animation |
| `5`    | `spin()`               | `[0]`                       | Spin animation |
| `6`    | `show(data)` / `customize(data)` | `[r,g,b,0] × 12`  | Per-LED colors (12 LEDs → 48 bytes) |
| `0x20` | `set_brightness(b)`    | `[brightness]`              | Brightness `0x00`–`0x1F` |
| `0x21` | `set_color_palette(a,b)` | `[ra,ga,ba,0, rb,gb,bb,0]` | Two-color palette used by animations |
| `0x22` | `set_vad_led(state)`   | `[state]`                   | Center LED: `0`=off, `1`=on, other=follow VAD |
| `0x23` | `set_volume(v)`        | `[volume]`                  | VU/volume level `0`–`12` |
| `0x24` | `change_pattern(p)`    | `[pattern]`                 | `0`=Google pattern, else Echo. **Not implemented in this repo's `PixelRing` class** |

> ⚠️ The Seeed wiki's table swaps the labels for `speak`/`think` and mislabels a few modes.
> The table above reflects the actual `led.py` (`PixelRing`) in this repo, which is what runs.

### Minimal usage (cross-platform, USB)

```python
import usb.core, time
from yz_pixel_ring.led import PixelRing

dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
ring = PixelRing(dev)
ring.set_brightness(0x0A)
ring.wakeup(); time.sleep(2)
ring.think();  time.sleep(2)
ring.off()
ring.close()           # release the USB handle
```

---

## 2. DSP tuning, VAD & DOA (`tuning.py`)

DSP parameters are read/written over a **separate** vendor control interface (same
VID/PID `0x2886`/`0x0018`). This repo's own [`Tuning`](../yz_pixel_ring/tuning.py)
class implements the documented protocol; the daemon also exposes it over REST
(`GET /tuning`, `POST /tuning/{name}`).

```python
import usb.core
from yz_pixel_ring.tuning import Tuning

mic = Tuning(usb.core.find(idVendor=0x2886, idProduct=0x0018))
mic.read('DOAANGLE')          # read one
mic.write('AGCONOFF', 0)      # write one (rw params only)
```

### Real-time sound-source localization (DOA)

```python
import usb.core, time
from yz_pixel_ring.tuning import Tuning

dev = usb.core.find(idVendor=0x2886, idProduct=0x0018)
mic = Tuning(dev)
while True:
    print(mic.direction)   # 0–359 degrees, == DOAANGLE
    time.sleep(0.2)
```

- `mic.direction` returns **`DOAANGLE`**, `0`–`359°`. Orientation depends on firmware build / board orientation — calibrate against the hardware diagram.
- On the ring, the **green LED indicates the detected voice direction** in trace/listen mode.

### Voice Activity Detection (VAD)

```python
mic.is_voice()        # -> 0/1, reads VOICEACTIVITY
mic.read('SPEECHDETECTED')
```

### Key parameters (VAD / DOA / AGC / noise)

| Parameter | Type | R/W | Range | Meaning |
|-----------|------|-----|-------|---------|
| `DOAANGLE`        | int   | ro | 0–359           | Direction-of-arrival angle (current) |
| `VOICEACTIVITY`   | int   | ro | 0–1             | VAD: 1 = voice present |
| `SPEECHDETECTED`  | int   | ro | 0–1             | Speech detected flag |
| `GAMMAVAD_SR`     | float | rw | 0–1000          | VAD threshold, [-inf..60] dB (default 3.5 dB) — raise to make VAD less sensitive |
| `AGCONOFF`        | int   | rw | 0–1             | Automatic Gain Control on/off |
| `AGCDESIREDLEVEL` | float | rw | 1e-8–0.99       | AGC target level, [-inf..0] dBov (default −23 dBov) |
| `AGCMAXGAIN`      | float | rw | 1–1000          | Max AGC gain, [0..60] dB (default 30 dB) |
| `AGCGAIN`         | float | rw | 1–1000          | Current AGC gain factor |
| `AGCTIME`         | float | rw | 0.1–1           | AGC ramp time constant (s) |
| `ECHOONOFF`       | int   | rw | 0–1             | Acoustic echo suppression on/off |
| `AECFREEZEONOFF`  | int   | rw | 0–1             | Freeze adaptive echo canceller |
| `AECNORM`         | float | rw | 0.25–16         | Limit on AEC filter coeff norm |
| `CNIONOFF`        | int   | rw | 0–1             | Comfort noise insertion |
| `STATNOISEONOFF`  | int   | rw | 0–1             | Stationary noise suppression |
| `NONSTATNOISEONOFF` | int | rw | 0–1             | Non-stationary noise suppression |
| `FREEZEONOFF`     | int   | rw | 0–1             | Freeze adaptive beamformer (1 = frozen) |
| `HPFONOFF`        | int   | rw | 0–3             | High-pass filter: 0=off, 1=70 Hz, 2=125 Hz, 3=180 Hz |

> The full parameter list (covering beamformer, AEC, NS internals) is the
> `PARAMETERS` dict in this repo's [tuning.py](../yz_pixel_ring/tuning.py).

---

## 3. Audio capture / voice extraction

- **Sample rate:** 16 kHz · **Sample width:** 16-bit (2 bytes).
- The processed (beamformed + AEC + NS) ASR audio is **channel 0**.

### Firmware variants (decide channel layout)

| Firmware | Channels | Layout |
|----------|----------|--------|
| `1_channel_firmware.bin` | 1 | Processed audio for ASR only |
| `6_channels_firmware.bin` (factory default) | 6 | ch0 = processed/ASR · ch1–4 = raw mics · ch5 = playback reference |

Flash (Linux only, via DFU):
```bash
git clone https://github.com/respeaker/usb_4_mic_array.git
cd usb_4_mic_array
sudo python dfu.py --download 6_channels_firmware.bin   # or 1_channel_firmware.bin
```

### Record with PyAudio

```python
import pyaudio, wave, numpy as np

RATE, WIDTH, CHANNELS = 16000, 2, 6   # CHANNELS = 1 for 1-ch firmware
CHUNK, SECONDS = 1024, 5
DEV_INDEX = 2                          # the device's PyAudio index (enumerate via get_device_info_by_index)

p = pyaudio.PyAudio()
stream = p.open(rate=RATE, channels=CHANNELS,
                format=p.get_format_from_width(WIDTH),
                input=True, input_device_index=DEV_INDEX)

frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * SECONDS))]
stream.stop_stream(); stream.close(); p.terminate()

# Pull just the clean ASR channel (channel 0) out of the 6-ch interleave:
buf = b''.join(frames)
ch0 = np.frombuffer(buf, dtype=np.int16)[0::CHANNELS]
```

Quick CLI test (Linux): `arecord -D plughw:1,0 -f cd test.wav`

---

## 4. Putting it together

The DSP already does VAD, DOA and beamforming on-device, so a typical app:

1. Open the **USB tuning interface** (`Tuning`) → poll `mic.direction` (DOA) and `mic.is_voice()` (VAD).
2. Open the **audio interface** (PyAudio) → read **channel 0** for clean speech.
3. Open the **pixel-ring interface** (`PixelRing`) → reflect state on the LEDs (`wakeup` on VAD, color/green LED toward DOA, `off` when idle).

All three are independent USB control/stream paths to the same `0x2886:0x0018` device.

## References

This document describes the device's **public USB protocol** (per the Seeed wiki) and
this repo's own **MIT-licensed** implementation of it (`led.py`, `tuning.py`). The
original respeaker projects below are **GPL-licensed and referenced for the protocol
only — no code from them is reused here**; the implementations are independent rewrites.

- Seeed wiki (protocol docs): https://wiki.seeedstudio.com/ReSpeaker-USB-Mic-Array/
- respeaker/pixel_ring — GPL, reference only: https://github.com/respeaker/pixel_ring
- respeaker/usb_4_mic_array — GPL, reference only (also hosts the external DFU firmware
  tool used in §3): https://github.com/respeaker/usb_4_mic_array
