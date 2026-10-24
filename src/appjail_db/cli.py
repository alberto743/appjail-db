# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

"""`python -m appjail_db build`: regenerate catalog.json from ivan-hc/AM and AppImageHub (appimage.github.io).

The output is only replaced by a catalog that parses under appjail's own rules and is not suspiciously smaller than
the one it replaces. Apps whose source moved to a different owner are reported (`--report`), so the weekly commit
message shows them. When the apps are unchanged the file is left alone, so a new AM commit that touches neither the
list nor the scripts makes no diff (and no commit in the weekly workflow).
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from . import amsource, catalog, fetch, hubsource, merge
from .catalog import IndexProblem

MIN_APPS = 5000
MAX_SHRINK = 0.10
MAX_REPORTED = 50


def load(path):
    """The catalog at path, or None when there is none yet or it is unreadable."""
    try:
        return catalog.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, IndexProblem):
        return None


def check(new, old, min_apps):
    """Refuse a catalog that looks like a broken conversion rather than a real change of AM."""
    if len(new.apps) < min_apps:
        raise IndexProblem(f"only {len(new.apps)} apps, fewer than the minimum of {min_apps}")
    if old is not None and len(new.apps) < len(old.apps) * (1 - MAX_SHRINK):
        raise IndexProblem(f"{len(new.apps)} apps against {len(old.apps)} in the current catalog: "
                           f"a drop of more than {MAX_SHRINK:.0%}")


def owner_changes(old, new):
    """(name, old source, new source) of the apps whose source has a different kind, host or owner."""
    before = {a.name: a.source for a in old.apps}
    return [(a.name, before[a.name], a.source) for a in new.apps
            if before.get(a.name) and a.source and catalog.identity(before[a.name]) != catalog.identity(a.source)]


def report_lines(changes):
    lines = [f"{name}: {x} -> {y}" for name, x, y in changes[:MAX_REPORTED]]
    if len(changes) > MAX_REPORTED:
        lines.append(f"... and {len(changes) - MAX_REPORTED} more")
    return lines


def build(out, tree=None, commit="HEAD", min_apps=MIN_APPS, report=None, *, hub_feed=None):
    """Write the catalog to out; return "updated" or "unchanged". With report, the owner changes go there (one per line).
    With hub_feed (the text of the AppImageHub feed) its apps are merged into AM's."""
    if tree is not None:
        cat = amsource.convert(tree, commit if commit != "HEAD" else "")
    else:
        with tempfile.TemporaryDirectory(prefix="appjail-db-") as work:
            fetched = fetch.fetch(work, commit)
            cat = amsource.convert(fetched.tree, fetched.commit)
    if hub_feed is not None:
        cat = merge.merge(cat, hubsource.convert(hub_feed))
    cat = merge.drop_unpointed(cat)
    text = catalog.dumps(cat)
    cat = catalog.parse(text)  # what is written is what appjail will read (apps sorted by name)
    old = load(out)
    check(cat, old, min_apps)
    if old is not None and old.apps == cat.apps:
        return "unchanged"
    lines = report_lines(owner_changes(old, cat)) if old is not None else []
    if report is not None:
        Path(report).write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    tmp = f"{out}.tmp"
    Path(tmp).write_text(text, encoding="utf-8")
    os.replace(tmp, out)
    return "updated"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="appjail-db", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="fetch AM and AppImageHub and write the catalog")
    b.add_argument("-o", "--output", default="catalog.json")
    b.add_argument("--commit", default="HEAD", help="AM commit (40 hex digits) or HEAD")
    b.add_argument("--tree", help="use an already fetched AM tree (containing programs/) instead of fetching")
    b.add_argument("--hub-feed", help="use this AppImageHub feed.json file instead of fetching it")
    b.add_argument("--no-hub", action="store_true", help="AM only: do not merge AppImageHub")
    b.add_argument("--report", help="write the apps whose source changed owner to this file")
    b.add_argument("--min-apps", type=int, default=MIN_APPS)
    args = parser.parse_args(argv)
    try:
        hub_feed = None
        if args.hub_feed:
            hub_feed = amsource.read_text(args.hub_feed, hubsource.MAX_FEED_BYTES)
            if hub_feed is None:
                raise IndexProblem("cannot read the AppImageHub feed file")
        elif not args.no_hub:
            hub_feed = hubsource.fetch_feed()
        print(build(args.output, args.tree, args.commit, args.min_apps, args.report, hub_feed=hub_feed))
    except IndexProblem as e:
        print(f"appjail-db: {e}", file=sys.stderr)
        return 1
    return 0
