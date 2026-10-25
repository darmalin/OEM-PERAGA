from collections.abc import Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.db import new_id

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client


class Storage(Protocol):
    def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def delete(self, bucket: str, key: str) -> None: ...
    def stream(self, bucket: str, key: str) -> Iterator[bytes]: ...
    def ensure_bucket(self, bucket: str) -> None: ...


def new_object_key(suffix: str = "") -> str:
    """Random object keys so names never leak content."""
    return f"{new_id()}{suffix}"


class S3Storage:
    def __init__(self) -> None:
        s = get_settings()
        # Storage is never reachable from browsers: downloads stream through the API.
        self._client = self._make_client(s.s3_endpoint_url)

    @staticmethod
    def _make_client(endpoint_url: str | None) -> "S3Client":
        s = get_settings()
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=s.s3_access_key.get_secret_value() or None,
            aws_secret_access_key=s.s3_secret_key.get_secret_value() or None,
            region_name=s.s3_region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, bucket: str, key: str) -> bytes:
        return self._client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def delete(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def stream(self, bucket: str, key: str) -> Iterator[bytes]:
        """Chunks of an object. Raises FileNotFoundError at once if it is gone."""
        try:
            body = self._client.get_object(Bucket=bucket, Key=key)["Body"]
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from e
            raise

        def chunks() -> Iterator[bytes]:
            try:
                yield from body.iter_chunks(64 * 1024)
            finally:
                body.close()

        return chunks()

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError:
            self._client.create_bucket(Bucket=bucket)


class MemoryStorage:
    """In-process storage for tests."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self.objects[(bucket, key)] = data

    def get(self, bucket: str, key: str) -> bytes:
        return self.objects[(bucket, key)]

    def delete(self, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    def stream(self, bucket: str, key: str) -> Iterator[bytes]:
        if (bucket, key) not in self.objects:
            raise FileNotFoundError(key)
        return iter([self.objects[(bucket, key)]])

    def ensure_bucket(self, bucket: str) -> None:
        return None


_override: list[Storage] = []


def set_storage(storage: Storage | None) -> None:
    _override.clear()
    if storage is not None:
        _override.append(storage)


@lru_cache
def _default_storage() -> Storage:
    return S3Storage()


def get_storage() -> Storage:
    return _override[0] if _override else _default_storage()
