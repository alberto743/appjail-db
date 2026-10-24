# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

"""Fetch the two paths of ivan-hc/AM that the catalog needs.

Same hardened, sparse, blobless fetch as appjail's `amsource.fetch`, without the bwrap jail: this runs on an
ephemeral CI runner (or a throwaway directory), and git is never run on the fetched tree beyond the checkout itself.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .amsource import AM_URL
from .catalog import IndexProblem
from .textsafe import clean

COMMIT_RE = re.compile(r"[0-9a-f]{40}")

GIT_SCRIPT = r"""set -eu
G="git -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.attributesFile=/dev/null \
-c submodule.recurse=false -c advice.detachedHead=false -c gc.auto=0 \
-c protocol.allow=never -c protocol.https.allow=always"
$G init -q repo
cd repo
$G config core.repositoryformatversion 1
$G config extensions.partialclone origin
$G remote add origin "$2"
$G config remote.origin.promisor true
$G config remote.origin.partialclonefilter blob:none
$G sparse-checkout set --no-cone /programs/x86_64-appimages /programs/x86_64/
$G fetch -q --depth 1 --filter=blob:none --no-tags --no-recurse-submodules origin "$1"
$G checkout -q --detach FETCH_HEAD
echo "commit $($G rev-parse HEAD)"
"""


@dataclass(frozen=True)
class Fetched:
    commit: str
    tree: Path  # directory containing programs/...


def fetch(workdir, commit="HEAD", url=AM_URL, timeout=1800):
    """Fetch the requested commit (or the remote HEAD) into workdir."""
    if commit != "HEAD" and not COMMIT_RE.fullmatch(commit):
        raise IndexProblem("commit must be a 40-digit lowercase hex id or HEAD")
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    try:
        proc = subprocess.run(["/bin/sh", "-c", GIT_SCRIPT, "sh", commit, url], cwd=workdir, env=env,
                              capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise IndexProblem("git timed out") from None
    if proc.returncode != 0:
        raise IndexProblem("git failed: " + clean(proc.stderr.strip() or f"exit {proc.returncode}", 400))
    out = dict(line.split(" ", 1) for line in proc.stdout.splitlines() if " " in line)
    if not COMMIT_RE.fullmatch(out.get("commit", "")):
        raise IndexProblem("could not determine the fetched commit")
    return Fetched(out["commit"], Path(workdir) / "repo")
