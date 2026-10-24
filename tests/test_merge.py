# SPDX-FileCopyrightText: 2026 Alberto P
# SPDX-License-Identifier: MPL-2.0

from appjail_db import catalog, merge
from appjail_db.catalog import App


def cat(*apps, origin="o", revision="r"):
    return catalog.Catalog(tuple(apps), origin, revision)


def merged(am, hub):
    return {a.name: a for a in merge.merge(cat(*am, origin="am", revision="1"), cat(*hub, origin="hub", revision="2")).apps}


def test_same_repository_under_different_names_keeps_am_name_and_hub_text():
    apps = merged([App("icq", "old", "github:o/icq")], [App("-ICQ", "new", "github:O/ICQ")])
    assert apps == {"icq": App("icq", "new", "github:O/ICQ")}


def test_same_name_ignoring_case_and_same_repository_is_one_app():
    apps = merged([App("vlc", "am", "github:o/vlc")], [App("VLC", "", "github:o/vlc")])
    assert apps == {"vlc": App("vlc", "am", "github:o/vlc")}


def test_same_name_other_repository_is_left_to_the_user_with_both_in_the_note():
    apps = merged([App("etcher", "am", "github:balena-io/etcher")], [App("Etcher", "hub", "github:resin-io/etcher")])
    assert apps["etcher"] == App("etcher", "hub", "", "resolve manually: AM balena-io/etcher; AppImageHub resin-io/etcher")
    assert len(apps["etcher"].note) < catalog.NOTE_MAX


def test_non_github_sources_keep_their_prefix_in_the_note():
    apps = merged([App("h", "", "gitlab:gitlab.com/g/h")], [App("H", "", "github:p/h")])
    assert apps["h"].note == "resolve manually: AM gitlab:gitlab.com/g/h; AppImageHub p/h"


def test_a_missing_source_on_one_side_is_filled_from_the_other():
    apps = merged([App("a", "", "", "no source in the index"), App("b", "", "github:o/b", "repackager x")],
                  [App("A", "", "github:o/a"), App("B", "", "", "no source in the index")])
    assert apps["a"].source == "github:o/a" and apps["a"].note == ""
    assert apps["b"].source == "github:o/b" and apps["b"].note == "repackager x"


def test_a_repository_with_several_apps_is_not_matched_by_source():
    am = [App("one", "", "github:o/pack"), App("two", "", "github:o/pack")]
    apps = merged(am, [App("Three", "", "github:o/pack")])
    assert set(apps) == {"one", "two", "Three"} and apps["one"].source == "github:o/pack"
    apps = merged([App("solo", "", "github:o/pack")], [App("X", "", "github:o/pack"), App("Y", "", "github:o/pack")])
    assert set(apps) == {"solo", "X", "Y"}


def test_one_am_app_is_merged_with_only_the_first_hub_app():
    apps = merged([App("app", "", "github:o/app")], [App("App", "first", "github:o/app"), App("app2", "", "github:o/app2")])
    assert apps["app"].description == "first" and set(apps) == {"app", "app2"}


def test_hub_only_and_am_only_apps_are_kept_and_the_result_has_no_duplicates():
    am = [App("a", "", "github:o/a"), App("b", "", "github:o/b")]
    hub = [App("B", "", "github:p/b"), App("c", "", "github:o/c")]
    result = merge.merge(cat(*am), cat(*hub))
    parsed = catalog.parse(catalog.dumps(result))
    assert [a.name for a in parsed.apps] == ["a", "b", "c"]
    assert len({a.name.lower() for a in parsed.apps}) == 3


def test_origin_and_revision_name_both_halves():
    result = merge.merge(cat(origin="am", revision="1"), cat(origin="hub", revision="2"))
    assert result.origin == "am + hub" and result.revision == "AM 1; AppImageHub 2"


def test_apps_with_no_source_and_no_pointer_in_the_note_are_dropped():
    cat_ = cat(App("keep-src", "", "github:o/a"), App("keep-site", "", "", "resolve manually: https://x.org/a"),
               App("keep-repack", "", "", "repackager github:o/r"), App("a", "", "", "no source in the index"),
               App("b", "", "", "no install script in the index"), App("c"))
    assert [a.name for a in merge.drop_unpointed(cat_).apps] == ["keep-src", "keep-site", "keep-repack"]
