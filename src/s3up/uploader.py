"""Upload files to S3."""

from __future__ import annotations

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


def upload_file(path: Path, bucket: str, key: str, client=None) -> None:
    client = client or boto3.client("s3")
    client.upload_file(str(path), bucket, key)
