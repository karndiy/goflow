import pytest

from app.core import storage as storage_module
from app.core.storage import StorageError, resolve_path, save_file


def _use_tmp_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))


def test_save_file_writes_bytes_and_returns_storage_key(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    workspace_id = "11111111-1111-1111-1111-111111111111"

    storage_key = save_file(workspace_id, "image/png", b"fake-bytes")

    assert storage_key.startswith(f"{workspace_id}/")
    assert storage_key.endswith(".png")
    assert resolve_path(storage_key).read_bytes() == b"fake-bytes"


def test_save_file_rejects_unsupported_mime_type(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)

    with pytest.raises(StorageError):
        save_file("ws", "application/pdf", b"data")


def test_save_file_rejects_oversized_upload(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(storage_module, "MAX_UPLOAD_SIZE_BYTES", 4)

    with pytest.raises(StorageError):
        save_file("ws", "image/png", b"12345")


def test_resolve_path_rejects_traversal_outside_storage_root(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)

    with pytest.raises(StorageError):
        resolve_path("../../etc/passwd")
