import pytest
from unittest.mock import MagicMock, patch


def _make_handler(preset_data: dict):
    from src.chat_handler import ChatHandler
    pm = MagicMock()
    pm.presets = {"custom": preset_data}
    handler = ChatHandler(
        session_manager=MagicMock(),
        memory_manager=MagicMock(),
        chat_processor=MagicMock(),
        research_handler=MagicMock(),
        preset_manager=pm,
        upload_handler=MagicMock(),
    )
    return handler


def test_spirit_preset_sets_character_name_to_spirit_name():
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "ryuzu",
        "grimoire_writes": True,
        "system_prompt": "",
        "character_name": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    })
    temperature, max_tokens, system_prompt, character_name, spirit_name, grimoire_writes = (
        handler.validate_and_extract_preset("custom")
    )
    assert character_name == "ryuzu"
    assert spirit_name == "ryuzu"
    assert grimoire_writes is True
    # No "Your name is ryuzu." prefix — system_prompt should be None
    assert system_prompt is None


def test_spirit_preset_no_name_prefix():
    """Spirit presets must NOT prepend 'Your name is X.' — persona.md owns identity."""
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "beatrice",
        "grimoire_writes": False,
        "system_prompt": "",
        "character_name": "",
        "temperature": 1.0,
        "max_tokens": 0,
    })
    _, _, system_prompt, _, _, grimoire_writes = handler.validate_and_extract_preset("custom")
    assert system_prompt is None or "Your name is" not in (system_prompt or "")
    assert grimoire_writes is False


def test_character_preset_still_gets_name_prefix():
    """Regular character presets (no spirit_name) must still get 'Your name is X.'"""
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "",
        "grimoire_writes": True,
        "system_prompt": "Be helpful.",
        "character_name": "Spark",
        "temperature": 1.0,
        "max_tokens": 0,
    })
    _, _, system_prompt, character_name, spirit_name, _ = handler.validate_and_extract_preset("custom")
    assert character_name == "Spark"
    assert spirit_name == ""
    assert "Your name is Spark." in system_prompt


def test_grimoire_writes_defaults_true_when_absent():
    handler = _make_handler({
        "enabled": True,
        "spirit_name": "echo",
        "system_prompt": "",
        "character_name": "",
        "temperature": 1.0,
        "max_tokens": 0,
        # grimoire_writes not set — should default True
    })
    _, _, _, _, _, grimoire_writes = handler.validate_and_extract_preset("custom")
    assert grimoire_writes is True
