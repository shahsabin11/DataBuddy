"""Private object storage (MinIO/R2/S3, or local disk for Docker-less dev).

Only the API holds credentials. Callers must authorize against Postgres
before put/get/delete or issuing a signed URL.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import boto3
from botocore.client import BaseClient, Config
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings, get_settings


def dataset_object_key(
    *,
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    dataset_id: uuid.UUID,
    filename: str,
) -> str:
    """Canonical key: institution_id/user_id/dataset_id/<safe name>."""
    safe = filename.rsplit("/", 1)[-1].replace("\\", "_").strip() or "upload.bin"
    if len(safe) > 200:
        safe = safe[-200:]
    return f"{institution_id}/{user_id}/{dataset_id}/{safe}"


def _local_root(settings: Settings) -> Path:
    root = Path(settings.local_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_local_path(settings: Settings, key: str) -> Path:
    root = _local_root(settings).resolve()
    path = (root / key).resolve()
    if not str(path).startswith(str(root) + "/") and path != root:
        raise ValueError("invalid_storage_key")
    return path


@lru_cache
def _client_for(
    endpoint: str | None,
    region: str,
    access_key: str,
    secret_key: str,
    force_path_style: bool,
) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if force_path_style else "auto"},
        ),
    )


def s3_client(settings: Settings | None = None) -> BaseClient:
    settings = settings or get_settings()
    return _client_for(
        settings.s3_endpoint_url,
        settings.s3_region,
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
        settings.s3_force_path_style,
    )


def put_bytes(
    *,
    key: str,
    body: bytes,
    content_type: str,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    if settings.storage_backend == "local":
        path = _safe_local_path(settings, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        # content_type is recorded in Postgres; local disk needs no metadata store.
        return
    # Bucket policy keeps objects private; never set public-read ACLs.
    s3_client(settings).put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


def put_fileobj(
    *,
    key: str,
    body: BinaryIO,
    content_type: str,
    settings: Settings | None = None,
) -> None:
    put_bytes(key=key, body=body.read(), content_type=content_type, settings=settings)


def delete_keys(keys: list[str], settings: Settings | None = None) -> None:
    if not keys:
        return
    settings = settings or get_settings()
    if settings.storage_backend == "local":
        for key in keys:
            path = _safe_local_path(settings, key)
            if path.is_file():
                path.unlink()
        return
    client = s3_client(settings)
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        client.delete_objects(
            Bucket=settings.s3_bucket,
            Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
        )


def _local_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=settings.session_secret,
        salt="databuddy-storage-get-v1",
    )


def presigned_get_url(
    key: str,
    *,
    settings: Settings | None = None,
    expires_in: int | None = None,
) -> str:
    settings = settings or get_settings()
    ttl = expires_in if expires_in is not None else settings.s3_presign_ttl_seconds
    if settings.storage_backend == "local":
        token = _local_serializer(settings).dumps({"key": key})
        return (
            f"{settings.api_url}/api/storage/download"
            f"?token={quote(token, safe='')}"
        )
    return s3_client(settings).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=ttl,
    )


def resolve_local_download_token(
    token: str, *, settings: Settings | None = None
) -> Path:
    settings = settings or get_settings()
    try:
        data = _local_serializer(settings).loads(
            token, max_age=settings.s3_presign_ttl_seconds
        )
    except SignatureExpired as exc:
        raise ValueError("url_expired") from exc
    except BadSignature as exc:
        raise ValueError("url_invalid") from exc
    key = str(data.get("key") or "")
    if not key or ".." in key.split("/"):
        raise ValueError("url_invalid")
    path = _safe_local_path(settings, key)
    if not path.is_file():
        raise ValueError("not_found")
    return path
