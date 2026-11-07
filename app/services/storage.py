"""Async-friendly wrappers around the synchronous MinIO SDK."""

from __future__ import annotations

import asyncio
import io
from datetime import timedelta
from typing import Any

from minio import Minio
from minio.error import S3Error

from app.config import settings

DEFAULT_URL_TTL = timedelta(hours=1)
NOT_FOUND_CODES = {"NoSuchKey", "NoSuchObject", "NoSuchBucket", "NotFound"}


def create_minio_client(endpoint: str | None = None) -> Minio:
    """Build a MinIO client from application settings."""

    return Minio(
        endpoint=endpoint or settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _ttl(expires: timedelta | int) -> timedelta:
    """Normalize URL TTL values to a timedelta."""

    if isinstance(expires, timedelta):
        return expires
    return timedelta(seconds=expires)


async def ensure_bucket(client: Any, bucket: str) -> None:
    """Create the configured bucket when it does not exist yet."""

    exists = await asyncio.to_thread(client.bucket_exists, bucket)
    if not exists:
        await asyncio.to_thread(client.make_bucket, bucket)


async def presigned_put_url(
    client: Any,
    bucket: str,
    object_key: str,
    expires: timedelta | int = DEFAULT_URL_TTL,
) -> str:
    """Return a presigned PUT URL for direct client-to-MinIO upload."""

    ttl = _ttl(expires)

    def _presign() -> str:
        method = getattr(client, "presigned_put_url", None)
        if callable(method):
            return method(bucket, object_key, expires=ttl)
        return client.presigned_put_object(bucket, object_key, expires=ttl)

    return await asyncio.to_thread(_presign)


async def presigned_get_url(
    client: Any,
    bucket: str,
    object_key: str,
    expires: timedelta | int = DEFAULT_URL_TTL,
) -> str:
    """Return a presigned GET URL for playback or thumbnails."""

    ttl = _ttl(expires)

    def _presign() -> str:
        method = getattr(client, "presigned_get_url", None)
        if callable(method):
            return method(bucket, object_key, expires=ttl)
        return client.presigned_get_object(bucket, object_key, expires=ttl)

    return await asyncio.to_thread(_presign)


async def stat_object(client: Any, bucket: str, object_key: str) -> Any | None:
    """Return MinIO object metadata, or None when the object is absent."""

    try:
        return await asyncio.to_thread(client.stat_object, bucket, object_key)
    except S3Error as exc:
        if exc.code in NOT_FOUND_CODES:
            return None
        raise


async def put_object(
    client: Any,
    bucket: str,
    object_key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload in-memory bytes (used for generated placeholder thumbnails)."""

    stream = io.BytesIO(data)
    await asyncio.to_thread(
        client.put_object,
        bucket,
        object_key,
        stream,
        len(data),
        content_type=content_type,
    )


class StorageService:
    """Small convenience facade over the module-level storage functions."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    async def ensure_bucket(self) -> None:
        await ensure_bucket(self.client, self.bucket)

    async def presigned_put_url(
        self,
        object_key: str,
        expires: timedelta | int = DEFAULT_URL_TTL,
    ) -> str:
        return await presigned_put_url(self.client, self.bucket, object_key, expires)

    async def presigned_get_url(
        self,
        object_key: str,
        expires: timedelta | int = DEFAULT_URL_TTL,
    ) -> str:
        return await presigned_get_url(self.client, self.bucket, object_key, expires)

    async def stat_object(self, object_key: str) -> Any | None:
        return await stat_object(self.client, self.bucket, object_key)

    async def put_object(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        await put_object(self.client, self.bucket, object_key, data, content_type)
