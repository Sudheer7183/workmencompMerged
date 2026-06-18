"""
test_s3_service.py — Phase 5 unit tests.

Tests for S3Service using moto[s3] mock — no real S3 or MinIO connection needed.
Per the Phase 5 implementation prompt test spec.
"""
from __future__ import annotations

import pytest
import boto3
from moto import mock_aws
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from app.services.s3_service import S3Service
from app.core.config import Settings


TEST_BUCKET = "audit-platform-uploads"
TEST_REGION = "us-east-1"


# ── moto S3 fixture ───────────────────────────────────────────────────────────


@pytest.fixture
def moto_s3_bucket():
    """Uses moto to mock AWS S3. Creates the test bucket before each test."""
    with mock_aws():
        s3 = boto3.client(
            "s3",
            region_name=TEST_REGION,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        s3.create_bucket(Bucket=TEST_BUCKET)
        yield s3


@pytest.fixture
def mock_settings():
    """Returns a mock Settings object pointing at the moto test bucket."""
    settings = MagicMock(spec=Settings)
    settings.S3_BUCKET = TEST_BUCKET
    settings.AWS_REGION = TEST_REGION
    settings.AWS_ACCESS_KEY_ID = "test"
    settings.AWS_SECRET_ACCESS_KEY = "test"
    settings.S3_ENDPOINT_URL = ""
    return settings


@pytest.fixture
def svc(mock_settings) -> S3Service:
    with patch("app.services.s3_service.get_settings", return_value=mock_settings):
        yield S3Service()


# ── Upload tests ──────────────────────────────────────────────────────────────


def test_upload_bytes_succeeds(moto_s3_bucket, svc: S3Service) -> None:
    """S3Service.upload_bytes returns the key on success"""
    key = "reports/demo/1/policy_audit/test-job.pdf"
    data = b"fake pdf content"
    returned_key = svc.upload_bytes(key=key, data=data, content_type="application/pdf")
    assert returned_key == key


def test_upload_bytes_object_retrievable_after_upload(
    moto_s3_bucket, svc: S3Service
) -> None:
    """After upload_bytes, the object exists in S3"""
    key = "reports/demo/1/policy_audit/test-job.pdf"
    data = b"fake pdf content"
    svc.upload_bytes(key=key, data=data, content_type="application/pdf")

    # Verify via boto3 directly
    obj = moto_s3_bucket.get_object(Bucket=TEST_BUCKET, Key=key)
    assert obj["Body"].read() == data


def test_upload_bytes_raises_on_s3_error() -> None:
    """ClientError from boto3 propagates — not swallowed by S3Service"""
    svc = S3Service()
    mock_client = MagicMock()
    mock_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
        "PutObject",
    )
    mock_settings = MagicMock()
    mock_settings.S3_BUCKET = TEST_BUCKET
    mock_settings.S3_ENDPOINT_URL = ""

    with patch("app.services.s3_service.get_settings", return_value=mock_settings):
        with patch.object(svc, "_client", return_value=mock_client):
            with pytest.raises(ClientError):
                svc.upload_bytes("key", b"data", "application/pdf")


# ── Pre-signed URL tests ───────────────────────────────────────────────────────


def test_presign_url_returns_string(moto_s3_bucket, svc: S3Service) -> None:
    """S3Service.presign_url returns a non-empty string URL"""
    key = "reports/demo/1/policy_audit/test-job.pdf"
    svc.upload_bytes(key=key, data=b"content", content_type="application/pdf")
    url = svc.presign_url(key=key)
    assert isinstance(url, str)
    assert len(url) > 0
    assert "test-job.pdf" in url


def test_presign_url_default_expiry_is_24h(moto_s3_bucket, svc: S3Service) -> None:
    """Default expiry_seconds parameter is 86400 (24 hours)"""
    import inspect
    sig = inspect.signature(svc.presign_url)
    default = sig.parameters["expiry_seconds"].default
    assert default == 86400


# ── key_exists tests ──────────────────────────────────────────────────────────


def test_key_exists_true_after_upload(moto_s3_bucket, svc: S3Service) -> None:
    """key_exists returns True for an object that was just uploaded"""
    key = "reports/demo/1/policy_audit/test-job.pdf"
    svc.upload_bytes(key=key, data=b"content", content_type="application/pdf")
    assert svc.key_exists(key) is True


def test_key_exists_false_for_nonexistent_key(moto_s3_bucket, svc: S3Service) -> None:
    """key_exists returns False when the key does not exist"""
    assert svc.key_exists("nonexistent/key/file.pdf") is False


# ── MinIO path-style test ─────────────────────────────────────────────────────


def test_minio_endpoint_url_sets_path_style() -> None:
    """When S3_ENDPOINT_URL is set, boto3 client uses path-style (signature_version=s3v4)"""
    svc = S3Service()
    mock_settings = MagicMock()
    mock_settings.S3_ENDPOINT_URL = "http://minio:9000"
    mock_settings.AWS_REGION = "us-east-1"
    mock_settings.AWS_ACCESS_KEY_ID = "minioadmin"
    mock_settings.AWS_SECRET_ACCESS_KEY = "minioadmin"

    created_kwargs: dict = {}

    def capture_client(service, **kwargs):  # type: ignore[no-untyped-def]
        created_kwargs.update(kwargs)
        return MagicMock()

    with patch("app.services.s3_service.get_settings", return_value=mock_settings):
        with patch("boto3.client", side_effect=capture_client):
            svc._client()

    assert created_kwargs.get("endpoint_url") == "http://minio:9000"
    assert created_kwargs.get("config") is not None
