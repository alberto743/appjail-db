# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

import json

import pytest

from appjail_db import hubsource
from appjail_db.catalog import App, IndexProblem


def feed(*items):
    return json.dumps({"items": list(items)})


def link(kind, url):
    return {"type": kind, "url": url}


def convert(*items):
    return {a.name: a for a in hubsource.convert(feed(*items)).apps}


def test_sources_come_from_the_repository_links():
    apps = convert(
        {"name": "gh", "description": "d", "links": [link("Download", "https://x.org/gh"), link("GitHub", "o/gh")]},
        {"name": "gl", "links": [link("GitLab", "group/gl")]},
        {"name": "cb", "links": [link("Codeberg", "user/cb")]},
    )
    assert apps["gh"] == App("gh", "d", "github:o/gh", "")
    assert apps["gl"].source == "gitlab:gitlab.com/group/gl"
    assert apps["cb"].source == "forgejo:codeberg.org/user/cb"


def test_a_github_download_link_is_the_fallback_and_other_links_become_notes():
    apps = convert(
        {"name": "rel", "links": [link("Download", "https://github.com/o/rel/releases")]},
        {"name": "far", "links": [link("Download", "https://example.org/far.AppImage")]},
        {"name": "none", "links": None},
        {"name": "bad", "links": [link("GitHub", "not a repo"), 3, "x"]},
    )
    assert apps["rel"].source == "github:o/rel"
    assert apps["far"].source == "" and apps["far"].note.startswith("resolve manually: https://example.org/far")
    assert apps["none"].note == "no source in the index" and apps["bad"].note == "no source in the index"


def test_descriptions_are_cleaned_and_capped():
    apps = convert({"name": "a", "description": "x\x1b[31m " + "word " * 40}, {"name": "b", "description": 5})
    assert "\x1b" not in apps["a"].description and len(apps["a"].description) <= 100
    assert apps["b"].description == ""


def test_unusable_names_and_case_duplicates_are_skipped():
    apps = convert({"name": "-_ICQ"}, {"name": "fre:ac"}, {"name": 4}, "x",
                   {"name": "Dup", "links": [link("GitHub", "a/dup")]}, {"name": "dup", "links": [link("GitHub", "b/dup")]},
                   {"name": "ok"})
    assert set(apps) == {"Dup", "ok"} and apps["Dup"].source == "github:a/dup"


def test_the_revision_tells_feeds_apart():
    a = hubsource.convert(feed({"name": "a"}))
    b = hubsource.convert(feed({"name": "b"}))
    assert a.revision.startswith("sha256:") and a.revision != b.revision and a.origin == hubsource.HUB_URL


@pytest.mark.parametrize("text", ["nope", "[]", '{"items": 3}', '{"items": []}', '{"items": [{"name": "-x"}]}'])
def test_a_bad_feed_is_refused(text):
    with pytest.raises(IndexProblem):
        hubsource.convert(text)


def test_only_https_is_fetched():
    with pytest.raises(IndexProblem, match="https"):
        hubsource.fetch_feed("http://appimage.github.io/feed.json")
