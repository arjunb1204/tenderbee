"""
Unit tests for Backblaze B2 Object Storage adapter and factory.
"""
from pathlib import Path
from backend.services.b2_storage import BackblazeB2Storage
from backend.services.r2_storage import get_object_storage


def test_b2_storage_initialization_defaults():
    storage = BackblazeB2Storage(
        endpoint_url="https://s3.us-west-004.backblazeb2.com",
        key_id="test_key_id",
        application_key="test_app_key",
        bucket_name="test_bucket",
    )
    assert storage.region_name == "us-west-004"
    assert storage.endpoint_url == "https://s3.us-west-004.backblazeb2.com"
    assert storage.bucket_name == "test_bucket"


def test_b2_storage_local_disk_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("B2_APPLICATION_KEY_ID", raising=False)
    monkeypatch.delenv("B2_APPLICATION_KEY", raising=False)
    monkeypatch.delenv("B2_ENDPOINT_URL", raising=False)
    storage = BackblazeB2Storage(endpoint_url="", key_id="", application_key="")
    assert storage.is_configured is False

    test_content = b"%PDF-1.4 test bidder document content"
    res = storage.upload_bytes("b2_test/doc.pdf", test_content)
    assert res["success"] is True
    assert res["backend"] == "local_disk"

    downloaded = storage.download_bytes("b2_test/doc.pdf")
    assert downloaded == test_content
    assert storage.file_exists("b2_test/doc.pdf") is True


def test_get_object_storage_factory(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "b2")
    storage = get_object_storage()
    assert isinstance(storage, BackblazeB2Storage)
