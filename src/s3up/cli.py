import argparse
import sys
from pathlib import Path

from . import __version__
from .uploader import Uploader, parse_s3_url


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
    parser.add_argument("--progress", action="store_true", help="show per-file progress")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.source.exists():
        parser.error(f"{args.source} does not exist")
    if args.chunk_size < 5:
        parser.error("--chunk-size must be at least 5 (S3's minimum part size)")
    try:
        bucket, prefix = parse_s3_url(args.destination)
    except ValueError as err:
        parser.error(str(err))

    uploader = Uploader(
        chunk_size_mb=args.chunk_size, concurrency=args.concurrency, progress=args.progress
    )
    keys = uploader.upload_tree(
        args.source, bucket, prefix, include=args.include, exclude=args.exclude
    )
    for key in keys:
        print(f"uploaded: s3://{bucket}/{key}")
    print(f"{len(keys)} file(s) uploaded", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
