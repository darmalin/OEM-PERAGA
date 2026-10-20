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
    def presigned_url(self, bucket: str, key: str, filename: str) -> str: ...
    def ensure_bucket(self, bucket: str) -> None: ...


def new_object_key(suffix: str = "") -> str:
    """Random object keys so names never leak content."""
    return f"{new_id()}{suffix}"


class S3Storage:
    def __init__(self) -> None:
        s = get_settings()
        self._client = self._make_client(s.s3_endpoint_url)
        # SigV4 signs the host, so links for browsers are signed with the public host.
        self._signer = (
            self._make_client(s.s3_public_endpoint_url)
            if s.s3_public_endpoint_url
            else self._client
        )
        self._ttl = s.presigned_url_ttl_seconds

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

    def presigned_url(self, bucket: str, key: str, filename: str) -> str:
        return self._signer.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=self._ttl,
        )

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

    def presigned_url(self, bucket: str, key: str, filename: str) -> str:
        return f"memory://{bucket}/{key}?filename={filename}"

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
