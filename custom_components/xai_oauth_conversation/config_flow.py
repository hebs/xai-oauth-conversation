"""Config flow for xAI OAuth Conversation."""
from __future__ import annotations

import time
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .const import CLIENT_ID, CONF_ACCESS_TOKEN, CONF_EXPIRES, CONF_MAX_OUTPUT_TOKENS, CONF_MODEL, CONF_PROMPT, CONF_REFRESH_TOKEN, CONF_TOKEN_ENDPOINT, DEFAULT_MAX_OUTPUT_TOKENS, DEFAULT_MODEL, DEFAULT_NAME, DEFAULT_PROMPT, DOMAIN, MODEL_OPTIONS, OAUTH_DISCOVERY_URL, OAUTH_SCOPE
from .xai_client import create_response, text_part

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
MODEL_SELECTOR = SelectSelector(
    SelectSelectorConfig(options=list(MODEL_OPTIONS), mode=SelectSelectorMode.DROPDOWN)
)


class XAIOAuthConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle xAI device-code OAuth setup."""

    VERSION = 1
    _oauth_input: dict[str, Any]
    _device: dict[str, Any]

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._oauth_input = {
                "name": user_input.get("name", DEFAULT_NAME),
                CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
                CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                CONF_MAX_OUTPUT_TOKENS: user_input.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS),
            }
            return await self._async_start_device_auth()
        return self.async_show_form(step_id="user", data_schema=self._settings_schema())

    def _settings_schema(self, entry: ConfigEntry | None = None) -> vol.Schema:
        data = {**entry.data, **entry.options} if entry else {}
        return vol.Schema({
            vol.Optional("name", default=entry.title if entry else DEFAULT_NAME): str,
            vol.Optional(CONF_MODEL, default=data.get(CONF_MODEL, DEFAULT_MODEL)): MODEL_SELECTOR,
            vol.Optional(CONF_PROMPT, default=data.get(CONF_PROMPT, DEFAULT_PROMPT)): str,
            vol.Optional(CONF_MAX_OUTPUT_TOKENS, default=data.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS)): int,
        })

    async def _async_start_device_auth(self) -> ConfigFlowResult:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(OAUTH_DISCOVERY_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                discovery = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise ValueError(f"discovery returned {resp.status}")
            device_endpoint = discovery["device_authorization_endpoint"]
            token_endpoint = discovery["token_endpoint"]
            if not str(device_endpoint).startswith("https://") or not str(token_endpoint).startswith("https://"):
                raise ValueError("untrusted OAuth endpoint")
            async with session.post(device_endpoint, data={"client_id": CLIENT_ID, "scope": OAUTH_SCOPE}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                device = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise ValueError(str(device.get("error_description") or device.get("error")))
        except Exception as err:
            return self.async_abort(reason="oauth_start_failed", description_placeholders={"details": str(err)[:200]})
        self._device = {**device, CONF_TOKEN_ENDPOINT: token_endpoint}
        return self._show_device_form()

    def _show_device_form(self, error: str | None = None) -> ConfigFlowResult:
        url = self._device.get("verification_uri_complete") or self._device.get("verification_uri")
        errors = {"base": error} if error else None
        return self.async_show_form(
            step_id="device_auth",
            data_schema=vol.Schema({vol.Required("authorization_complete", default=False): bool}),
            errors=errors,
            description_placeholders={"verification_url": str(url), "user_code": str(self._device.get("user_code", ""))},
        )

    async def async_step_device_auth(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None or not user_input.get("authorization_complete"):
            return self._show_device_form("authorization_not_complete" if user_input else None)
        session = async_get_clientsession(self.hass)
        async with session.post(
            self._device[CONF_TOKEN_ENDPOINT],
            data={"grant_type": DEVICE_GRANT, "client_id": CLIENT_ID, "device_code": self._device["device_code"]},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            token = await resp.json(content_type=None)
            if resp.status >= 400:
                error = token.get("error")
                if error in ("authorization_pending", "slow_down"):
                    return self._show_device_form("authorization_pending")
                return self.async_abort(reason="oauth_failed", description_placeholders={"details": str(token.get("error_description") or error)[:200]})
        return await self._async_finish_oauth(token)

    async def _async_finish_oauth(self, token: dict[str, Any]) -> ConfigFlowResult:
        access = token.get("access_token")
        refresh = token.get("refresh_token")
        if not access or not refresh:
            return self.async_abort(reason="oauth_error")
        data = {
            CONF_ACCESS_TOKEN: access,
            CONF_REFRESH_TOKEN: refresh,
            CONF_EXPIRES: int((time.time() + int(token.get("expires_in") or 3600)) * 1000),
            CONF_TOKEN_ENDPOINT: self._device[CONF_TOKEN_ENDPOINT],
            CONF_MODEL: self._oauth_input[CONF_MODEL],
            CONF_PROMPT: self._oauth_input[CONF_PROMPT],
            CONF_MAX_OUTPUT_TOKENS: self._oauth_input[CONF_MAX_OUTPUT_TOKENS],
        }
        temp_entry = type("TempEntry", (), {"data": data, "title": self._oauth_input["name"]})()
        try:
            await create_response(self.hass, temp_entry, model=data[CONF_MODEL], instructions="Reply with exactly: ok", content=[text_part("ok")], max_output_tokens=20)
        except Exception:
            return self.async_abort(reason="cannot_connect")
        if self.context.get("source") == "reauth":
            entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_create_entry(title=self._oauth_input["name"], data=data)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            updates = {CONF_MODEL: user_input[CONF_MODEL], CONF_PROMPT: user_input[CONF_PROMPT], CONF_MAX_OUTPUT_TOKENS: user_input[CONF_MAX_OUTPUT_TOKENS]}
            return self.async_update_reload_and_abort(entry, data_updates=updates, title=user_input.get("name", entry.title))
        return self.async_show_form(step_id="reconfigure", data_schema=self._settings_schema(entry))

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        self._oauth_input = {"name": entry.title, CONF_MODEL: entry_data.get(CONF_MODEL, DEFAULT_MODEL), CONF_PROMPT: entry_data.get(CONF_PROMPT, DEFAULT_PROMPT), CONF_MAX_OUTPUT_TOKENS: entry_data.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS)}
        return await self._async_start_device_auth()

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        return XAIOAuthOptionsFlow()


class XAIOAuthOptionsFlow(OptionsFlow):
    """Allow changing the model and assistant defaults from the gear button."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            name = user_input.pop("name", self.config_entry.title)
            self.hass.config_entries.async_update_entry(self.config_entry, title=name)
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema({
            vol.Optional("name", default=self.config_entry.title): str,
            vol.Optional(CONF_MODEL, default=data.get(CONF_MODEL, DEFAULT_MODEL)): MODEL_SELECTOR,
            vol.Optional(CONF_PROMPT, default=data.get(CONF_PROMPT, DEFAULT_PROMPT)): str,
            vol.Optional(CONF_MAX_OUTPUT_TOKENS, default=data.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS)): int,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
