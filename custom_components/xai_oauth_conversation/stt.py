"""Speech-to-text entity for xAI OAuth."""
from __future__ import annotations

from collections.abc import AsyncIterable
import logging

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_STT_ENABLED, DEFAULT_STT_ENABLED, STT_LANGUAGES, entry_setting
from .xai_client import XAIOAuthError, transcribe_audio

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the xAI STT entity."""
    if entry_setting(config_entry, CONF_STT_ENABLED, DEFAULT_STT_ENABLED):
        async_add_entities([XAIOAuthSTTEntity(config_entry)])


class XAIOAuthSTTEntity(SpeechToTextEntity):
    """Represent xAI speech-to-text."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_stt"
        self._attr_name = f"{entry.title} Speech-to-text"

    @property
    def supported_languages(self) -> list[str]:
        return list(STT_LANGUAGES)

    @property
    def supported_formats(self) -> list[AudioFormats]:
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        return [
            AudioSampleRates.SAMPLERATE_8000,
            AudioSampleRates.SAMPLERATE_16000,
            AudioSampleRates.SAMPLERATE_22000,
            AudioSampleRates.SAMPLERATE_44100,
            AudioSampleRates.SAMPLERATE_48000,
        ]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        return [AudioChannels.CHANNEL_MONO, AudioChannels.CHANNEL_STEREO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        extension = "wav" if metadata.format == AudioFormats.WAV else "ogg"
        content_type = "audio/wav" if extension == "wav" else "audio/ogg"
        try:
            text = await transcribe_audio(
                self.hass,
                self.entry,
                audio=stream,
                filename=f"assist.{extension}",
                content_type=content_type,
                language=metadata.language,
            )
        except XAIOAuthError:
            _LOGGER.exception("xAI speech-to-text request failed")
            return SpeechResult(None, SpeechResultState.ERROR)
        return SpeechResult(text, SpeechResultState.SUCCESS)
