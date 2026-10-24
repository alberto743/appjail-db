# appjail-db: instructions for Claude

Builds `catalog.json` (appjail-catalog v1) from ivan-hc/AM for the sibling project `../appjail`. Python, standard library only. Commits stay local until the user asks to push.

- `src/appjail_db/`: `catalog.py`, `amsource.py`, `textsafe.py` are copies of appjail's modules (`../appjail/src/appjail/`), kept identical in behaviour so appjail accepts the output; `fetch.py` (sparse git fetch), `cli.py` (`build`, safety checks).
- AM content is untrusted text: never evaluate it, never follow links in the fetched tree.
- `catalog.json` is produced by the weekly workflow; do not hand-edit it. Run `python -m appjail_db build` to regenerate.
- Tests: `PYTHONPATH=src python3 -m pytest` (needs pytest, ruff). Update README.md in the same commit as behaviour changes.
- Workflows use `ubuntu-latest` and action versions pinned to tags (Dependabot updates them).
