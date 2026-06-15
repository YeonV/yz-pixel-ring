"""Unit tests for the pure animation engine (no hardware required)."""

from yz_pixel_ring import animations as fx


def _valid(frame):
    assert len(frame) == fx.N_LEDS
    for px in frame:
        assert len(px) == 3
        for c in px:
            assert 0 <= c <= 255


def test_off_is_all_dark():
    assert fx.render(fx.RingSpec(kind="off"), 0) == [(0, 0, 0)] * fx.N_LEDS


def test_solid_uses_color_and_intensity():
    frame = fx.render(fx.RingSpec(kind="solid", color=(200, 100, 50), intensity=1.0), 0)
    assert frame == [(200, 100, 50)] * fx.N_LEDS
    dim = fx.render(fx.RingSpec(kind="solid", color=(200, 100, 50), intensity=0.5), 0)
    assert dim[0] == (100, 50, 25)


def test_all_creative_effects_render_valid_frames():
    for name in fx.CREATIVE:
        for t in (0, 1, 7, 13):
            _valid(fx.render(fx.RingSpec(kind="creative", name=name, color=(0, 200, 255), intensity=0.6), t))


def test_assistant_echo_and_google_render_valid_frames():
    for name in fx.ASSISTANT:
        for style in ("echo", "google"):
            _valid(fx.render(fx.RingSpec(kind="assistant", name=name, style=style, intensity=0.8), t=3, doa=90))


def test_wakeup_points_at_doa():
    # The bright LED should land at the index derived from the DOA angle.
    frame = fx.echo("wakeup", t=0, color=(255, 255, 255), intensity=1.0, doa=90)
    brightest = max(range(fx.N_LEDS), key=lambda i: sum(frame[i]))
    assert brightest == int((90 + 15) / 30) % fx.N_LEDS


def test_doa_falls_back_to_sweep_when_none():
    a = fx.echo("wakeup", t=0, color=(255, 255, 255), intensity=1.0, doa=None)
    b = fx.echo("wakeup", t=30, color=(255, 255, 255), intensity=1.0, doa=None)
    assert a != b  # the sweep advances with t


def test_to_show_data_shape():
    data = fx.to_show_data([(1, 2, 3)] * fx.N_LEDS)
    assert len(data) == fx.N_LEDS * 4
    assert data[:4] == [1, 2, 3, 0]
