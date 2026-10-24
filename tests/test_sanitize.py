# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

import pytest

from appjail_db import catalog, sanitize
from appjail_db.catalog import App


@pytest.mark.parametrize("ch", [
    "\u200b", "\u200e", "\u200f", "\u061c", "\u2060", "\ufeff", "\u2028", "\u2029", "\u00ad",
    "\U000e0041", "\ue000", "\U000e007f", "\u0378",
])
def test_unwanted_characters_are_stripped(ch):
    assert sanitize.remove(f"a{ch}b") == ("ab", {ch: 1})


def test_what_emoji_and_scripts_need_stays():
    for text in ("\U0001f468\u200d\U0001f469\u200d\U0001f467", "می\u200cخواهم", "\u2764\ufe0f", "café \u4e2d\u6587"):
        assert sanitize.remove(text) == (text, {})


def test_stripping_is_idempotent_and_leaves_clean_text_alone():
    once, _ = sanitize.remove("x\u200b\u200by\u2028")
    assert once == "xy" and sanitize.remove(once) == ("xy", {})


def test_sanitize_cleans_description_and_note_and_reports_each():
    cat = catalog.Catalog((App("a", "one\u200btwo\u200b", "github:o/a", "n\u2060"), App("b", "fine", "github:o/b")), "o", "r")
    clean, lines = sanitize.sanitize(cat)
    assert [(a.description, a.note) for a in clean.apps] == [("onetwo", "n"), ("fine", "")]
    assert lines == ["a: description: stripped U+200B x2", "a: note: stripped U+2060"]
    assert (clean.origin, clean.revision) == ("o", "r")


def test_a_description_that_was_only_invisible_becomes_empty():
    clean, _ = sanitize.sanitize(catalog.Catalog((App("a", "\u200b \u200b", "github:o/a"),)))
    assert clean.apps[0].description == ""
