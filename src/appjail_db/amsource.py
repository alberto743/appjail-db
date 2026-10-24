# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

"""Convert the two paths of the AM (ivan-hc/AM) tree that appjail reads into a catalog.

The tree is untrusted text: the list and the install script of each listed app are read as plain text (a regex finds
`SITE=`, nothing is evaluated, links are not followed). Copied from appjail's `amsource.py`, minus the jail.
"""

import os
import re
import stat

from . import catalog, textsafe
from .catalog import IndexProblem

AM_URL = "https://github.com/ivan-hc/AM"
LIST_FILE = os.path.join("programs", "x86_64-appimages")
SCRIPT_DIR = os.path.join("programs", "x86_64")
MAX_LIST_BYTES = 8 * 1024 * 1024
MAX_SCRIPT_BYTES = 256 * 1024

# "◆ name : description" (the bullet, and anything before the name, is ignored)
LIST_RE = re.compile(r"^[^\w\s]{0,2}\s*([A-Za-z0-9][A-Za-z0-9._+-]{0,80}) : (.*)$")
# SITE="..." / SITE2='...' / SITE=bare, possibly several assignments on one line
SITE_RE = re.compile(r"""(?:^|[\s;])(SITE2?)=(?:"([^"\n]*)"|'([^'\n]*)'|([^\s"';#]*))""", re.MULTILINE)
GITHUB_URL_RE = re.compile(r"https?://(?:www\.)?github\.com/([^/\s]+/[^/\s#?]+?)(?:\.git)?(?:/.*)?")
# gitlab.com keeps subgroups, so the project path ends at "/-/" (its page separator), a ".git" or the end
GITLAB_URL_RE = re.compile(r"https?://(?:www\.)?gitlab\.com/([^\s#?]+?)(?:\.git)?(?:/-/.*|/)?")
CODEBERG_URL_RE = re.compile(r"https?://(?:www\.)?codeberg\.org/([^/\s]+/[^/\s#?]+?)(?:\.git)?(?:/.*)?")


# -- reading the untrusted tree as text -----------------------------------------------------------


def read_text(path, limit):
    """Read a regular, non-symlink file as text (invalid bytes replaced), at most limit bytes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read(limit).decode("utf-8", errors="replace")
    finally:
        os.close(fd)


def parse_list(text):
    """(name, description) pairs from the AM list file; lines that do not match are skipped."""
    entries = []
    for raw in text.splitlines():
        m = LIST_RE.match(textsafe.clean(raw, 600))
        if m:
            entries.append((m.group(1), m.group(2).strip()))
    return entries


def parse_sites(text):
    """(SITE, SITE2) as first assigned in the script text; '' when absent. Nothing is evaluated."""
    found = {}
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for m in SITE_RE.finditer(code):
        found.setdefault(m.group(1), next(g for g in m.groups()[1:] if g is not None))
    return found.get("SITE", ""), found.get("SITE2", "")


def classify(site):
    """(catalog source, note) for a SITE value: a bare owner/repo or a github.com URL is GitHub, gitlab.com and
    codeberg.org URLs are their forges, anything else is left to the user."""
    if not site:
        return "", "no source in the index"
    if catalog.REPO_RE.fullmatch(site):
        return f"github:{site}", ""
    for regex, prefix in ((GITHUB_URL_RE, "github:"), (GITLAB_URL_RE, "gitlab:gitlab.com/"), (CODEBERG_URL_RE, "codeberg:")):
        m = regex.fullmatch(site)
        if m:
            try:
                return "{}:{}".format(*catalog.parse_source(prefix + m.group(1))), ""
            except ValueError:
                break
    return "", "resolve manually: " + textsafe.clean(site, 100)


def app_from_script(name, description, script):
    if script is None:
        return catalog.App(name, description, "", "no install script in the index")
    site, site2 = parse_sites(script)
    source, note = classify(site)
    if site2:
        repack, _ = classify(site2)
        extra = f"repackager {repack}" if repack else "repackager " + textsafe.clean(site2, 100)
        note = f"{note}; {extra}" if note else extra
    return catalog.App(name, description, source, note)


def _directory(path, what):
    try:
        st = os.lstat(path)
    except OSError:
        raise IndexProblem(f"missing {what} in the fetched tree") from None
    if not stat.S_ISDIR(st.st_mode):
        raise IndexProblem(f"{what} is not a directory")


def convert(tree, revision=""):
    """The catalog of a fetched AM work tree. Only the files named by the list are opened, without following links;
    a link where a directory should be refuses the whole tree."""
    tree = str(tree)
    _directory(os.path.join(tree, "programs"), "programs")
    _directory(os.path.join(tree, SCRIPT_DIR), SCRIPT_DIR)
    text = read_text(os.path.join(tree, LIST_FILE), MAX_LIST_BYTES)
    if text is None:
        raise IndexProblem(f"missing or unusable {LIST_FILE} in the fetched tree")
    apps, seen = [], set()
    for name, description in parse_list(text):
        if name in seen:
            continue
        seen.add(name)
        script = read_text(os.path.join(tree, SCRIPT_DIR, name), MAX_SCRIPT_BYTES)
        apps.append(app_from_script(name, textsafe.clean(description, catalog.DESCRIPTION_MAX), script))
    if not apps:
        raise IndexProblem("the fetched list contains no apps")
    return catalog.Catalog(tuple(apps), AM_URL, revision)
