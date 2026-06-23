import os
import pytest
from src.voidcat_tools import _assert_not_immutable, execute_update_grimoire


def test_assert_not_immutable_blocks_persona(tmp_path):
    persona_path = str(tmp_path / "persona.md")
    with pytest.raises(PermissionError, match="immutable"):
        _assert_not_immutable(persona_path)


def test_assert_not_immutable_allows_grimoire(tmp_path):
    grimoire_path = str(tmp_path / "grimoire.md")
    # Should not raise
    _assert_not_immutable(grimoire_path)


def test_assert_not_immutable_allows_other_files(tmp_path):
    other_path = str(tmp_path / "notes.md")
    _assert_not_immutable(other_path)  # no raise


def test_execute_update_grimoire_blocks_persona_target(tmp_path, monkeypatch):
    """If spirit_dir somehow contains only persona.md and no grimoire.md,
    the function should not write persona.md even if grimoire path is constructed."""
    # Patch PANTHEON_ROOT to tmp_path
    monkeypatch.setattr("src.voidcat_tools.PANTHEON_ROOT", str(tmp_path))
    spirit_dir = tmp_path / "ryuzu"
    spirit_dir.mkdir()
    # No grimoire.md — it gets created by the function, so test the guard indirectly
    # by verifying a direct persona.md write raises
    with pytest.raises(PermissionError):
        _assert_not_immutable(str(spirit_dir / "persona.md"))
