import os

from conftest import BUCKET

from s3up.uploader import MB, Uploader, sha256_file


def keys(s3, prefix=""):
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return sorted(obj["Key"] for obj in response.get("Contents", []))


def test_uploads_tree_and_records_sha256(s3, tree):
    summary = Uploader(s3).upload_tree(tree, BUCKET, "site")

    assert summary.failed == []
    assert keys(s3) == [
        "site/css/site.css",
        "site/index.html",
        "site/logs/app.log",
        "site/reports/2026/q3.csv",
    ]
    head = s3.head_object(Bucket=BUCKET, Key="site/index.html")
    assert head["Metadata"]["sha256"] == sha256_file(tree / "index.html")


def test_second_run_skips_unchanged_files(s3, tree):
    uploader = Uploader(s3)
    uploader.upload_tree(tree, BUCKET)
    (tree / "index.html").write_bytes(b"<h1>changed</h1>")

    summary = uploader.upload_tree(tree, BUCKET)

    assert summary.uploaded == ["index.html"]
    assert len(summary.unchanged) == 3


def test_force_uploads_everything(s3, tree):
    uploader = Uploader(s3)
    uploader.upload_tree(tree, BUCKET)

    summary = uploader.upload_tree(tree, BUCKET, force=True)

    assert len(summary.uploaded) == 4
    assert summary.unchanged == []


def test_dry_run_writes_nothing(s3, tree):
    summary = Uploader(s3).upload_tree(tree, BUCKET, dry_run=True)

    assert len(summary.uploaded) == 4
    assert keys(s3) == []


def test_large_file_goes_up_as_multipart(s3, tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(os.urandom(12 * MB))

    Uploader(s3, chunk_size_mb=5).upload_tree(big, BUCKET, "data")

    head = s3.head_object(Bucket=BUCKET, Key="data/big.bin")
    assert head["ContentLength"] == 12 * MB
    # Multipart ETags end in -<part count>: 12 MB in 5 MB parts is 3 parts.
    assert head["ETag"].strip('"').endswith("-3")
    assert head["Metadata"]["sha256"] == sha256_file(big)


def test_storage_class_and_encryption_are_applied(s3, tree):
    uploader = Uploader(s3, storage_class="STANDARD_IA", sse="AES256")
    uploader.upload_tree(tree / "index.html", BUCKET)

    head = s3.head_object(Bucket=BUCKET, Key="index.html")
    assert head["StorageClass"] == "STANDARD_IA"
    assert head["ServerSideEncryption"] == "AES256"


def test_failures_are_reported_and_other_files_still_upload(s3, tree):
    unreadable = tree / "logs" / "app.log"
    unreadable.chmod(0)
    try:
        summary = Uploader(s3).upload_tree(tree, BUCKET)
    finally:
        unreadable.chmod(0o644)

    if os.geteuid() == 0:  # root can read anything, so nothing fails
        assert summary.failed == []
        return
    assert [key for key, _ in summary.failed] == ["logs/app.log"]
    assert len(summary.uploaded) == 3
