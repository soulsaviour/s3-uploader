import boto3
import pytest
from moto import mock_aws

BUCKET = "test-bucket"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


@pytest.fixture
def tree(tmp_path):
    """A small directory tree to upload."""
    files = {
        "index.html": b"<h1>hello</h1>",
        "css/site.css": b"body { margin: 0 }",
        "logs/app.log": b"started\n",
        "reports/2026/q3.csv": b"region,revenue\nnorth,10\n",
    }
    for name, content in files.items():
        path = tmp_path / "site" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return tmp_path / "site"
