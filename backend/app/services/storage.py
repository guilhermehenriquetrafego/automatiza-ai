"""
AUTOMATIZA AI — Cloudflare R2 Storage
Free tier: 10GB storage, free egress.
Used to store product images and AI-generated variation images.
"""

import asyncio
import httpx
from typing import Optional
from loguru import logger
from app.core.config import get_settings

settings = get_settings()


class R2Storage:
    """
    Cloudflare R2 storage — S3-compatible API.
    Uses boto3 under the hood for S3 compatibility.
    """

    def __init__(self):
        self.endpoint = settings.R2_ENDPOINT_URL
        self.bucket = settings.R2_BUCKET_NAME
        self.public_url = settings.R2_PUBLIC_URL
        self._client = None

    @property
    def client(self):
        """Lazy-load boto3 S3 client configured for R2."""
        if self._client is None:
            import boto3
            from botocore.config import Config
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
        return self._client

    async def upload(self, data: bytes, key: str, content_type: str = "image/png") -> Optional[str]:
        """Upload bytes to R2 and return the public URL."""
        try:
            # Run in thread pool since boto3 is sync
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._upload_sync, data, key, content_type)
            url = f"{self.public_url}/{key}"
            logger.info(f"Uploaded to R2: {key}")
            return url
        except Exception as e:
            logger.error(f"R2 upload failed for {key}: {e}")
            return None

    def _upload_sync(self, data: bytes, key: str, content_type: str):
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def delete(self, key: str) -> bool:
        """Delete a file from R2."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._delete_sync, key)
            return True
        except Exception as e:
            logger.error(f"R2 delete failed for {key}: {e}")
            return False

    def _delete_sync(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    async def generate_presigned_url(self, key: str, expires: int = 3600) -> str:
        """Generate a time-limited URL for a private file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._presign_sync, key, expires)

    def _presign_sync(self, key: str, expires: int) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )
