"""
Backblaze B2 S3-Compatible Object Storage Service for TenderBee.
Provides 100% S3-compatible storage using boto3 for Backblaze B2 Cloud Storage
(10GB Free Tier), presigned download URLs, and local disk fallback for offline development.
"""
import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class BackblazeB2Storage:
    """
    Backblaze B2 Object Storage Adapter using the B2 S3-Compatible API.
    Works seamlessly with Backblaze B2's 10GB Free tier and zero/low-cost Bandwidth Alliance.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        key_id: Optional[str] = None,
        application_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
    ):
        # 1. Endpoint URL (e.g. https://s3.us-west-004.backblazeb2.com)
        raw_endpoint = (
            endpoint_url
            or os.getenv("B2_ENDPOINT_URL")
            or os.getenv("S3_ENDPOINT_URL")
            or ""
        ).strip()
        if raw_endpoint and not raw_endpoint.startswith("http"):
            raw_endpoint = f"https://{raw_endpoint}"
        self.endpoint_url = raw_endpoint

        # 2. Backblaze Credentials (keyID and applicationKey)
        self.access_key_id = (
            key_id
            or os.getenv("B2_APPLICATION_KEY_ID")
            or os.getenv("B2_KEY_ID")
            or os.getenv("S3_ACCESS_KEY_ID")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or ""
        ).strip()
        self.secret_access_key = (
            application_key
            or os.getenv("B2_APPLICATION_KEY")
            or os.getenv("S3_SECRET_ACCESS_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or ""
        ).strip()

        # 3. Bucket Name
        self.bucket_name = (
            bucket_name
            or os.getenv("B2_BUCKET_NAME")
            or os.getenv("S3_BUCKET_NAME")
            or os.getenv("AWS_STORAGE_BUCKET_NAME")
            or "tenderbee"
        ).strip()

        # 4. Region (explicit region_name -> inferred from endpoint_url -> B2_REGION env -> default)
        if region_name:
            self.region_name = region_name.strip()
        else:
            match = re.search(r"s3\.([a-z0-9\-]+)\.backblazeb2\.com", self.endpoint_url)
            if match:
                self.region_name = match.group(1)
            else:
                self.region_name = (os.getenv("B2_REGION") or "us-west-004").strip()

        # Check configuration readiness
        self.is_configured = bool(
            self.endpoint_url and self.access_key_id and self.secret_access_key
        )

        self._client = None
        if self.is_configured:
            try:
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name=self.region_name,
                    config=Config(
                        signature_version="s3v4",
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                )
                logger.info("Backblaze B2 storage client connected: %s (bucket: %s)", self.endpoint_url, self.bucket_name)
            except Exception as e:
                logger.warning("Failed to initialize Backblaze B2 client: %s. Falling back to local disk.", e)
                self.is_configured = False
        else:
            logger.info("Backblaze B2 credentials not fully set. Operating in local filesystem storage mode.")

    def _get_media_root(self) -> Path:
        try:
            return Path(settings.MEDIA_ROOT)
        except Exception:
            return Path(__file__).resolve().parent.parent.parent / "data" / "media"

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Uploads binary bytes to Backblaze B2 (with graceful local disk fallback).
        """
        key = key.lstrip("/")
        if self.is_configured and self._client:
            try:
                extra_args = {"ContentType": content_type}
                if metadata:
                    extra_args["Metadata"] = metadata

                self._client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data,
                    **extra_args,
                )
                remote_url = f"{self.endpoint_url}/{self.bucket_name}/{key}"
                return {
                    "backend": "backblaze_b2",
                    "bucket": self.bucket_name,
                    "key": key,
                    "url": remote_url,
                    "success": True,
                }
            except Exception as e:
                logger.error("Failed to upload to Backblaze B2 (%s): %s. Falling back to local disk.", key, e)

        # Local fallback
        local_path = self._get_media_root() / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)

        return {
            "backend": "local_disk",
            "bucket": "local",
            "key": key,
            "path": str(local_path),
            "url": f"/media/{key}",
            "success": True,
        }

    def upload_file(
        self,
        key: str,
        file_path: Union[str, Path],
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Uploads a local file to Backblaze B2."""
        with open(file_path, "rb") as f:
            data = f.read()
        return self.upload_bytes(
            key=key,
            data=data,
            content_type=content_type or "application/octet-stream",
        )

    def download_bytes(self, key: str) -> Optional[bytes]:
        """Downloads object bytes from Backblaze B2 or local disk."""
        key = key.lstrip("/")
        if self.is_configured and self._client:
            try:
                response = self._client.get_object(Bucket=self.bucket_name, Key=key)
                return response["Body"].read()
            except ClientError as e:
                logger.warning("Object not found in Backblaze B2: %s (%s)", key, e)
            except Exception as e:
                logger.error("Error downloading from Backblaze B2: %s", e)

        # Check local disk
        local_path = self._get_media_root() / key
        if local_path.exists():
            with open(local_path, "rb") as f:
                return f.read()
        return None

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generates a secure temporary pre-signed download URL for a file in Backblaze B2.
        """
        key = key.lstrip("/")
        if self.is_configured and self._client:
            try:
                url = self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
                return url
            except Exception as e:
                logger.error("Failed to generate presigned URL for %s: %s", key, e)
        return None

    def file_exists(self, key: str) -> bool:
        """Checks if a file exists in Backblaze B2 or local disk."""
        key = key.lstrip("/")
        if self.is_configured and self._client:
            try:
                self._client.head_object(Bucket=self.bucket_name, Key=key)
                return True
            except ClientError:
                pass

        local_path = self._get_media_root() / key
        return local_path.exists()

    def delete_file(self, key: str) -> bool:
        """Deletes a file from Backblaze B2 or local disk."""
        key = key.lstrip("/")
        deleted = False
        if self.is_configured and self._client:
            try:
                self._client.delete_object(Bucket=self.bucket_name, Key=key)
                deleted = True
            except Exception as e:
                logger.error("Failed to delete object %s from B2: %s", key, e)

        local_path = self._get_media_root() / key
        if local_path.exists():
            try:
                local_path.unlink()
                deleted = True
            except Exception:
                pass
        return deleted

