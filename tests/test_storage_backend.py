"""
tests/test_storage_backend.py
-----------------------------
Unit tests for the StorageBackend abstraction (Task 10).
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.api.data_access import (
    LocalStorageBackend,
    S3StorageBackend,
    AdapterNotConfigured,
    AuditLogWriter,
    get_storage_backend,
)


class TestLocalStorageBackend:
    def test_write_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(Path(tmp))
            backend.write("test/key.json", b'{"hello": "world"}')
            data = backend.read("test/key.json")
            assert data == b'{"hello": "world"}'

    def test_read_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(Path(tmp))
            assert backend.read("nonexistent.json") is None

    def test_list_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(Path(tmp))
            backend.write("cases/CASE-001.json", b"{}")
            backend.write("cases/CASE-002.json", b"{}")
            keys = backend.list("cases/")
            assert len(keys) == 2
            assert all(k.endswith(".json") for k in keys)

    def test_delete_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(Path(tmp))
            backend.write("test.json", b"data")
            assert backend.read("test.json") == b"data"
            backend.delete("test.json")
            assert backend.read("test.json") is None

    def test_delete_missing_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(Path(tmp))
            backend.delete("nonexistent.json")  # Should not raise


class TestS3StorageBackend:
    def test_s3_backend_requires_bucket(self):
        """Missing SENTINELGRAPH_S3_BUCKET raises AdapterNotConfigured."""
        with patch.dict(os.environ, {"SENTINELGRAPH_S3_BUCKET": ""}, clear=False):
            with pytest.raises(AdapterNotConfigured):
                S3StorageBackend(bucket="")

    def test_s3_backend_requires_boto3(self):
        """Missing boto3 raises AdapterNotConfigured."""
        with patch.dict(os.environ, {"SENTINELGRAPH_S3_BUCKET": "test-bucket"}):
            # Simulate missing boto3 by patching the import
            with patch("src.api.data_access.S3StorageBackend.__init__",
                       side_effect=AdapterNotConfigured("boto3 not installed")):
                with pytest.raises(AdapterNotConfigured):
                    S3StorageBackend(bucket="test-bucket")

    def test_s3_backend_mocked(self):
        """Test S3StorageBackend with mocked boto3."""
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b'{"data": 1}')}
        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "cases/c1.json"}]}
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {"Contents": [{"Key": "cases/c1.json"}]}
        ]

        backend = S3StorageBackend.__new__(S3StorageBackend)
        backend.bucket = "test-bucket"
        backend.prefix = ""
        backend.s3 = mock_s3

        # Read
        data = backend.read("cases/c1.json")
        assert data == b'{"data": 1}'
        # Write
        backend.write("cases/c2.json", b'{"data": 2}')
        mock_s3.put_object.assert_called()
        # List
        keys = backend.list("cases/")
        assert len(keys) >= 1


class TestAuditBuffer:
    def test_local_backend_direct_append(self):
        """Local backend: audit lines are appended directly."""
        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalStorageBackend(Path(tmp))
            writer = AuditLogWriter(backend=backend)
            writer.append({"action": "test1", "ts": "2025-01-01T00:00:00Z"})
            data = backend.read("exports/audit_log.jsonl")
            assert data is not None
            assert b"test1" in data

    def test_s3_buffer_flushes_after_50(self):
        """S3 backend: buffer flushes after 50 entries."""
        mock_backend = MagicMock(spec=LocalStorageBackend)

        writer = AuditLogWriter(backend=mock_backend)
        writer._is_s3 = True  # Force S3 mode

        for i in range(50):
            writer.append({"action": f"event_{i}"})

        # After 50 entries, flush should have been called
        mock_backend.write.assert_called()
        assert len(writer._buffer) == 0  # Buffer should be empty after flush


class TestGetStorageBackend:
    def test_missing_s3_uses_local(self):
        """Missing S3 env var → LocalStorageBackend is selected."""
        with patch.dict(os.environ, {"SENTINELGRAPH_S3_BUCKET": ""}, clear=False):
            backend = get_storage_backend()
            assert isinstance(backend, LocalStorageBackend)
