# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

"""Convert the feed of AppImageHub (appimage.github.io) into a catalog.

The feed is one JSON document published by the site. It is untrusted data: it is parsed strictly, every text is
cleaned, links are only read as strings (never followed) and nothing in it is evaluated.
"""

import hashlib
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import amsource, catalog, textsafe
from .catalog import IndexProblem

HUB_URL = "https://appimage.github.io"
FEED_URL = f"{HUB_URL}/feed.json"
MAX_FEED_BYTES = 16 * 1024 ** 2
FEED_TIMEOUT = 120
# Link types of the feed that name a repository as a bare `owner/repo` (GitLab and Codeberg only on their main host).
LINK_PREFIXES = (("GitHub", "github:"), ("GitLab", "gitlab:gitlab.com/"), ("Codeberg", "codeberg:"))


class _SameHost(urllib.request.HTTPRedirectHandler):
    """Follow redirects only within the same https host: the feed is a fixed address, not a pointer to elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0917 (the stdlib signature)
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if new.scheme != "https" or new.hostname != old.hostname:
            raise IndexProblem(f"the feed redirects to another host: {textsafe.clean(newurl, 100)}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_feed(url=FEED_URL, timeout=FEED_TIMEOUT):
    """The feed text; IndexProblem when it cannot be had, is not https or is too large."""
    if urlsplit(url).scheme != "https":
        raise IndexProblem("the feed must be fetched over https")
    opener = urllib.request.build_opener(_SameHost)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "appjail-db"}), timeout=timeout) as r:
            data = r.read(MAX_FEED_BYTES + 1)
    except IndexProblem:
        raise
    except (OSError, urllib.error.URLError) as e:
        raise IndexProblem("could not fetch the AppImageHub feed: " + textsafe.clean(e, 200)) from None
    if len(data) > MAX_FEED_BYTES:
        raise IndexProblem("the AppImageHub feed is too large")
    return data.decode("utf-8", errors="replace")


def _links(item):
    links = item.get("links")
    return [x for x in links if isinstance(x, dict)] if isinstance(links, list) else []


def source_of(item):
    """(catalog source, note) of a feed item: the repository link of the feed, else what AM's classifier makes of
    the download link (a github.com release page, say), else a note."""
    links = _links(item)
    for kind, prefix in LINK_PREFIXES:
        for link in links:
            value = link.get("url")
            if link.get("type") == kind and isinstance(value, str):
                try:
                    return "{}:{}".format(*catalog.parse_source(prefix + value.strip())), ""
                except ValueError:
                    continue
    for link in links:
        value = link.get("url")
        if link.get("type") in ("Download", "Install") and isinstance(value, str):
            source, note = amsource.classify(value.strip())
            if source or note:
                return source, note
    return "", "no source in the index"


def convert(text):
    """The catalog of a feed text. Items with an unusable name are skipped; of names that differ only in case the
    first (by name) is kept. The revision is a hash of the feed, as the feed carries no commit."""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as e:
        raise IndexProblem(f"the AppImageHub feed is not valid JSON: {e}") from e
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise IndexProblem('the AppImageHub feed has no "items" list')
    named = [i for i in items if isinstance(i, dict) and isinstance(i.get("name"), str)
             and catalog.NAME_RE.fullmatch(i["name"])]
    apps, seen = [], set()
    for item in sorted(named, key=lambda i: i["name"]):
        if item["name"].lower() in seen:
            continue
        seen.add(item["name"].lower())
        description = item.get("description")
        description = amsource.shorten(textsafe.clean(description, catalog.DESCRIPTION_MAX)) \
            if isinstance(description, str) else ""
        source, note = source_of(item)
        apps.append(catalog.App(item["name"], description.strip(), source, note))
    if not apps:
        raise IndexProblem("the AppImageHub feed contains no usable apps")
    return catalog.Catalog(tuple(apps), HUB_URL, "sha256:" + hashlib.sha256(text.encode()).hexdigest()[:12])
