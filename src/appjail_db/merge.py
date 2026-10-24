# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

"""Merge the AM catalog and the AppImageHub catalog into one without duplicates.

An app is the same in both when its source (repository) is the same and that repository holds only that app on both
sides (several apps may be published from one repository), or else when its name is the same ignoring case. The entry
keeps AM's name and takes AppImageHub's description and source. When the names are the same but the repositories
differ, which one is right is not decided here: the entry has no `source` and the note names both.
"""

from . import catalog

# Notes that only say there is nothing to point at (amsource.app_from_script, amsource.classify, hubsource.source_of).
NO_POINTER = {"", "no source in the index", "no install script in the index"}
AM_LABEL = "AM"
HUB_LABEL = "AppImageHub"


def _unique_sources(apps):
    """lowercase source -> app, for the sources that exactly one app has."""
    found = {}
    for app in apps:
        if app.source:
            found.setdefault(app.source.lower(), []).append(app)
    return {source: group[0] for source, group in found.items() if len(group) == 1}


def _short(source):
    return source[len("github:"):] if source.startswith("github:") else source


def combine(am, hub):
    """The one app that stands for am and hub: AM's name, AppImageHub's text."""
    description = hub.description or am.description
    if am.source and hub.source and am.source.lower() != hub.source.lower():
        note = f"resolve manually: {AM_LABEL} {_short(am.source)}; {HUB_LABEL} {_short(hub.source)}"
        return catalog.App(am.name, description, "", note)
    if hub.source:
        return catalog.App(am.name, description, hub.source, hub.note)
    if am.source:
        return catalog.App(am.name, description, am.source, am.note)
    return catalog.App(am.name, description, "", hub.note or am.note)


def drop_unpointed(cat):
    """cat without the apps that have neither a source nor a note pointing somewhere (a site, a repackager, both
    repositories of a clash): nothing can be done with them."""
    return catalog.Catalog(tuple(a for a in cat.apps if a.source or a.note not in NO_POINTER), cat.origin, cat.revision)


def merge(am, hub):
    """The Catalog of both; origin and revision say where each half came from."""
    am_by_source, hub_by_source = _unique_sources(am.apps), _unique_sources(hub.apps)
    am_by_name = {a.name.lower(): a for a in am.apps}
    combined = {a.name: a for a in am.apps}
    taken = set()  # AM apps already merged with a hub app: the first (by name) one wins
    for app in hub.apps:
        twin = None
        if app.source and hub_by_source.get(app.source.lower()) is app:
            twin = am_by_source.get(app.source.lower())
        if twin is None:
            twin = am_by_name.get(app.name.lower())
        if twin is None:
            combined[app.name] = app
        elif twin.name not in taken:
            taken.add(twin.name)
            combined[twin.name] = combine(twin, app)
    return catalog.Catalog(tuple(combined.values()), f"{am.origin} + {hub.origin}".strip(" +"),
                           f"{AM_LABEL} {am.revision}; {HUB_LABEL} {hub.revision}")
