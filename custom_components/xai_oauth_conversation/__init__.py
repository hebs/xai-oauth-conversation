"""xAI OAuth Conversation custom integration."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAX_OUTPUT_TOKENS, CONF_MODEL, CONF_PROMPT, DEFAULT_MAX_OUTPUT_TOKENS, DEFAULT_MODEL, DEFAULT_PROMPT, DOMAIN
from .xai_client import create_response, image_bytes_part, image_url_part, text_part

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _instructions(prompt: str, model: str) -> str:
    return f"{prompt}\n\nCurrent backend model: {model}. If asked which model you use, answer with that exact model name."


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def generate_content(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        model = call.data.get(CONF_MODEL) or entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        system_prompt = entry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        result = await create_response(hass, entry, model=model, instructions=_instructions(system_prompt, model), content=[text_part(call.data[CONF_PROMPT])], max_output_tokens=call.data.get(CONF_MAX_OUTPUT_TOKENS) or entry.data.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS))
        return {"text": result.text}

    async def analyze_image(call: ServiceCall) -> ServiceResponse:
        entry = _get_entry(hass, call.data["config_entry"])
        content: list[dict[str, Any]] = [text_part(call.data[CONF_PROMPT])]
        for url in call.data.get("image_url", []) or []:
            content.append(image_url_part(url))
        for path in call.data.get("image_file", []) or []:
            content.append(await _image_part_from_file(hass, path))
        for entity_id in call.data.get(CONF_ENTITY_ID, []) or []:
            content.append(await _image_part_from_entity(hass, entity_id))
        if len(content) == 1:
            raise ServiceValidationError("Provide image_file, image_url, or entity_id")
        model = call.data.get(CONF_MODEL) or entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        system_prompt = call.data.get("system_prompt") or entry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        result = await create_response(hass, entry, model=model, instructions=_instructions(system_prompt, model), content=content, max_output_tokens=call.data.get(CONF_MAX_OUTPUT_TOKENS) or entry.data.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS))
        return {"response_text": result.text, "text": result.text}

    hass.services.async_register(DOMAIN, "generate_content", generate_content, schema=vol.Schema({vol.Required("config_entry"): selector.ConfigEntrySelector({"integration": DOMAIN}), vol.Required(CONF_PROMPT): str, vol.Optional(CONF_MODEL): str, vol.Optional(CONF_MAX_OUTPUT_TOKENS): int}), supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "analyze_image", analyze_image, schema=vol.Schema({vol.Required("config_entry"): selector.ConfigEntrySelector({"integration": DOMAIN}), vol.Required(CONF_PROMPT): str, vol.Optional("system_prompt"): str, vol.Optional(CONF_MODEL): str, vol.Optional("image_url", default=[]): cv.ensure_list, vol.Optional("image_file", default=[]): cv.ensure_list, vol.Optional(CONF_ENTITY_ID, default=[]): cv.ensure_list, vol.Optional(CONF_MAX_OUTPUT_TOKENS): int}), supports_response=SupportsResponse.ONLY)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _get_entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(f"Invalid config_entry: {entry_id}")
    return entry


async def _image_part_from_file(hass: HomeAssistant, raw_path: str) -> dict[str, Any]:
    path = Path(raw_path) if Path(raw_path).is_absolute() else Path(hass.config.path(raw_path))
    try:
        data = await hass.async_add_executor_job(path.read_bytes)
    except OSError as err:
        raise HomeAssistantError(f"Could not read image file {raw_path}: {err}") from err
    return image_bytes_part(data, mimetypes.guess_type(str(path))[0] or "image/jpeg")


async def _image_part_from_entity(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    domain = entity_id.split(".", 1)[0]
    if domain == "camera":
        from homeassistant.components.camera import async_get_image
        image = await async_get_image(hass, entity_id, timeout=10)
        return image_bytes_part(image.content, image.content_type or "image/jpeg")
    if domain == "image":
        state = hass.states.get(entity_id)
        if state and (entity_picture := state.attributes.get("entity_picture")):
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            from homeassistant.helpers.network import get_url
            url = get_url(hass) + entity_picture if entity_picture.startswith("/") else entity_picture
            async with async_get_clientsession(hass).get(url) as resp:
                data = await resp.read()
                if resp.status >= 400:
                    raise HomeAssistantError(f"Could not fetch image entity {entity_id}: {resp.status}")
                return image_bytes_part(data, resp.headers.get("content-type", "image/jpeg"))
    raise ServiceValidationError(f"Unsupported image entity: {entity_id}")
