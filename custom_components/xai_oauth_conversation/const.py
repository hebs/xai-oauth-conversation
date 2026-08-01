"""Constants for xAI OAuth Conversation."""
from __future__ import annotations

import logging

DOMAIN = "xai_oauth_conversation"


def entry_setting(entry, key: str, default):
    """Return a user setting, preferring values saved by the options flow."""
    return entry.options.get(key, entry.data.get(key, default))


LOGGER = logging.getLogger(__package__)

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES = "expires"
CONF_TOKEN_ENDPOINT = "token_endpoint"
CONF_MODEL = "model"
CONF_PROMPT = "prompt"
CONF_MAX_OUTPUT_TOKENS = "max_output_tokens"
CONF_STT_ENABLED = "stt_enabled"
CONF_TTS_ENABLED = "tts_enabled"
CONF_TTS_VOICE = "tts_voice"
CONF_TTS_LANGUAGE = "tts_language"
CONF_TTS_SPEED = "tts_speed"
CONF_TTS_STREAMING_LATENCY = "tts_streaming_latency"

DEFAULT_NAME = "xAI OAuth (Grok)"
DEFAULT_MODEL = "grok-4.20-0309-reasoning"
MODEL_OPTIONS = (
    "grok-4.5-latest",
    "grok-4.5",
    "grok-4.3-latest",
    "grok-4.3",
    "grok-4.20-reasoning-latest",
    "grok-4.20-non-reasoning-latest",
    "grok-4.20-0309-reasoning",
    "grok-4.20-0309-non-reasoning",
    "grok-latest",
)
DEFAULT_PROMPT = "You are a helpful voice assistant for Home Assistant. Answer concisely and naturally."
DEFAULT_MAX_OUTPUT_TOKENS = 1000
DEFAULT_STT_ENABLED = True
DEFAULT_TTS_ENABLED = True
DEFAULT_TTS_VOICE = "eve"
DEFAULT_TTS_LANGUAGE = "en"
DEFAULT_TTS_SPEED = 1.0
DEFAULT_TTS_STREAMING_LATENCY = 1

STT_LANGUAGES = (
    "ar", "cs", "da", "de", "en", "es", "fa", "fil", "fr", "hi", "id",
    "it", "ja", "ko", "mk", "ms", "nl", "pl", "pt", "ro", "ru", "sv",
    "th", "tr", "vi",
)
TTS_LANGUAGES = (
    "auto", "ar-AE", "ar-EG", "ar-SA", "bn", "de", "en", "es-ES", "es-MX",
    "fr", "hi", "id", "it", "ja", "ko", "pt-BR", "pt-PT", "ru", "tr", "vi",
    "zh",
)
TTS_VOICES = (
    "altair", "ara", "atlas", "carina", "castor", "celeste", "cosmo", "eve",
    "helios", "helix", "iris", "kepler", "leo", "lumen", "luna", "lux", "naksh",
    "orion", "perseus", "rex", "rigel", "sal", "sirius", "ursa", "zagan", "zenith",
)

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
OAUTH_DISCOVERY_URL = "https://auth.x.ai/.well-known/openid-configuration"
OAUTH_SCOPE = "openid profile email offline_access grok-cli:access api:access"
API_BASE_URL = "https://api.x.ai/v1"
