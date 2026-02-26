# OpenAI model probe results

**Generated:** 2026-02-26T14:33:42.609304-05:00  

**Base URL:** `https://api.openai.com`  

**Auth mode:** `bearer`

## Summary

- Total models probed: **122**
- Supported (probe OK): **122**
- Failed: **0**

## Results by category

| Category | Total | OK | Fail |
|---|---:|---:|---:|
| audio_chat | 11 | 11 | 0 |
| computer_use | 2 | 2 | 0 |
| dalle | 2 | 2 | 0 |
| deep_research | 4 | 4 | 0 |
| embeddings | 3 | 3 | 0 |
| image | 4 | 4 | 0 |
| moderation | 2 | 2 | 0 |
| realtime | 11 | 11 | 0 |
| search | 6 | 6 | 0 |
| text | 62 | 62 | 0 |
| transcribe | 6 | 6 | 0 |
| tts | 7 | 7 | 0 |
| video | 2 | 2 | 0 |

## Failed models

_None._

## Notes

- This is a **smoke probe**, not a full capability test. It uses minimal payloads to confirm the model works on its likely endpoint.
- Video models (`sora-*`) are probed using a **validation-only** request (invalid `size`) to avoid expensive generation.
