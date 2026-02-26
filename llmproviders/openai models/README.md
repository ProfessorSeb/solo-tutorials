# OpenAI model support — docs index vs API key

**Generated:** 2026-02-26 02:41 PM EST  
**Docs index source:** https://developers.openai.com/api/docs/models  
**API inventory source:** `GET https://api.openai.com/v1/models`

## Support summary

| Category | Count |
|---|---:|
| Models on OpenAI docs index | 76 |
| Models returned by this API key (`/models`) | 122 |
| Docs-index models **supported** (present in `/models`) | 67 |
| Docs-index models **NOT supported** (missing from `/models`) | 9 |
| Extra models visible to the API key (not on docs index) | 55 |

### NOT supported (docs index models missing from `/models`)

```text
chatgpt-4o-latest
codex-mini-latest
gpt-4.5-preview
gpt-oss-120b
gpt-oss-20b
o1-mini
o1-preview
text-moderation-latest
text-moderation-stable
```

### Supported (docs index models present in `/models`)

```text
babbage-002
chatgpt-image-latest
computer-use-preview
dall-e-2
dall-e-3
davinci-002
gpt-3.5-turbo
gpt-4
gpt-4-turbo
gpt-4-turbo-preview
gpt-4.1
gpt-4.1-mini
gpt-4.1-nano
gpt-4o
gpt-4o-audio-preview
gpt-4o-mini
gpt-4o-mini-audio-preview
gpt-4o-mini-realtime-preview
gpt-4o-mini-search-preview
gpt-4o-mini-transcribe
gpt-4o-mini-tts
gpt-4o-realtime-preview
gpt-4o-search-preview
gpt-4o-transcribe
gpt-4o-transcribe-diarize
gpt-5
gpt-5-chat-latest
gpt-5-codex
gpt-5-mini
gpt-5-nano
gpt-5-pro
gpt-5.1
gpt-5.1-chat-latest
gpt-5.1-codex
gpt-5.1-codex-max
gpt-5.1-codex-mini
gpt-5.2
gpt-5.2-chat-latest
gpt-5.2-codex
gpt-5.2-pro
gpt-5.3-codex
gpt-audio
gpt-audio-1.5
gpt-audio-mini
gpt-image-1
gpt-image-1-mini
gpt-image-1.5
gpt-realtime
gpt-realtime-1.5
gpt-realtime-mini
o1
o1-pro
o3
o3-deep-research
o3-mini
o3-pro
o4-mini
o4-mini-deep-research
omni-moderation-latest
sora-2
sora-2-pro
text-embedding-3-large
text-embedding-3-small
text-embedding-ada-002
tts-1
tts-1-hd
whisper-1
```

## Runtime probe results (per-model)

We ran a minimal (low-cost) probe against every model returned by `GET /v1/models` for this API key.

| Mode | Total | OK | Fail | Output |
|---|---:|---:|---:|---|
| Direct OpenAI (`https://api.openai.com`) | 122 | 122 | 0 | [`probes/probe-direct.md`](probes/probe-direct.md) |
| Via agentgateway (standalone) | 122 | 122 | 0 | [`probes/probe-agentgateway.md`](probes/probe-agentgateway.md) |

Raw JSON:
- [`probes/probe-direct.json`](probes/probe-direct.json)
- [`probes/probe-agentgateway.json`](probes/probe-agentgateway.json)

Probe behavior (high level):
- Text models: `/v1/responses` → `/v1/chat/completions` → `/v1/completions`
- Deep research: `/v1/responses` with `tools: [{"type":"web_search_preview"}]` (counted OK if accepted, even if `status=incomplete`)
- Video (sora-*): `/v1/videos` with intentionally invalid `size` (validation-only; no paid generation)
- Realtime: `/v1/realtime/sessions` (client_secret redacted in JSON output)

Reproduce:
```bash
export OPENAI_API_KEY=...

# optional: run the proxy (edit port if needed)
agentgateway -f agentgateway-standalone.yaml

python3 probe_all_models.py --base-url https://api.openai.com --auth-mode bearer \
  --out-json probes/probe-direct.json --out-md probes/probe-direct.md

python3 probe_all_models.py --base-url http://localhost:18080 --auth-mode none \
  --out-json probes/probe-agentgateway.json --out-md probes/probe-agentgateway.md
```

agentgateway gotchas:
- Route matching is **suffix-based**; `"*"` is the catch-all and must be quoted in YAML.
- Keep `/v1/completions` as **passthrough** if you want legacy completion models to work.

## API model inventory (grouped)

These are *all* model IDs returned by `GET /v1/models` for this API key.

### Families (counts)

| Family | Count |
|---|---:|
| GPT-5.x | 25 |
| o-series (reasoning) | 16 |
| GPT-4o | 18 |
| GPT-4.1 | 6 |
| GPT-4 | 7 |
| GPT-3.5 | 6 |
| Embeddings | 3 |
| Moderation | 2 |
| Images | 6 |
| Audio / Realtime | 27 |
| Computer Use | 2 |
| Legacy | 2 |
| Other | 2 |

### Full list (grouped)

#### GPT-5.x (25)

```text
gpt-5
gpt-5-2025-08-07
gpt-5-chat-latest
gpt-5-codex
gpt-5-mini
gpt-5-mini-2025-08-07
gpt-5-nano
gpt-5-nano-2025-08-07
gpt-5-pro
gpt-5-pro-2025-10-06
gpt-5-search-api
gpt-5-search-api-2025-10-14
gpt-5.1
gpt-5.1-2025-11-13
gpt-5.1-chat-latest
gpt-5.1-codex
gpt-5.1-codex-max
gpt-5.1-codex-mini
gpt-5.2
gpt-5.2-2025-12-11
gpt-5.2-chat-latest
gpt-5.2-codex
gpt-5.2-pro
gpt-5.2-pro-2025-12-11
gpt-5.3-codex
```

#### o-series (reasoning) (16)

```text
o1
o1-2024-12-17
o1-pro
o1-pro-2025-03-19
o3
o3-2025-04-16
o3-deep-research
o3-deep-research-2025-06-26
o3-mini
o3-mini-2025-01-31
o3-pro
o3-pro-2025-06-10
o4-mini
o4-mini-2025-04-16
o4-mini-deep-research
o4-mini-deep-research-2025-06-26
```

#### GPT-4o (18)

```text
gpt-4o
gpt-4o-2024-05-13
gpt-4o-2024-08-06
gpt-4o-2024-11-20
gpt-4o-mini
gpt-4o-mini-2024-07-18
gpt-4o-mini-search-preview
gpt-4o-mini-search-preview-2025-03-11
gpt-4o-mini-transcribe
gpt-4o-mini-transcribe-2025-03-20
gpt-4o-mini-transcribe-2025-12-15
gpt-4o-mini-tts
gpt-4o-mini-tts-2025-03-20
gpt-4o-mini-tts-2025-12-15
gpt-4o-search-preview
gpt-4o-search-preview-2025-03-11
gpt-4o-transcribe
gpt-4o-transcribe-diarize
```

#### GPT-4.1 (6)

```text
gpt-4.1
gpt-4.1-2025-04-14
gpt-4.1-mini
gpt-4.1-mini-2025-04-14
gpt-4.1-nano
gpt-4.1-nano-2025-04-14
```

#### GPT-4 (7)

```text
gpt-4
gpt-4-0125-preview
gpt-4-0613
gpt-4-1106-preview
gpt-4-turbo
gpt-4-turbo-2024-04-09
gpt-4-turbo-preview
```

#### GPT-3.5 (6)

```text
gpt-3.5-turbo
gpt-3.5-turbo-0125
gpt-3.5-turbo-1106
gpt-3.5-turbo-16k
gpt-3.5-turbo-instruct
gpt-3.5-turbo-instruct-0914
```

#### Embeddings (3)

```text
text-embedding-3-large
text-embedding-3-small
text-embedding-ada-002
```

#### Moderation (2)

```text
omni-moderation-2024-09-26
omni-moderation-latest
```

#### Images (6)

```text
chatgpt-image-latest
dall-e-2
dall-e-3
gpt-image-1
gpt-image-1-mini
gpt-image-1.5
```

#### Audio / Realtime (27)

```text
gpt-4o-audio-preview
gpt-4o-audio-preview-2024-12-17
gpt-4o-audio-preview-2025-06-03
gpt-4o-mini-audio-preview
gpt-4o-mini-audio-preview-2024-12-17
gpt-4o-mini-realtime-preview
gpt-4o-mini-realtime-preview-2024-12-17
gpt-4o-realtime-preview
gpt-4o-realtime-preview-2024-12-17
gpt-4o-realtime-preview-2025-06-03
gpt-audio
gpt-audio-1.5
gpt-audio-2025-08-28
gpt-audio-mini
gpt-audio-mini-2025-10-06
gpt-audio-mini-2025-12-15
gpt-realtime
gpt-realtime-1.5
gpt-realtime-2025-08-28
gpt-realtime-mini
gpt-realtime-mini-2025-10-06
gpt-realtime-mini-2025-12-15
tts-1
tts-1-1106
tts-1-hd
tts-1-hd-1106
whisper-1
```

#### Computer Use (2)

```text
computer-use-preview
computer-use-preview-2025-03-11
```

#### Legacy (2)

```text
babbage-002
davinci-002
```

#### Other (2)

```text
sora-2
sora-2-pro
```

## OpenClaw note (model allowlist)

If your `openclaw.json` sets `agents.defaults.models`, that becomes a **model allowlist**.
To use additional OpenAI models in OpenClaw, either:
- add them under `agents.defaults.models`, or
- remove/empty the allowlist so `/model` can pick anything.

Example (add a few common ones):

```json
{
  "agents": {
    "defaults": {
      "models": {
        "openai/gpt-5.2": {
          "alias": "gpt-5.2"
        },
        "openai/gpt-4o-mini": {
          "alias": "4o-mini"
        },
        "openai/o3-mini": {
          "alias": "o3-mini"
        }
      }
    }
  }
}
```
