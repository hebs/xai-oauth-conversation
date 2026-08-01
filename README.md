# xAI OAuth Conversation for Home Assistant

Unofficial Home Assistant custom integration for using Grok through xAI OAuth. It adds a Grok conversation agent to Home Assistant Assist without requiring an xAI API key.

## Features

- Grok conversation agent for Home Assistant Assist
- Home Assistant LLM tool support for device queries and control
- xAI device-code sign-in, with no localhost callback
- Automatic OAuth token refresh
- `generate_content` service for text generation
- `analyze_image` service for camera entities, image entities, local files, and URLs
- Configurable model, system prompt, and maximum output tokens

## Requirements and warnings

- Home Assistant 2026.4 or newer is recommended.
- An xAI account with OAuth access to the selected Grok model is required.
- This project is unofficial, experimental, and is not affiliated with xAI or Home Assistant.
- xAI may change its OAuth scopes, endpoints, model access, or API behavior at any time.
- OAuth access may be subject to xAI account limits, subscriptions, and terms. This integration does not bypass them.

## Installation with HACS

1. Open HACS.
2. Add `https://github.com/hebs/xai-oauth-conversation` as a custom repository of type **Integration**.
3. Install **xAI OAuth Conversation**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for **xAI OAuth Conversation**.
6. Choose a model, follow the xAI device sign-in link, approve access, then return to Home Assistant and confirm authorization.

xAI may identify the OAuth application as **Grok Build** during consent.

## Manual installation

Copy `custom_components/xai_oauth_conversation` into `/config/custom_components/xai_oauth_conversation`, then restart Home Assistant.

## Configuration

- **Model:** The exact xAI model ID. The default is `grok-4.20-0309-reasoning`. You may enter `grok-4.5` if it is available to your account.
- **System prompt:** Instructions applied to conversation and service requests.
- **Max output tokens:** A response ceiling. `2000` is a good general-purpose starting point; use `1000` for shorter voice replies or `4000` for longer reasoning tasks.

The setup flow tests the configured model. If the account does not have access, setup ends with a connection error.

## Services

### `xai_oauth_conversation.generate_content`

```yaml
action: xai_oauth_conversation.generate_content
data:
  config_entry: YOUR_CONFIG_ENTRY_ID
  prompt: Summarize today's weather in one sentence.
  max_output_tokens: 1000
response_variable: grok_response
```

### `xai_oauth_conversation.analyze_image`

At least one `entity_id`, `image_file`, or `image_url` is required.

```yaml
action: xai_oauth_conversation.analyze_image
data:
  config_entry: YOUR_CONFIG_ENTRY_ID
  prompt: Briefly describe what is visible.
  entity_id:
    - camera.front_door
response_variable: grok_vision
```

Local files can use an absolute path such as `/config/www/snapshot.jpg`, or a path relative to the Home Assistant config directory.

## Security

OAuth access and refresh tokens are stored in the Home Assistant config entry. Protect Home Assistant backups and `.storage` files. Never publish copied config entries, logs containing tokens, or long-lived Home Assistant access tokens.

Remote image URLs are fetched by xAI. Camera, image-entity, and local-file images are encoded and sent to xAI for analysis.

## Removal

Remove the integration from **Settings → Devices & services**, then uninstall it from HACS (or delete its custom component directory) and restart Home Assistant.

## License

MIT
