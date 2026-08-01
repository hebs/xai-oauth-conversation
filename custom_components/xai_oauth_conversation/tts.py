"""Text-to-speech entity for xAI OAuth."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from homeassistant.components.tts import (
    ATTR_VOICE,
    TTSAudioRequest,
    TTSAudioResponse,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_TTS_ENABLED,
    CONF_TTS_LANGUAGE,
    CONF_TTS_SPEED,
    CONF_TTS_STREAMING_LATENCY,
    CONF_TTS_VOICE,
    DEFAULT_TTS_ENABLED,
    DEFAULT_TTS_LANGUAGE,
    DEFAULT_TTS_SPEED,
    DEFAULT_TTS_STREAMING_LATENCY,
    DEFAULT_TTS_VOICE,
    TTS_LANGUAGES,
    TTS_VOICES,
    entry_setting,
)
from .xai_client import stream_speech


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the xAI TTS entity."""
    if entry_setting(config_entry, CONF_TTS_ENABLED, DEFAULT_TTS_ENABLED):
        async_add_entities([XAIOAuthTTSEntity(config_entry)])


class XAIOAuthTTSEntity(TextToSpeechEntity):
    """Represent xAI text-to-speech."""

    _attr_supported_languages = list(TTS_LANGUAGES)
    _attr_supported_options = [ATTR_VOICE]

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tts"
        self._attr_name = f"{entry.title} Text-to-speech"
        self._attr_default_language = entry_setting(
            entry, CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE
        )
        self._attr_default_options = {
            ATTR_VOICE: entry_setting(entry, CONF_TTS_VOICE, DEFAULT_TTS_VOICE)
        }

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return the xAI voice catalog."""
        return [Voice(voice, voice.title()) for voice in TTS_VOICES]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Generate complete MP3 speech audio."""
        audio = b"".join(
            [chunk async for chunk in self._stream(message, language, options)]
        )
        return "mp3", audio

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Stream MP3 speech audio as soon as xAI returns it."""
        message = "".join([chunk async for chunk in request.message_gen])
        return TTSAudioResponse(
            "mp3", self._stream(message, request.language, request.options)
        )

    async def _stream(
        self, message: str, language: str, options: dict[str, Any]
    ) -> AsyncGenerator[bytes]:
        voice = options.get(
            ATTR_VOICE, entry_setting(self.entry, CONF_TTS_VOICE, DEFAULT_TTS_VOICE)
        )
        async for chunk in stream_speech(
            self.hass,
            self.entry,
            text=message,
            voice=voice,
            language=language or entry_setting(
                self.entry, CONF_TTS_LANGUAGE, DEFAULT_TTS_LANGUAGE
            ),
            speed=float(entry_setting(self.entry, CONF_TTS_SPEED, DEFAULT_TTS_SPEED)),
            streaming_latency=int(
                entry_setting(
                    self.entry,
                    CONF_TTS_STREAMING_LATENCY,
                    DEFAULT_TTS_STREAMING_LATENCY,
                )
            ),
        ):
            yield chunk
