"""ReSpeaker USB Mic Array v2.0 pixel ring.

USB LED control (:class:`PixelRing`), DSP tuning / DOA / VAD (:class:`Tuning`),
and a pure animation engine (:mod:`yz_pixel_ring.animations`).

The legacy Raspberry-Pi SPI/APA102 backend has been removed — this package now
targets the USB ring only.
"""

__version__ = "0.2.1"

from .led import PixelRing, find
from .tuning import Tuning

__all__ = ["PixelRing", "find", "Tuning", "__version__"]
