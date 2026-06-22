"""
Unit tests — Settings schema validation.
"""

import pytest
from pydantic import ValidationError

from app.modules.users.settings_schemas import (
    BooleanToggle,
    DefaultModeUpdate,
    DefaultModelUpdate,
    SettingsUpdate,
    ThemeUpdate,
)
from app.core.constants import DefaultMode, DefaultModel, Theme


class TestThemeUpdate:
    """Tests for ThemeUpdate schema."""

    def test_valid_themes(self):
        for theme in Theme:
            update = ThemeUpdate(theme=theme)
            assert update.theme == theme

    def test_invalid_theme(self):
        with pytest.raises(ValidationError):
            ThemeUpdate(theme="neon")

    def test_light_theme(self):
        update = ThemeUpdate(theme="light")
        assert update.theme == Theme.LIGHT

    def test_dark_theme(self):
        update = ThemeUpdate(theme="dark")
        assert update.theme == Theme.DARK

    def test_system_theme(self):
        update = ThemeUpdate(theme="system")
        assert update.theme == Theme.SYSTEM


class TestDefaultModelUpdate:
    """Tests for DefaultModelUpdate schema."""

    def test_valid_models(self):
        for model in DefaultModel:
            update = DefaultModelUpdate(default_model=model)
            assert update.default_model == model

    def test_invalid_model(self):
        with pytest.raises(ValidationError):
            DefaultModelUpdate(default_model="nonexistent-model")

    def test_chatgpt(self):
        update = DefaultModelUpdate(default_model="chatgpt")
        assert update.default_model == DefaultModel.CHATGPT

    def test_claude_sonnet(self):
        update = DefaultModelUpdate(default_model="claude-sonnet-4.5")
        assert update.default_model == DefaultModel.CLAUDE_SONNET


class TestDefaultModeUpdate:
    """Tests for DefaultModeUpdate schema."""

    def test_valid_modes(self):
        for mode in DefaultMode:
            update = DefaultModeUpdate(default_mode=mode)
            assert update.default_mode == mode

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            DefaultModeUpdate(default_mode="invalid-mode")

    def test_youtube_shorts(self):
        update = DefaultModeUpdate(default_mode="youtube-shorts")
        assert update.default_mode == DefaultMode.YOUTUBE_SHORTS


class TestBooleanToggle:
    """Tests for BooleanToggle schema."""

    def test_enable(self):
        toggle = BooleanToggle(enabled=True)
        assert toggle.enabled is True

    def test_disable(self):
        toggle = BooleanToggle(enabled=False)
        assert toggle.enabled is False

    def test_missing_value(self):
        with pytest.raises(ValidationError):
            BooleanToggle()


class TestSettingsUpdate:
    """Tests for SettingsUpdate bulk update schema."""

    def test_partial_update(self):
        update = SettingsUpdate(theme="dark")
        assert update.theme == "dark"
        assert update.default_mode is None
        assert update.default_model is None

    def test_full_update(self):
        update = SettingsUpdate(
            theme="light",
            default_mode="research",
            default_model="gpt-4",
            show_diff_by_default=False,
            auto_detect_intent=False,
        )
        assert update.theme == "light"
        assert update.default_mode == "research"
        assert update.show_diff_by_default is False

    def test_empty_update(self):
        update = SettingsUpdate()
        assert update.theme is None
        assert update.default_mode is None
