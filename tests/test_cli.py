import pytest
from conftest import BUCKET

from s3up.cli import main


def test_cli_uploads_and_reports(s3, tree, capsys):
    assert main([str(tree), f"s3://{BUCKET}/backup", "--exclude", "logs/*"]) == 0

    out, err = capsys.readouterr()
    assert "uploaded: s3://test-bucket/backup/index.html" in out
    assert "3 uploaded, 0 unchanged, 0 failed" in err


def test_cli_dry_run(s3, tree, capsys):
    assert main([str(tree), f"s3://{BUCKET}", "--dry-run"]) == 0

    out, err = capsys.readouterr()
    assert "would upload: s3://test-bucket/index.html" in out
    assert s3.list_objects_v2(Bucket=BUCKET).get("KeyCount") == 0


@pytest.mark.parametrize(
    "extra",
    [["--chunk-size", "4"], ["--kms-key-id", "alias/x"], ["--sse", "aws:kms", "--chunk-size", "1"]],
)
def test_cli_rejects_bad_options(s3, tree, extra):
    with pytest.raises(SystemExit) as exc:
        main([str(tree), f"s3://{BUCKET}", *extra])
    assert exc.value.code == 2


def test_cli_rejects_missing_source(s3, tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "nope"), f"s3://{BUCKET}"])
