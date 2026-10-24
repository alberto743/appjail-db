# appjail-db

The reference catalog of AppImages for [appjail](https://github.com/alberto743/appjail), rebuilt weekly from the
index of [ivan-hc/AM](https://github.com/ivan-hc/AM) and the feed of [AppImageHub](https://appimage.github.io).

`catalog.json` is an `appjail-catalog` (version 1) document: for each app a name, a description and, where AM or AppImageHub
know it, a kind-prefixed `source` (`github:owner/repo`, `gitlab:...`, `forgejo:...`) or a `note` saying why there is none
(`resolve manually: ...`, `repackager ...`). It only suggests; `appjail add` still verifies the repository.
appjail reads it, pinned to a commit, instead of fetching AM or AppImageHub itself:

    https://raw.githubusercontent.com/alberto743/appjail-db/main/catalog.json

## How it is made

`python -m appjail_db build -o catalog.json` (standard library only, Python 3.12+):

1. fetches `programs/x86_64-appimages` and `programs/x86_64/` of AM with a sparse, blobless, hardened `git` fetch;
2. reads the list (`◆ name : description`) and each app's install script as plain text; a regex finds the first
   `SITE=` (and `SITE2=`, noted as repackager) and keeps only the first 100 characters of each description (see
   Licensing). Nothing from AM is ever executed or sourced;
3. downloads AppImageHub's `https://appimage.github.io/feed.json` (https only, same-host redirects only, at most
   16 MB) and merges it, without duplicates (see below). If the feed cannot be had the build fails and the catalog
   stays as it is;
4. validates the result with the same rules appjail applies, and refuses it if it has fewer than 5000 apps or
   shrinks by more than 10% against the committed one (an AM layout change must not publish a gutted catalog);
5. leaves `catalog.json` untouched when the apps are unchanged, so only real changes make a commit.

Merge rules (`merge.py`): an app is the same in both when its repository is the same and holds only that app on both
sides (a repository may publish several apps), or else when the name is the same ignoring case. The merged app keeps
AM's name and takes AppImageHub's description and source (AM's where the feed has none). When the name is the same but
the repositories differ, the app has no `source` and its `note` says `resolve manually: AM owner/repo; AppImageHub
owner/repo`: which one is right is for the user to decide at `appjail add`. Apps in only one of the two are kept as
they are, except that an app with no `source` and no pointer in its `note` (only "no source in the index" or "no
install script in the index") is dropped, whichever catalog it came from: there is nothing to do with it.

Texts are then sanitized (`sanitize.py`, on top of appjail's `textsafe.py`): invisible and formatting characters
(Unicode categories Cf, Zl, Zp, Co, Cs, Cn and the tag block) are stripped from descriptions and notes; zero-width
joiner and non-joiner and variation selectors stay, as emoji and some scripts need them. This never stops the
build: what was stripped is listed in the `--report` file and so in the commit message.

Options: `--hub-feed FILE` (a feed already downloaded), `--no-hub` (AM only), `--report FILE` (apps whose source
changed owner, texts that were sanitized), `--tree DIR` (an already fetched AM tree), `--commit SHA` (a specific AM commit), `--min-apps N`.

`catalog.py` and `textsafe.py` are copies of appjail's modules of the same name; keep them in step with appjail when
its format changes. `amsource.py`, `hubsource.py` and `merge.py` exist only here: appjail no longer reads AM, it asks the GitHub API for the latest
commit of this repository and downloads `catalog.json` at that commit (`appjail index update`, or `--commit SHA`).

## Weekly update

`.github/workflows/update.yml` runs every Monday (and on demand) in two jobs. `test` is read-only and the only one that
installs packages (pytest, ruff). `update` uses the standard library only, builds the catalog and, if it changed, commits
and pushes it as `github-actions[bot]`; the write token is not stored by checkout and reaches only the push step. Apps
whose source moved to a different owner are listed in the commit message, so a repointed app is visible in the history
(appjail also shows such changes at `index update`); the subject names the AM commit and AppImageHub. Requirements:

- Settings → Actions → General → Workflow permissions: *Read and write*.
- `main` may be protected (and should be: enable two-factor authentication and restrict who can push), but the ruleset
  must let the workflow push directly, i.e. allow bypass for GitHub Actions and no required pull requests.
  `catalog.json` is not signed: its integrity rests on HTTPS and on who can write to this repository.
- GitHub pauses scheduled workflows after 60 days without repository activity; run the workflow manually to resume.

## Development

    python3 -m pip install pytest ruff
    python3 -m pytest

## Licensing

- **Code:** MPL-2.0 (see `LICENSES/`).
- **`catalog.json`:** CC0-1.0. It is a mechanical compilation of facts (app names, and where each app comes from).
  To the extent any rights exist in the compilation, they are dedicated to the public domain.

### What the catalog contains

- Names and repository links, which are facts.
- Descriptions, cut to 100 characters, as a label and not a copy of the text. They originate from the upstream
  projects' own texts (their GitHub description, `.desktop` comment or AppStream summary), which reach us through the
  two sources below. No claim is made over them.

### Sources

| Source | Its license | What is taken |
|---|---|---|
| [ivan-hc/AM](https://github.com/ivan-hc/AM) | GPL-3.0 | App list, `SITE=` values, short descriptions. No AM code is included. |
| [AppImageHub](https://appimage.github.io) | MIT, © Simon Peter and contributors | Names, repository links, short descriptions from its `feed.json`. No code or data files of that repository are included. |

### Removal

If you hold rights in something published here and want it changed or removed, open an issue.
