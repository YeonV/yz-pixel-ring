"""PyInstaller entry point.

A plain script (absolute imports, no package-relative imports) so PyInstaller
can use it as the frozen app's entry. It just calls the daemon's ``main()``.
"""
import multiprocessing

from yz_pixel_ring.daemon import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # harmless; guards against frozen re-spawn
    main()
