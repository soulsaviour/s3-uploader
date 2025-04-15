"""Upload files and directories to S3."""

from __future__ import annotations

import fnmatch
import hashlib
import sys
import threading
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import boto3
from boto3.exceptions import S3UploadFailedError
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

MB = 1024 * 1024


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


def sha256_file(path: Path, chunk_size: int = MB) -> str:
    """Hex SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class Summary:
    uploaded: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


class Progress:
    """Prints how much of a file has been sent, in 25% steps.

    boto3 calls this from several threads during multipart uploads.
    """

    def __init__(self, path: Path, stream=sys.stderr):
        self._name = path.name
        self._size = path.stat().st_size
        self._sent = 0
        self._last_step = -1
        self._lock = threading.Lock()
        self._stream = stream

    def __call__(self, bytes_sent: int) -> None:
        with self._lock:
            self._sent += bytes_sent
            percent = 100 if not self._size else min(100, self._sent * 100 // self._size)
            step = percent // 25
            if step != self._last_step:
                self._last_step = step
                print(f"  {self._name}: {percent}%", file=self._stream)


class Uploader:
    def __init__(
        self,
        client=None,
        *,
        chunk_size_mb: int = 16,
        concurrency: int = 8,
        storage_class: str | None = None,
        sse: str | None = None,
        kms_key_id: str | None = None,
        progress: bool = False,
    ):
        # Adaptive retries back off on throttling (503 SlowDown) as well as
        # transient network errors.
        self.client = client or boto3.client(
            "s3", config=Config(retries={"mode": "adaptive", "max_attempts": 10})
        )
        # Files above the threshold go up as multipart uploads, with parts sent
        # in parallel. S3's minimum part size is 5 MB.
        self.transfer_config = TransferConfig(
            multipart_threshold=chunk_size_mb * MB,
            multipart_chunksize=chunk_size_mb * MB,
            max_concurrency=concurrency,
        )
        self.extra_args: dict = {"ChecksumAlgorithm": "SHA256"}
        if storage_class:
            self.extra_args["StorageClass"] = storage_class
        if sse:
            self.extra_args["ServerSideEncryption"] = sse
        if kms_key_id:
            self.extra_args["SSEKMSKeyId"] = kms_key_id
        self.progress = progress

    def remote_sha256(self, bucket: str, key: str) -> str | None:
        """The sha256 s3up stored on an existing object, or None."""
        try:
            head = self.client.head_object(Bucket=bucket, Key=key)
        except ClientError as err:
            if err.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return head.get("Metadata", {}).get("sha256")

    def upload(
        self, path: Path, bucket: str, key: str, *, force: bool = False, dry_run: bool = False
    ) -> bool:
        """Upload one file. Returns False if S3 already has identical content.

        With dry_run, nothing is written; the return value says whether the
        file would have been uploaded.
        """
        digest = sha256_file(path)
        if not force and self.remote_sha256(bucket, key) == digest:
            return False
        if dry_run:
            return True
        # S3 verifies each part against a SHA-256 checksum on arrival. For
        # multipart uploads S3's own checksum is a checksum of the parts, so
        # the whole-file digest is also kept in metadata to detect changes.
        extra_args = {**self.extra_args, "Metadata": {"sha256": digest}}
        self.client.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs=extra_args,
            Config=self.transfer_config,
            Callback=Progress(path) if self.progress else None,
        )
        return True

    def upload_tree(
        self,
        source: Path,
        bucket: str,
        prefix: str = "",
        *,
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        force: bool = False,
        dry_run: bool = False,
    ) -> Summary:
        """Upload a file or directory. One failed file doesn't stop the rest."""
        summary = Summary()
        for path in iter_files(source, include, exclude):
            key = object_key(prefix, source, path)
            try:
                changed = self.upload(path, bucket, key, force=force, dry_run=dry_run)
            except (ClientError, S3UploadFailedError, OSError) as err:
                summary.failed.append((key, str(err)))
                continue
            (summary.uploaded if changed else summary.unchanged).append(key)
        return summary
