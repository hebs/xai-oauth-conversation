"""Constants for xAI OAuth Conversation."""
from __future__ import annotations

import logging

DOMAIN = "xai_oauth_conversation"
LOGGER = logging.getLogger(__package__)

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES = "expires"
CONF_TOKEN_ENDPOINT = "token_endpoint"
CONF_MODEL = "model"
CONF_PROMPT = "prompt"
CONF_MAX_OUTPUT_TOKENS = "max_output_tokens"

DEFAULT_NAME = "xAI OAuth (Grok)"
DEFAULT_MODEL = "grok-4.20-0309-reasoning"
DEFAULT_PROMPT = "You are a helpful voice assistant for Home Assistant. Answer concisely and naturally."
DEFAULT_MAX_OUTPUT_TOKENS = 1000

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
OAUTH_DISCOVERY_URL = "https://auth.x.ai/.well-known/openid-configuration"
OAUTH_SCOPE = "openid profile email offline_access grok-cli:access api:access"
API_BASE_URL = "https://api.x.ai/v1"
