"""Tests for optional case_sensitive matching in character_presence and presence_report."""

from __future__ import annotations

from lixity.characters import character_presence, presence_report
from lixity.models import CorpusConfig


def test_character_presence_case_sensitive_option() -> None:
    text = (
        "## Chapter 1\n\n"
        "Grace walked with grace through the hall. Mark left a mark on the door.\n\n"
        '"Hello," Grace said.\n\n'
        '"Hi," Mark replied.\n'
    )
    cfg = CorpusConfig(language="en")

    # Default remains case-insensitive.
    insensitive = {item.name: item.mentions for item in character_presence(text, ["Grace", "Mark"], cfg)}
    assert insensitive == {"Grace": 3, "Mark": 3}

    # Explicit case_sensitive=True matches only exact casing.
    sensitive = {
        item.name: item.mentions
        for item in character_presence(text, ["Grace", "Mark"], cfg, case_sensitive=True)
    }
    assert sensitive == {"Grace": 2, "Mark": 2}

    report = presence_report(text, {"Grace": "Grace", "Mark": "Mark"}, cfg, case_sensitive=True)
    figures = {fig["name"]: fig["mentions"] for fig in report["figures"]}
    assert figures == {"Grace": 2, "Mark": 2}
