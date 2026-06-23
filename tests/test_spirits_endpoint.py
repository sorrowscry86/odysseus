import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def pantheon(tmp_path):
    """Create a minimal Pantheon structure."""
    for name, has_grimoire in [("ryuzu", True), ("beatrice", True), ("echo", False)]:
        spirit_dir = tmp_path / name
        spirit_dir.mkdir()
        (spirit_dir / "persona.md").write_text(f"# {name} persona")
        if has_grimoire:
            (spirit_dir / "grimoire.md").write_text(f"# {name} grimoire")
    return tmp_path


def test_get_spirits_returns_roster(pantheon, monkeypatch):
    monkeypatch.setenv("PANTHEON_ROOT", str(pantheon))
    # Reimport to pick up new env
    import importlib
    import src.dispatcher as disp
    disp._KNOWN_SPIRITS = []  # reset cache
    monkeypatch.setattr("src.dispatcher.PANTHEON_ROOT", str(pantheon))

    from routes.voidcat_routes import setup_voidcat_routes
    from unittest.mock import MagicMock
    router = setup_voidcat_routes(MagicMock())

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/spirits")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    folders = {s["folder"] for s in data}
    assert "ryuzu" in folders
    assert "beatrice" in folders
    echo_entry = next(s for s in data if s["folder"] == "echo")
    assert echo_entry["has_grimoire"] is False
    ryuzu_entry = next(s for s in data if s["folder"] == "ryuzu")
    assert ryuzu_entry["has_grimoire"] is True


def test_get_spirits_returns_empty_when_pantheon_missing(monkeypatch):
    monkeypatch.setattr("src.dispatcher.PANTHEON_ROOT", "/nonexistent/path")
    import src.dispatcher as disp
    disp._KNOWN_SPIRITS = []

    from routes.voidcat_routes import setup_voidcat_routes
    from unittest.mock import MagicMock
    router = setup_voidcat_routes(MagicMock())

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/spirits")
    assert resp.status_code == 200
    assert resp.json() == []
