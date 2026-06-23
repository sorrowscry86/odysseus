import io
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.preset_manager import PresetManager
from routes.preset_routes import setup_preset_routes
from core.middleware import require_admin


@pytest.fixture
def app(tmp_path):
    pm = PresetManager(str(tmp_path))
    # Save a template to upload avatar for
    pm.save_user_template({
        "id": "tmpl-001",
        "name": "Razor",
        "system_prompt": "Be brief.",
        "temperature": 0.4,
        "max_tokens": 0,
        "avatar_url": "",
        "category": "character",
    })
    fapp = FastAPI()
    fapp.include_router(setup_preset_routes(pm))
    # Bypass require_admin for tests — no auth manager in the minimal test app
    fapp.dependency_overrides[require_admin] = lambda: None
    return fapp, pm, tmp_path


def test_upload_avatar_saves_file(app):
    fapp, pm, tmp_path = app
    client = TestClient(fapp)

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header
    resp = client.post(
        "/api/presets/templates/tmpl-001/avatar",
        files={"file": ("avatar.png", io.BytesIO(fake_png), "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "avatar_url" in data
    assert data["avatar_url"].startswith("/api/presets/avatars/")

    # File exists on disk
    filename = os.path.basename(data["avatar_url"])
    assert os.path.isfile(tmp_path / "avatars" / filename)


def test_upload_avatar_rejects_oversized_file(app):
    fapp, _, _ = app
    client = TestClient(fapp)
    big_data = b"x" * (2 * 1024 * 1024 + 1)  # 2MB + 1 byte
    resp = client.post(
        "/api/presets/templates/tmpl-001/avatar",
        files={"file": ("big.png", io.BytesIO(big_data), "image/png")},
    )
    assert resp.status_code == 413


def test_serve_avatar_returns_file(app):
    fapp, pm, tmp_path = app
    client = TestClient(fapp)

    # Upload first
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    upload_resp = client.post(
        "/api/presets/templates/tmpl-001/avatar",
        files={"file": ("av.png", io.BytesIO(fake_png), "image/png")},
    )
    filename = os.path.basename(upload_resp.json()["avatar_url"])

    serve_resp = client.get(f"/api/presets/avatars/{filename}")
    assert serve_resp.status_code == 200
    assert serve_resp.content == fake_png


def test_serve_avatar_404_for_missing(app):
    fapp, _, _ = app
    client = TestClient(fapp)
    resp = client.get("/api/presets/avatars/nonexistent.png")
    assert resp.status_code == 404
