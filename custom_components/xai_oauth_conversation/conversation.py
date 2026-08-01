"""Conversation entity for xAI OAuth."""
from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAX_OUTPUT_TOKENS, CONF_MODEL, CONF_PROMPT, DEFAULT_MAX_OUTPUT_TOKENS, DEFAULT_MODEL, DEFAULT_PROMPT, DOMAIN
from .xai_client import create_response, create_tool_response, text_part


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([XAIOAuthConversationEntity(config_entry)])


class XAIOAuthConversationEntity(conversation.ConversationEntity, conversation.AbstractConversationAgent):
    _attr_supports_streaming = False
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(self, user_input: conversation.ConversationInput, chat_log: conversation.ChatLog) -> conversation.ConversationResult:
        model = self.entry.data.get(CONF_MODEL, DEFAULT_MODEL)
        base_prompt = self.entry.data.get(CONF_PROMPT, DEFAULT_PROMPT)
        prompt = f"{base_prompt}\n\nCurrent backend model: {model}. If asked which model you use, answer with that exact model name."
        try:
            await chat_log.async_provide_llm_data(user_input.as_llm_context(DOMAIN), "assist", prompt, user_input.extra_system_prompt)
        except conversation.ConverseError as err:
            return err.as_conversation_result()
        instructions = chat_log.content[0].content if chat_log.content else prompt
        max_tokens = self.entry.data.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS)
        if chat_log.llm_api:
            result = await create_tool_response(self.hass, self.entry, model=model, instructions=instructions or prompt, user_text=user_input.text, llm_api=chat_log.llm_api, max_output_tokens=max_tokens)
        else:
            result = await create_response(self.hass, self.entry, model=model, instructions=instructions or prompt, content=[text_part(user_input.text)], max_output_tokens=max_tokens)
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(result.text)
        return conversation.ConversationResult(response=response, conversation_id=user_input.conversation_id)
