from pathlib import Path

import pytest

from s3up.uploader import iter_files, object_key, parse_s3_url


def relative(paths, root):
    return [p.relative_to(root).as_posix() for p in paths]


def test_iter_files_walks_the_tree_in_order(tree):
    assert relative(iter_files(tree), tree) == [
        "css/site.css",
        "index.html",
        "logs/app.log",
        "reports/2026/q3.csv",
    ]


def test_include_and_exclude_patterns(tree):
    assert relative(iter_files(tree, include=["*.csv", "*.html"]), tree) == [
        "index.html",
        "reports/2026/q3.csv",
    ]
    assert relative(iter_files(tree, exclude=["logs/*"]), tree) == [
        "css/site.css",
        "index.html",
        "reports/2026/q3.csv",
    ]


def test_exclude_wins_over_include(tree):
    assert list(iter_files(tree, include=["*.csv"], exclude=["reports/*"])) == []


def test_single_file_source(tree):
    source = tree / "index.html"
    assert list(iter_files(source)) == [source]
    assert object_key("backup/", source, source) == "backup/index.html"


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [("", "css/site.css"), ("static", "static/css/site.css"), ("/static/", "static/css/site.css")],
)
def test_object_key_keeps_layout_under_prefix(tree, prefix, expected):
    assert object_key(prefix, tree, tree / "css" / "site.css") == expected


def test_parse_s3_url():
    assert parse_s3_url("s3://bucket") == ("bucket", "")
    assert parse_s3_url("s3://bucket/a/b/") == ("bucket", "a/b/")
    for bad in ("bucket/key", "s3://", "https://bucket.s3.amazonaws.com/key"):
        with pytest.raises(ValueError):
            parse_s3_url(bad)


def test_paths_are_posix_style(tree):
    key = object_key("p", tree, tree / Path("reports") / "2026" / "q3.csv")
    assert key == "p/reports/2026/q3.csv"
