"""DSP parameter access for the ReSpeaker USB Mic Array v2.0 (XVSR3000).

Reads/writes the on-board DSP parameters (DOA angle, VAD, AGC, AEC, noise
suppression, …) over the device's vendor control interface — the same USB
device as the pixel ring (0x2886:0x0018), a different interface.

PARAMETERS below is the device's public parameter spec (id, offset, type,
range, access). The read/write methods implement the documented binary
control-transfer protocol; no upstream source is reused.
"""

import usb.core
import usb.util
import struct


# name: (id, offset, type, max, min, rw, description...)
PARAMETERS = {
    'AECFREEZEONOFF': (18, 7, 'int', 1, 0, 'rw', 'Adaptive Echo Canceler updates inhibit. 0=enabled 1=frozen'),
    'AECNORM': (18, 19, 'float', 16, 0.25, 'rw', 'Limit on norm of AEC filter coefficients'),
    'AECPATHCHANGE': (18, 25, 'int', 1, 0, 'ro', 'AEC Path Change Detection. 0=no 1=yes'),
    'RT60': (18, 26, 'float', 0.9, 0.25, 'ro', 'Current RT60 estimate in seconds'),
    'HPFONOFF': (18, 27, 'int', 3, 0, 'rw', 'High Pass Filter. 0=off 1=70Hz 2=125Hz 3=180Hz'),
    'RT60ONOFF': (18, 28, 'int', 1, 0, 'rw', 'RT60 Estimation for AES. 0=off 1=on'),
    'AECSILENCELEVEL': (18, 30, 'float', 1, 1e-09, 'rw', 'Threshold for signal detection in AEC [-inf..0] dBov'),
    'AECSILENCEMODE': (18, 31, 'int', 1, 0, 'ro', 'AEC far-end silence detection. 0=signal 1=silence'),
    'AGCONOFF': (19, 0, 'int', 1, 0, 'rw', 'Automatic Gain Control. 0=off 1=on'),
    'AGCMAXGAIN': (19, 1, 'float', 1000, 1, 'rw', 'Maximum AGC gain factor [0..60] dB'),
    'AGCDESIREDLEVEL': (19, 2, 'float', 0.99, 1e-08, 'rw', 'Target output power level [-inf..0] dBov'),
    'AGCGAIN': (19, 3, 'float', 1000, 1, 'rw', 'Current AGC gain factor [0..60] dB'),
    'AGCTIME': (19, 4, 'float', 1, 0.1, 'rw', 'AGC ramp-up/down time-constant (s)'),
    'CNIONOFF': (19, 5, 'int', 1, 0, 'rw', 'Comfort Noise Insertion. 0=off 1=on'),
    'FREEZEONOFF': (19, 6, 'int', 1, 0, 'rw', 'Adaptive beamformer updates. 0=enabled 1=frozen'),
    'STATNOISEONOFF': (19, 8, 'int', 1, 0, 'rw', 'Stationary noise suppression. 0=off 1=on'),
    'GAMMA_NS': (19, 9, 'float', 3, 0, 'rw', 'Over-subtraction factor of stationary noise'),
    'MINNS': (19, 10, 'float', 1, 0, 'rw', 'Gain-floor for stationary noise suppression [-inf..0] dB'),
    'NONSTATNOISEONOFF': (19, 11, 'int', 1, 0, 'rw', 'Non-stationary noise suppression. 0=off 1=on'),
    'GAMMA_NN': (19, 12, 'float', 3, 0, 'rw', 'Over-subtraction factor of non-stationary noise'),
    'MINNN': (19, 13, 'float', 1, 0, 'rw', 'Gain-floor for non-stationary noise suppression [-inf..0] dB'),
    'ECHOONOFF': (19, 14, 'int', 1, 0, 'rw', 'Echo suppression. 0=off 1=on'),
    'GAMMA_E': (19, 15, 'float', 3, 0, 'rw', 'Over-subtraction factor of echo (direct/early)'),
    'GAMMA_ETAIL': (19, 16, 'float', 3, 0, 'rw', 'Over-subtraction factor of echo (tail)'),
    'GAMMA_ENL': (19, 17, 'float', 5, 0, 'rw', 'Over-subtraction factor of non-linear echo'),
    'NLATTENONOFF': (19, 18, 'int', 1, 0, 'rw', 'Non-Linear echo attenuation. 0=off 1=on'),
    'NLAEC_MODE': (19, 20, 'int', 2, 0, 'rw', 'Non-Linear AEC training mode. 0=off 1=phase1 2=phase2'),
    'SPEECHDETECTED': (19, 22, 'int', 1, 0, 'ro', 'Speech detection status. 0=no 1=yes'),
    'FSBUPDATED': (19, 23, 'int', 1, 0, 'ro', 'FSB Update Decision. 0=no 1=yes'),
    'FSBPATHCHANGE': (19, 24, 'int', 1, 0, 'ro', 'FSB Path Change Detection. 0=no 1=yes'),
    'TRANSIENTONOFF': (19, 29, 'int', 1, 0, 'rw', 'Transient echo suppression. 0=off 1=on'),
    'VOICEACTIVITY': (19, 32, 'int', 1, 0, 'ro', 'VAD voice activity status. 0=no 1=voice'),
    'STATNOISEONOFF_SR': (19, 33, 'int', 1, 0, 'rw', 'Stationary noise suppression for ASR. 0=off 1=on'),
    'NONSTATNOISEONOFF_SR': (19, 34, 'int', 1, 0, 'rw', 'Non-stationary noise suppression for ASR. 0=off 1=on'),
    'GAMMA_NS_SR': (19, 35, 'float', 3, 0, 'rw', 'Over-subtraction factor of stationary noise for ASR'),
    'GAMMA_NN_SR': (19, 36, 'float', 3, 0, 'rw', 'Over-subtraction factor of non-stationary noise for ASR'),
    'MINNS_SR': (19, 37, 'float', 1, 0, 'rw', 'Gain-floor for stationary noise suppression for ASR [-inf..0] dB'),
    'MINNN_SR': (19, 38, 'float', 1, 0, 'rw', 'Gain-floor for non-stationary noise suppression for ASR [-inf..0] dB'),
    'GAMMAVAD_SR': (19, 39, 'float', 1000, 0, 'rw', 'VAD threshold [-inf..60] dB (default 3.5dB). Higher = less sensitive'),
    'DOAANGLE': (21, 0, 'int', 359, 0, 'ro', 'DOA angle 0-359 deg. Orientation depends on build config'),
}


class Tuning:
    """Reads/writes XVSR3000 DSP parameters over the vendor control interface.

    Param spec tuple: (resource_id, offset, type, max, min, access, description).
    """

    TIMEOUT = 100000

    def __init__(self, dev):
        self.dev = dev

    def read(self, name):
        p = PARAMETERS.get(name)
        if p is None:
            return None
        resid, offset, ptype = p[0], p[1], p[2]
        cmd = 0x80 | offset
        if ptype == 'int':
            cmd |= 0x40
        resp = self.dev.ctrl_transfer(
            usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
            0, cmd, resid, 8, self.TIMEOUT)
        value, exponent = struct.unpack(b'ii', resp.tobytes())
        return value if ptype == 'int' else value * (2.0 ** exponent)

    def write(self, name, value):
        p = PARAMETERS.get(name)
        if p is None:
            return
        resid, offset, ptype, vmax, vmin, access = p[0], p[1], p[2], p[3], p[4], p[5]
        if access == 'ro':
            raise ValueError('{} is read-only'.format(name))
        if ptype == 'int':
            payload = struct.pack(b'iiiii', offset, int(value), 1, vmax, vmin)
        else:
            payload = struct.pack(b'ififf', offset, float(value), 0, vmax, vmin)
        self.dev.ctrl_transfer(
            usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
            0, 0, resid, payload, self.TIMEOUT)

    def is_voice(self):
        return self.read('VOICEACTIVITY')

    @property
    def direction(self):
        return self.read('DOAANGLE')

    def close(self):
        usb.util.dispose_resources(self.dev)


def find(vid=0x2886, pid=0x0018):
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    return Tuning(dev) if dev is not None else None
