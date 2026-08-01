"""Async client for the xAI Responses API using OAuth."""
from __future__ import annotations

import base64
import json
import time
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import aiohttp
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.json import json_dumps

from .const import API_BASE_URL, CLIENT_ID, CONF_ACCESS_TOKEN, CONF_EXPIRES, CONF_REFRESH_TOKEN, CONF_TOKEN_ENDPOINT, LOGGER
from .schema import normalize_tool_schema

MAX_TOOL_ITERATIONS = 10


@dataclass
class XAIResponse:
    text: str
    raw_events: list[dict[str, Any]]


@dataclass
class XAITurn:
    text: str
    function_calls: list[llm.ToolInput]
    raw_events: list[dict[str, Any]]


class XAIOAuthError(Exception):
    """xAI OAuth/API error."""


def _now_ms() -> int:
    return int(time.time() * 1000)


async def refresh_token(hass: HomeAssistant, entry: ConfigEntry) -> str:
    access = entry.data.get(CONF_ACCESS_TOKEN)
    expires = int(entry.data.get(CONF_EXPIRES) or 0)
    if access and expires > _now_ms() + 5 * 60 * 1000:
        return access
    refresh = entry.data.get(CONF_REFRESH_TOKEN)
    endpoint = entry.data.get(CONF_TOKEN_ENDPOINT)
    if not refresh or not endpoint:
        raise XAIOAuthError("Missing OAuth refresh data; reauthenticate the integration")
    session = async_get_clientsession(hass)
    async with session.post(endpoint, data={"grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": refresh}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        text = await resp.text()
        if resp.status >= 400:
            try:
                entry.async_start_reauth(hass)
            except Exception:
                pass
            raise XAIOAuthError(f"OAuth refresh failed ({resp.status}): {text[:300]}")
        payload = json.loads(text)
    new_access = payload.get("access_token")
    if not new_access:
        raise XAIOAuthError("OAuth refresh response was missing access_token")
    new_data = dict(entry.data)
    new_data[CONF_ACCESS_TOKEN] = new_access
    new_data[CONF_REFRESH_TOKEN] = payload.get("refresh_token") or refresh
    new_data[CONF_EXPIRES] = _now_ms() + int(payload.get("expires_in") or 3600) * 1000
    hass.config_entries.async_update_entry(entry, data=new_data)
    LOGGER.info("Refreshed xAI OAuth token for %s", entry.title)
    return new_access


def text_part(text: str) -> dict[str, str]:
    return {"type": "input_text", "text": text}


def image_url_part(url: str) -> dict[str, str]:
    return {"type": "input_image", "image_url": url}


def image_bytes_part(data: bytes, mime_type: str = "image/jpeg") -> dict[str, str]:
    return image_url_part(f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}")


async def _iter_sse(resp: aiohttp.ClientResponse) -> AsyncIterator[dict[str, Any]]:
    event_lines: list[str] = []
    async for raw in resp.content:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if event_lines:
                try:
                    yield json.loads("\n".join(event_lines))
                except json.JSONDecodeError:
                    pass
            event_lines = []
        elif line.startswith("data:"):
            value = line[5:].strip()
            if value != "[DONE]":
                event_lines.append(value)


def _format_tool(tool: llm.Tool, serializer: Callable[[Any], Any] | None) -> dict[str, Any]:
    schema = convert(tool.parameters, custom_serializer=serializer)
    return {"type": "function", "name": tool.name, "description": tool.description, "parameters": normalize_tool_schema(schema), "strict": False}


def _parse_tool_call(item: dict[str, Any]) -> llm.ToolInput | None:
    if item.get("type") != "function_call" or not isinstance(item.get("name"), str):
        return None
    try:
        arguments = json.loads(item.get("arguments") or "{}")
    except (json.JSONDecodeError, TypeError):
        arguments = {}
    return llm.ToolInput(id=str(item.get("call_id") or item.get("id")), tool_name=item["name"], tool_args=arguments if isinstance(arguments, dict) else {})


async def _create_turn(hass: HomeAssistant, entry: ConfigEntry, *, model: str, instructions: str | None, input_items: list[dict[str, Any]], max_output_tokens: int | None = None, tools: list[dict[str, Any]] | None = None) -> XAITurn:
    token = await refresh_token(hass, entry)
    payload: dict[str, Any] = {"model": model, "input": input_items, "instructions": instructions or None, "stream": True, "store": False}
    if max_output_tokens:
        payload["max_output_tokens"] = max_output_tokens
    if tools:
        payload.update({"tools": tools, "tool_choice": "auto"})
    session = async_get_clientsession(hass)
    async with session.post(f"{API_BASE_URL}/responses", json=payload, headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}, timeout=aiohttp.ClientTimeout(total=180)) as resp:
        if resp.status >= 400:
            raise XAIOAuthError(f"xAI response failed ({resp.status}): {(await resp.text())[:500]}")
        chunks: list[str] = []
        calls: list[llm.ToolInput] = []
        events: list[dict[str, Any]] = []
        async for data in _iter_sse(resp):
            events.append(data)
            kind = data.get("type")
            if kind == "response.output_text.delta":
                chunks.append(str(data.get("delta") or ""))
            elif kind == "response.output_text.done" and not chunks:
                chunks.append(str(data.get("text") or ""))
            elif kind == "response.output_item.done" and isinstance(data.get("item"), dict):
                if call := _parse_tool_call(data["item"]):
                    calls.append(call)
            elif kind == "response.failed":
                raise XAIOAuthError(f"xAI response failed: {data}")
    return XAITurn(text="".join(chunks).strip(), function_calls=calls, raw_events=events)


async def create_response(hass: HomeAssistant, entry: ConfigEntry, *, model: str, instructions: str | None, content: list[dict[str, Any]], max_output_tokens: int | None = None) -> XAIResponse:
    turn = await _create_turn(hass, entry, model=model, instructions=instructions, input_items=[{"role": "user", "content": content}], max_output_tokens=max_output_tokens)
    return XAIResponse(text=turn.text, raw_events=turn.raw_events)


async def create_tool_response(hass: HomeAssistant, entry: ConfigEntry, *, model: str, instructions: str, user_text: str, llm_api: llm.APIInstance, max_output_tokens: int | None = None) -> XAIResponse:
    tools = [_format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools]
    input_items: list[dict[str, Any]] = [{"role": "user", "content": [text_part(user_text)]}]
    all_events: list[dict[str, Any]] = []
    for _ in range(MAX_TOOL_ITERATIONS):
        turn = await _create_turn(hass, entry, model=model, instructions=instructions, input_items=input_items, max_output_tokens=max_output_tokens, tools=tools)
        all_events.extend(turn.raw_events)
        if not turn.function_calls:
            return XAIResponse(text=turn.text, raw_events=all_events)
        for call in turn.function_calls:
            input_items.append({"type": "function_call", "name": call.tool_name, "arguments": json_dumps(call.tool_args), "call_id": call.id})
            try:
                result = await llm_api.async_call_tool(call)
            except (Exception, vol.Invalid) as err:
                result = {"error": type(err).__name__, "error_text": str(err)}
            input_items.append({"type": "function_call_output", "call_id": call.id, "output": json_dumps(result)})
    raise XAIOAuthError("Too many tool iterations")


async def transcribe_audio(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    audio: AsyncIterable[bytes],
    filename: str,
    content_type: str,
    language: str,
) -> str:
    """Transcribe an audio stream with xAI STT."""
    token = await refresh_token(hass, entry)
    audio_bytes = bytearray()
    async for chunk in audio:
        audio_bytes.extend(chunk)
    if not audio_bytes:
        raise XAIOAuthError("No audio received")

    form = aiohttp.FormData()
    form.add_field("format", "true")
    form.add_field("language", language.split("-", 1)[0].lower())
    # xAI requires the file field to be the final multipart field.
    form.add_field(
        "file",
        bytes(audio_bytes),
        filename=filename,
        content_type=content_type,
    )
    session = async_get_clientsession(hass)
    async with session.post(
        f"{API_BASE_URL}/stt",
        data=form,
        headers={"Authorization": f"Bearer {token}"},
        timeout=aiohttp.ClientTimeout(total=180),
    ) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise XAIOAuthError(f"xAI STT failed ({resp.status}): {text[:500]}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        raise XAIOAuthError("xAI STT returned invalid JSON") from err
    transcript = payload.get("text")
    if not isinstance(transcript, str):
        raise XAIOAuthError("xAI STT response was missing transcript text")
    return transcript


async def stream_speech(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    text: str,
    voice: str,
    language: str,
    speed: float,
    streaming_latency: int,
) -> AsyncGenerator[bytes]:
    """Stream MP3 speech audio from xAI TTS."""
    token = await refresh_token(hass, entry)
    payload = {
        "text": text,
        "voice_id": voice,
        "language": language,
        "speed": speed,
        "optimize_streaming_latency": streaming_latency,
        "output_format": {
            "codec": "mp3",
            "sample_rate": 24000,
            "bit_rate": 128000,
        },
    }
    session = async_get_clientsession(hass)
    async with session.post(
        f"{API_BASE_URL}/tts",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=aiohttp.ClientTimeout(total=180),
    ) as resp:
        if resp.status >= 400:
            raise XAIOAuthError(
                f"xAI TTS failed ({resp.status}): {(await resp.text())[:500]}"
            )
        async for chunk in resp.content.iter_chunked(16 * 1024):
            if chunk:
                yield chunk
