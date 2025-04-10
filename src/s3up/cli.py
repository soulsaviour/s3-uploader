import argparse
import sys
from pathlib import Path

from . import __version__
from .uploader import parse_s3_url, upload_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="s3up", description="Upload a file to S3.")
    parser.add_argument("source", type=Path, help="file to upload")
    parser.add_argument("destination", help="s3://bucket[/prefix]")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.source.is_file():
        parser.error(f"{args.source} is not a file")
    try:
        bucket, prefix = parse_s3_url(args.destination)
    except ValueError as err:
        parser.error(str(err))

    key = f"{prefix.strip('/')}/{args.source.name}" if prefix.strip("/") else args.source.name
    upload_file(args.source, bucket, key)
    print(f"uploaded: s3://{bucket}/{key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
