import argparse
import sys
from pathlib import Path

from . import __version__
from .uploader import parse_s3_url, upload_tree


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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.source.exists():
        parser.error(f"{args.source} does not exist")
    try:
        bucket, prefix = parse_s3_url(args.destination)
    except ValueError as err:
        parser.error(str(err))

    keys = upload_tree(args.source, bucket, prefix, include=args.include, exclude=args.exclude)
    for key in keys:
        print(f"uploaded: s3://{bucket}/{key}")
    print(f"{len(keys)} file(s) uploaded", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
