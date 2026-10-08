"""Shared layout defaults carry geometry, never a project's author identity."""
from lixity.layout import BookLayoutConfig


def test_layout_identity_is_explicit_and_geometry_remains_shared():
    config = BookLayoutConfig(420, 595, 40, 40, 50, 50)
    assert config.contact_info == ""
    assert config.content_width == 340
    assert config.content_height == 495
    config.contact_info = "Synthetic project contact"
    assert config.contact_info == "Synthetic project contact"
