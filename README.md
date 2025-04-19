# s3up

A small command-line tool for uploading files and directory trees to Amazon S3,
built on boto3. It's meant for the jobs that end up as cron entries and CI
steps: shipping build artifacts, reports or backups to a bucket, where re-runs
should be cheap and failures should be loud.

- **Directories or single files**, with `--include` / `--exclude` globs
- **Multipart uploads** for large files, parts sent in parallel
- **Adaptive retries** that back off when S3 throttles
- **SHA-256 checksums**: S3 verifies every part on arrival
- **Change detection**: files whose content is already in S3 are skipped
- **Storage class and server-side encryption** (SSE-S3 or SSE-KMS)
- **Dry runs**, and a non-zero exit code if any file failed

## Install

```bash
pip install git+https://github.com/<you>/s3-uploader.git
# or, from a clone:
pip install -e .
```

Credentials come from the usual AWS chain: environment variables, a profile
(`AWS_PROFILE`), or an instance or pod role.

## Usage

```bash
# a directory, keeping its layout under a prefix
s3up ./dist s3://my-artifacts/releases/1.4.0

# only the CSVs, skipping drafts
s3up ./reports s3://analytics-drop/2026-10 --include "*.csv" --exclude "drafts/*"

# a large backup: 64 MB parts, 16 in parallel, infrequent-access storage, KMS
s3up db-dump.tar.zst s3://backups/postgres --chunk-size 64 --concurrency 16 \
  --storage-class STANDARD_IA --sse aws:kms --kms-key-id alias/backups --progress

# see what would be uploaded
s3up ./dist s3://my-artifacts/releases/1.4.0 --dry-run
```

Output lists each uploaded object on stdout and a summary on stderr:

```
uploaded: s3://my-artifacts/releases/1.4.0/app.tar.gz
uploaded: s3://my-artifacts/releases/1.4.0/checksums.txt
2 uploaded, 14 unchanged, 0 failed
```

| Option | Default | |
|--------|---------|-|
| `--include GLOB` | all files | Only upload matching paths (repeatable) |
| `--exclude GLOB` | none | Skip matching paths (repeatable, wins over include) |
| `--chunk-size MB` | 16 | Multipart threshold and part size (minimum 5) |
| `--concurrency N` | 8 | Parts uploaded in parallel per file |
| `--storage-class` | `STANDARD` | Any S3 storage class |
| `--sse` | bucket default | `AES256` or `aws:kms` |
| `--kms-key-id` | AWS managed key | Key for `--sse aws:kms` |
| `--force` | off | Upload even if the content is unchanged |
| `--dry-run` | off | List what would be uploaded |
| `--progress` | off | Per-file progress in 25% steps |

Patterns match the path relative to the source directory, so `logs/*` skips
the top-level `logs` directory and `*.log` skips log files at any depth.

## How change detection works

Before uploading, s3up hashes the file and compares the result with the
`sha256` metadata it stored on the existing object (a `HEAD` request per file).
If they match, the file is skipped. S3's ETag can't be used for this: for
multipart uploads it's a hash of the part hashes, so it depends on the part
size.

Uploads also send `ChecksumAlgorithm=SHA256`, so S3 rejects any part that was
corrupted in transit.

## IAM permissions

`s3:PutObject` and `s3:GetObject` (for the `HEAD` check) on the destination
prefix, plus `kms:GenerateDataKey` and `kms:Decrypt` on the key when using
SSE-KMS.

## Development

```bash
pip install -e ".[dev]"
ruff check . && pytest
```

The tests run against moto's S3 mock and cover path filtering, key layout,
change detection, multipart uploads, encryption settings, dry runs, partial
failures and the CLI.
