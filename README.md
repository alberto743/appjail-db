# appjail-db

The reference catalog of AppImages for [appjail](https://github.com/alberto743/appjail), rebuilt weekly from the
index of [ivan-hc/AM](https://github.com/ivan-hc/AM).

`catalog.json` is an `appjail-catalog` (version 1) document: for each app a name, a description and, where AM knows
it, a kind-prefixed `source` (`github:owner/repo`, `gitlab:...`, `forgejo:...`) or a `note` saying why there is none
(`resolve manually: ...`, `repackager ...`). It only suggests; `appjail add` still verifies the repository.
appjail can read it instead of fetching the whole AM repository:

    https://raw.githubusercontent.com/alberto743/appjail-db/main/catalog.json

## How it is made

`python -m appjail_db build -o catalog.json` (standard library only, Python 3.12+):

1. fetches `programs/x86_64-appimages` and `programs/x86_64/` of AM with a sparse, blobless, hardened `git` fetch;
2. reads the list (`◆ name : description`) and each app's install script as plain text; a regex finds the first
   `SITE=` (and `SITE2=`, noted as repackager). Nothing from AM is ever executed or sourced;
3. validates the result with the same rules appjail applies, and refuses it if it has fewer than 5000 apps or
   shrinks by more than 10% against the committed one (an AM layout change must not publish a gutted catalog);
4. leaves `catalog.json` untouched when the apps are unchanged, so only real changes make a commit.

Options: `--report FILE` (apps whose source changed owner), `--tree DIR` (an already fetched AM tree), `--commit SHA` (a specific AM commit), `--min-apps N`.

`catalog.py`, `amsource.py` and `textsafe.py` are copies of appjail's modules of the same name (without the jail);
keep them in step with appjail when its format changes.

## Weekly update

`.github/workflows/update.yml` runs every Monday (and on demand) in two jobs. `test` is read-only and the only one that
installs packages (pytest, ruff). `update` uses the standard library only, builds the catalog and, if it changed, commits
and pushes it as `github-actions[bot]`; the write token is not stored by checkout and reaches only the push step. Apps
whose source moved to a different owner are listed in the commit message, so a repointed app is visible in the history
(appjail also shows such changes at `index update`). Requirements:

- Settings → Actions → General → Workflow permissions: *Read and write*.
- The default branch must accept pushes from `GITHUB_TOKEN` (no branch protection requiring PRs).
- Protect `main` (ruleset: only you and the bot may push) and enable two-factor authentication: `catalog.json` is not signed, its integrity rests on HTTPS and on who can write to this repository.
- GitHub pauses scheduled workflows after 60 days without repository activity; run the workflow manually to resume.

## Development

    python3 -m pip install pytest ruff
    python3 -m pytest

Licensed under MPL-2.0 (see `LICENSES/`).
