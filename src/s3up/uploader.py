"""Upload files and directories to S3."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator, Sequence
from pathlib import Path

import boto3


def parse_s3_url(url: str) -> tuple[str, str]:
    """Split s3://bucket/some/prefix into ("bucket", "some/prefix")."""
    if not url.startswith("s3://"):
        raise ValueError(f"expected an s3:// URL, got {url!r}")
    bucket, _, prefix = url[len("s3://") :].partition("/")
    if not bucket:
        raise ValueError(f"no bucket in {url!r}")
    return bucket, prefix


def iter_files(
    source: Path, include: Sequence[str] = (), exclude: Sequence[str] = ()
) -> Iterator[Path]:
    """Yield source itself if it's a file, or every file below it.

    Glob patterns are matched against the path relative to source, e.g.
    "*.log" or "reports/2026-*/*.csv". Excludes win over includes.
    """
    source = Path(source)
    if source.is_file():
        yield source
        return
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        relative = path.relative_to(source).as_posix()
        if include and not any(fnmatch.fnmatch(relative, pattern) for pattern in include):
            continue
        if any(fnmatch.fnmatch(relative, pattern) for pattern in exclude):
            continue
        yield path


def object_key(prefix: str, source: Path, path: Path) -> str:
    """S3 key for path, keeping its layout relative to source under prefix."""
    source = Path(source)
    relative = path.name if source.is_file() else path.relative_to(source).as_posix()
    prefix = prefix.strip("/")
    return f"{prefix}/{relative}" if prefix else relative


def upload_tree(
    source: Path,
    bucket: str,
    prefix: str = "",
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    client=None,
) -> list[str]:
    """Upload a file or directory; returns the keys written."""
    client = client or boto3.client("s3")
    keys = []
    for path in iter_files(source, include, exclude):
        key = object_key(prefix, source, path)
        client.upload_file(str(path), bucket, key)
        keys.append(key)
    return keys
