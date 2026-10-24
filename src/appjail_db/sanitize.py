# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

"""Strip invisible and formatting characters from the texts of a catalog.

`textsafe.clean` (a copy of appjail's) removes escape sequences, control characters and bidirectional overrides; this
goes further, for what is published here: any character of the Unicode categories Cf (format), Zl and Zp (line and
paragraph separators), Co (private use), Cs and Cn, and the tag block (text a person cannot see but a model reads).
Zero-width joiner and non-joiner and variation selectors stay: emoji sequences and some scripts need them.
The categories decide, not a list of code points, so what Unicode adds later is covered. Stripping never fails the
build; what was stripped is reported.
"""

import unicodedata
from collections import Counter

from . import catalog

KEEP = {"‌", "‍", *map(chr, range(0xFE00, 0xFE10))}
CATEGORIES = {"Cf", "Zl", "Zp", "Co", "Cs", "Cn"}
FIELDS = ("description", "note")


def unwanted(ch):
    return ch not in KEEP and (unicodedata.category(ch) in CATEGORIES or 0xE0000 <= ord(ch) <= 0xE007F)


def remove(text):
    """(text without the unwanted characters, Counter of what was removed)."""
    found = Counter(ch for ch in text if unwanted(ch))
    if not found:
        return text, found
    return "".join(ch for ch in text if ch not in found), found


def sanitize(cat):
    """(the Catalog without the unwanted characters, report lines naming what was stripped, per app and field)."""
    apps, lines = [], []
    for app in cat.apps:
        values = {}
        for field in FIELDS:
            values[field], found = remove(getattr(app, field))
            if found:
                chars = ", ".join(f"U+{ord(c):04X}" + (f" x{n}" if n > 1 else "") for c, n in sorted(found.items()))
                lines.append(f"{app.name}: {field}: stripped {chars}")
        apps.append(catalog.App(app.name, values["description"].strip(), app.source, values["note"].strip()))
    return catalog.Catalog(tuple(apps), cat.origin, cat.revision), lines
