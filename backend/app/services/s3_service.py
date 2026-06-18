from __future__ import annotations

"""
S3Service — Phase 5.

Wraps boto3 S3 operations for report file storage.
Compatible with both AWS S3 and MinIO (via S3_ENDPOINT_URL override).

Key operations:
  upload_bytes:   Upload report bytes to S3 under a structured key.
  presign_url:    Generate a time-limited pre-signed GET URL.
  key_exists:     Check if an S3 object exists (for idempotency).

S3 key structure for reports:
  reports/{schema_name}/{carrier_id}/{report_type}/{job_id}.{ext}

Atomicity guarantee (V9 S21.2):
  The caller writes the S3 key to report_jobs.file_url ONLY after
  upload_bytes() returns without raising. If upload fails, the DB
  row must not be updated.

Local Docker dev — presigned URL hostname:
  boto3 embeds the endpoint hostname in the SigV4 HMAC signature.
  Post-generation string replacement (minio:9000 → localhost:9000)
  therefore always produces SignatureDoesNotMatch.

  The correct approach: use two separate clients.
    _client()        → uses S3_ENDPOINT_URL (e.g. http://minio:9000)
                        for upload/exists operations inside the container.
    _presign_client() → uses S3_PUBLIC_URL   (e.g. http://localhost:9000)
                        for presigning so the generated URL is already
                        browser-reachable without any post-signing rewrite.

  MinIO is happy to sign with localhost:9000 as long as it receives the
  request on that port — Docker's port mapping (9000:9000) ensures this.
"""

import boto3
import structlog
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class S3Service:
    """
    Thin wrapper around boto3 S3 operations.
    All methods are synchronous — called from within async context via
    run_in_executor if needed, but typically fast enough for direct use.
    """

    def _client(self) -> "boto3.client":  # type: ignore[type-arg]
        """
        Returns a boto3 S3 client pointed at S3_ENDPOINT_URL.
        Used for upload and existence-check operations that run
        inside the container network.
        """
        settings = get_settings()
        kwargs: dict = dict(
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
            kwargs["config"] = boto3.session.Config(  # type: ignore[attr-defined]
                signature_version="s3v4"
            )
        return boto3.client("s3", **kwargs)

    def _presign_client(self) -> "boto3.client":  # type: ignore[type-arg]
        """
        Returns a boto3 S3 client whose endpoint is S3_PUBLIC_URL when set,
        otherwise falls back to S3_ENDPOINT_URL.

        SigV4 embeds the endpoint hostname in the HMAC signature — the URL
        boto3 produces will contain exactly the hostname given here.
        Using S3_PUBLIC_URL (e.g. http://localhost:9000) means the presigned
        URL is already browser-reachable without any post-signing string
        replacement, which would invalidate the signature.

        In production (AWS S3) S3_PUBLIC_URL is left empty and this client
        is identical to _client(), so no behaviour change occurs.
        """
        settings = get_settings()
        presign_endpoint = (
            settings.S3_PUBLIC_URL.rstrip("/")
            if settings.S3_PUBLIC_URL
            else settings.S3_ENDPOINT_URL
        )
        kwargs: dict = dict(
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        if presign_endpoint:
            kwargs["endpoint_url"] = presign_endpoint
            kwargs["config"] = boto3.session.Config(  # type: ignore[attr-defined]
                signature_version="s3v4"
            )
        return boto3.client("s3", **kwargs)

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """
        Uploads data bytes to S3 under the given key.

        Returns the key on success.
        Raises botocore.exceptions.ClientError on S3 failure — caller must
        not write the key to DB until this returns successfully.
        """
        settings = get_settings()
        client = self._client()
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("s3.upload.complete", key=key, size_bytes=len(data))
        return key

    def presign_url(self, key: str, expiry_seconds: int = 86400) -> str:
        """
        Returns a pre-signed GET URL valid for expiry_seconds (default 24h).

        Uses _presign_client() so the URL is signed with the public-facing
        hostname (S3_PUBLIC_URL) rather than the internal Docker hostname
        (S3_ENDPOINT_URL). This avoids SignatureDoesNotMatch errors that
        occur when the browser follows the URL, since SigV4 signs the host.
        """
        settings = get_settings()
        client = self._presign_client()
        url: str = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=expiry_seconds,
        )
        logger.debug("s3.presign.generated", key=key, expiry_seconds=expiry_seconds)
        return url

    def key_exists(self, key: str) -> bool:
        """
        Returns True if the key exists in the configured bucket.
        Used for idempotency checks before re-generating reports.
        """
        settings = get_settings()
        try:
            self._client().head_object(Bucket=settings.S3_BUCKET, Key=key)
            return True
        except ClientError:
            return False