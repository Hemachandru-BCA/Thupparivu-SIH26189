"""
s3_document_store.py
--------------------
DocumentStore interface + optional S3/object-storage adapter (Phase T).

Disabled by default; requires ``boto3`` and bucket configuration.  The
local demo keeps raw documents under ``data/raw`` and needs no cloud
credentials.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

from src.adapters.postgres_repository import AdapterNotConfigured


class DocumentStore(Protocol):
    def put_document(self, key: str, content: bytes,
                     content_type: str = "application/octet-stream") -> str: ...

    def get_document(self, key: str) -> Optional[bytes]: ...

    def list_documents(self, prefix: str = "", limit: int = 100) -> List[str]: ...

    def presigned_url(self, key: str, expires_seconds: int = 3600) -> str: ...


class LocalDocumentStore:
    """Filesystem DocumentStore - the demo default (data/raw)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # prevent traversal
        clean = key.lstrip("/").replace("..", "_")
        return self.root / clean

    def put_document(self, key: str, content: bytes,
                     content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def get_document(self, key: str) -> Optional[bytes]:
        path = self._path(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def list_documents(self, prefix: str = "", limit: int = 100) -> List[str]:
        out = []
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and str(p.relative_to(self.root)).startswith(prefix):
                out.append(str(p.relative_to(self.root)))
                if len(out) >= limit:
                    break
        return out

    def presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        # local store: the path *is* the reference; no signed URLs
        return f"file://{self._path(key)}"


class S3DocumentStore:
    """S3-backed DocumentStore (boto3, lazy import).  Disabled unless
    ``SENTINELGRAPH_S3_BUCKET`` is set."""

    def __init__(self, bucket: Optional[str] = None,
                 prefix: str = "sentinelgraph/") -> None:
        try:
            import boto3  # noqa: F401
        except ImportError as exc:
            raise AdapterNotConfigured(
                "boto3 is not installed. Install with: pip install boto3"
            ) from exc
        self.bucket = bucket or os.environ.get("SENTINELGRAPH_S3_BUCKET")
        if not self.bucket:
            raise AdapterNotConfigured("SENTINELGRAPH_S3_BUCKET is not set")
        self.prefix = prefix
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("s3")
        return self._client

    def put_document(self, key: str, content: bytes,
                     content_type: str = "application/octet-stream") -> str:
        full = f"{self.prefix}{key}"
        self.client.put_object(
            Bucket=self.bucket, Key=full, Body=content, ContentType=content_type
        )
        return f"s3://{self.bucket}/{full}"

    def get_document(self, key: str) -> Optional[bytes]:
        from botocore.exceptions import ClientError

        full = f"{self.prefix}{key}"
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=full)
            return resp["Body"].read()
        except ClientError:
            return None

    def list_documents(self, prefix: str = "", limit: int = 100) -> List[str]:
        resp = self.client.list_objects_v2(
            Bucket=self.bucket, Prefix=f"{self.prefix}{prefix}", MaxKeys=limit
        )
        return [obj["Key"] for obj in resp.get("Contents", [])]

    def presigned_url(self, key: str, expires_seconds: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": f"{self.prefix}{key}"},
            ExpiresIn=expires_seconds,
        )
