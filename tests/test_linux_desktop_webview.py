"""Check that the optional WebKitGTK smoke rejects an unpainted capture."""

from types import SimpleNamespace

from desktop.scripts.smoke_linux_webview import _has_painted_detail


def test_graphical_smoke_requires_paints_inside_pixels():
    white_pixel = bytes([255, 255, 255])
    black_pixel = bytes([0, 0, 0])
    padding = bytes(4)
    white_row = white_pixel * 4 + padding
    pixels = white_row * 4
    pixbuf = SimpleNamespace(
        get_pixels=lambda: pixels,
        get_n_channels=lambda: 3,
        get_rowstride=lambda: 16,
        get_width=lambda: 4,
        get_height=lambda: 4,
    )

    assert not _has_painted_detail(pixbuf)
    pixels = (black_pixel + white_pixel * 3 + padding) + white_row * 3
    assert not _has_painted_detail(pixbuf)
    pixels = (black_pixel * 2 + white_pixel * 2 + padding) * 4
    assert _has_painted_detail(pixbuf)
