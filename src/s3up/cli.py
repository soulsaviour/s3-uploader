import argparse
import sys
from pathlib import Path

from . import __version__
from .uploader import Uploader, parse_s3_url


STORAGE_CLASSES = [
    "STANDARD",
    "STANDARD_IA",
    "ONEZONE_IA",
    "INTELLIGENT_TIERING",
    "GLACIER_IR",
    "GLACIER",
    "DEEP_ARCHIVE",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s3up", description="Upload a file or a directory tree to S3."
    )
    parser.add_argument("source", type=Path, help="file or directory to upload")
    parser.add_argument("destination", help="s3://bucket[/prefix]")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="only upload paths matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip paths matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=16,
        metavar="MB",
        help="multipart threshold and part size in MB (default 16, minimum 5)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="parts uploaded in parallel per file (default 8)",
    )
    parser.add_argument("--storage-class", choices=STORAGE_CLASSES, help="S3 storage class")
    parser.add_argument("--sse", choices=["AES256", "aws:kms"], help="server-side encryption")
    parser.add_argument(
        "--kms-key-id", help="KMS key for --sse aws:kms (default: the AWS managed key)"
    )
    parser.add_argument("--progress", action="store_true", help="show per-file progress")
    parser.add_argument(
        "--force", action="store_true", help="upload even when S3 already has identical content"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list what would be uploaded without uploading"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.source.exists():
        parser.error(f"{args.source} does not exist")
    if args.kms_key_id and args.sse != "aws:kms":
        parser.error("--kms-key-id needs --sse aws:kms")
    if args.chunk_size < 5:
        parser.error("--chunk-size must be at least 5 (S3's minimum part size)")
    try:
        bucket, prefix = parse_s3_url(args.destination)
    except ValueError as err:
        parser.error(str(err))

    uploader = Uploader(
        chunk_size_mb=args.chunk_size,
        concurrency=args.concurrency,
        storage_class=args.storage_class,
        sse=args.sse,
        kms_key_id=args.kms_key_id,
        progress=args.progress,
    )
    summary = uploader.upload_tree(
        args.source,
        bucket,
        prefix,
        include=args.include,
        exclude=args.exclude,
        force=args.force,
        dry_run=args.dry_run,
    )

    verb = "would upload" if args.dry_run else "uploaded"
    for key in summary.uploaded:
        print(f"{verb}: s3://{bucket}/{key}")
    for key, error in summary.failed:
        print(f"failed: s3://{bucket}/{key}: {error}", file=sys.stderr)
    print(
        f"{len(summary.uploaded)} {verb}, {len(summary.unchanged)} unchanged, "
        f"{len(summary.failed)} failed",
        file=sys.stderr,
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
