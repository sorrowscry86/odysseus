import os
import json
import pytest
from src.preset_manager import PresetManager


@pytest.fixture
def pm(tmp_path):
    return PresetManager(str(tmp_path))


def test_save_template_with_avatar_url(pm):
    tmpl = {
        "id": "test-001",
        "name": "Razor",
        "system_prompt": "Be brief.",
        "temperature": 0.4,
        "max_tokens": 0,
        "avatar_url": "/api/presets/avatars/test-001.png",
        "category": "character",
    }
    assert pm.save_user_template(tmpl)
    saved = pm.get_user_templates()
    assert saved[0]["avatar_url"] == "/api/presets/avatars/test-001.png"
    assert saved[0]["category"] == "character"


def test_delete_template_removes_avatar_file(pm, tmp_path):
    avatars_dir = tmp_path / "avatars"
    avatars_dir.mkdir()
    avatar_file = avatars_dir / "test-002.png"
    avatar_file.write_bytes(b"fake-png")

    tmpl = {
        "id": "test-002",
        "name": "Spark",
        "system_prompt": "Be bright.",
        "temperature": 1.0,
        "max_tokens": 0,
        "avatar_url": "/api/presets/avatars/test-002.png",
        "category": "character",
    }
    pm.save_user_template(tmpl)
    pm.delete_user_template("test-002")

    assert not avatar_file.exists()


def test_delete_template_no_avatar_does_not_crash(pm):
    tmpl = {
        "id": "test-003",
        "name": "Socrates",
        "system_prompt": "Only questions.",
        "temperature": 0.9,
        "max_tokens": 0,
        "avatar_url": "",
        "category": "character",
    }
    pm.save_user_template(tmpl)
    pm.delete_user_template("test-003")  # should not raise
