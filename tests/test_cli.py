# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

import json
from pathlib import Path

import pytest

from appjail_db import catalog, cli
from appjail_db.catalog import IndexProblem

C1 = "1" * 40


def make_tree(root, n=20, extra=None):
    (root / "programs/x86_64").mkdir(parents=True)
    lines = []
    for i in range(n):
        lines.append(f"◆ app{i} : application number {i}")
        (root / "programs/x86_64" / f"app{i}").write_text(f'SITE="owner/app{i}"\n')
    for name, desc in (extra or {}).items():
        lines.append(f"◆ {name} : {desc}")
        (root / "programs/x86_64" / name).write_text('SITE="o/extra"\n')
    (root / "programs/x86_64-appimages").write_text("\n".join(lines) + "\n")
    return root


def run(out, tree, commit="HEAD", min_apps=10):
    return cli.build(str(out), tree, commit, min_apps)


def test_build_writes_a_catalog_appjail_accepts(tmp_path):
    out = tmp_path / "catalog.json"
    assert run(out, make_tree(tmp_path / "t"), C1) == "updated"
    data = json.loads(out.read_text())
    assert data["format"] == "appjail-catalog" and data["revision"] == C1 and len(data["apps"]) == 20
    assert data["apps"][0] == {"name": "app0", "description": "application number 0", "source": "github:owner/app0"}


def test_unchanged_apps_leave_the_file_alone_even_with_a_new_revision(tmp_path):
    out = tmp_path / "catalog.json"
    tree = make_tree(tmp_path / "t")
    run(out, tree, C1)
    before = out.read_text()
    assert run(out, tree, "2" * 40) == "unchanged"
    assert out.read_text() == before


def test_a_real_change_updates_file_and_revision(tmp_path):
    out = tmp_path / "catalog.json"
    run(out, make_tree(tmp_path / "t"), C1)
    run(out, make_tree(tmp_path / "u", extra={"new": "fresh"}), "2" * 40)
    data = json.loads(out.read_text())
    assert data["revision"] == "2" * 40 and "new" in {a["name"] for a in data["apps"]}


def test_too_few_apps_is_refused_and_the_old_file_kept(tmp_path):
    out = tmp_path / "catalog.json"
    run(out, make_tree(tmp_path / "t"), C1)
    before = out.read_text()
    with pytest.raises(IndexProblem, match="fewer than the minimum"):
        run(out, make_tree(tmp_path / "u", n=5), "2" * 40)
    assert out.read_text() == before


def test_a_large_drop_is_refused(tmp_path):
    out = tmp_path / "catalog.json"
    run(out, make_tree(tmp_path / "t", n=100), C1)
    with pytest.raises(IndexProblem, match="a drop of more than"):
        run(out, make_tree(tmp_path / "u", n=80), "2" * 40)


def test_a_broken_tree_is_refused_and_leaves_no_file(tmp_path):
    out = tmp_path / "catalog.json"
    with pytest.raises(IndexProblem):
        run(out, tmp_path)
    assert not out.exists() and not (tmp_path / "catalog.json.tmp").exists()


def test_main_reports_problems_with_exit_status_1(tmp_path, capsys):
    assert cli.main(["build", "-o", str(tmp_path / "c.json"), "--tree", str(tmp_path)]) == 1
    assert "appjail-db:" in capsys.readouterr().err


def test_main_success(tmp_path, capsys):
    tree = make_tree(tmp_path / "t")
    assert cli.main(["build", "-o", str(tmp_path / "c.json"), "--tree", str(tree), "--min-apps", "10"]) == 0
    assert capsys.readouterr().out.strip() == "updated"


def test_the_committed_catalog_is_valid():
    path = Path(__file__).resolve().parent.parent / "catalog.json"
    assert len(catalog.parse(path.read_text(encoding="utf-8")).apps) >= cli.MIN_APPS


def cat(**sources):
    return catalog.Catalog(tuple(catalog.App(n, "", s) for n, s in sources.items()))


def test_owner_changes_ignore_renames_additions_and_missing_sources():
    old = cat(a="github:o/a", b="github:o/b", c="", d="github:o/d", e="github:o/e")
    new = cat(a="github:o/renamed", b="github:evil/b", c="github:x/c", d="", e="gitlab:gitlab.com/o/e", f="github:z/f")
    assert cli.owner_changes(old, new) == [("b", "github:o/b", "github:evil/b"),
                                           ("e", "github:o/e", "gitlab:gitlab.com/o/e")]


def test_report_is_capped():
    lines = cli.report_lines([(f"a{i}", "github:o/x", "github:p/x") for i in range(cli.MAX_REPORTED + 3)])
    assert len(lines) == cli.MAX_REPORTED + 1 and lines[-1] == "... and 3 more"


def test_build_writes_the_owner_report(tmp_path):
    out, report = tmp_path / "catalog.json", tmp_path / "owners.txt"
    cli.build(str(out), make_tree(tmp_path / "t"), C1, 10, str(report))
    assert report.read_text() == ""
    tree = make_tree(tmp_path / "u")
    (tree / "programs/x86_64/app3").write_text('SITE="evil/app3"\n')
    cli.build(str(out), tree, "2" * 40, 10, str(report))
    assert report.read_text() == "app3: github:owner/app3 -> github:evil/app3\n"


def test_main_passes_the_report_option(tmp_path):
    out, report = tmp_path / "c.json", tmp_path / "r.txt"
    args = ["build", "-o", str(out), "--min-apps", "10", "--report", str(report)]
    cli.main([*args, "--tree", str(make_tree(tmp_path / "t"))])
    assert report.exists()
