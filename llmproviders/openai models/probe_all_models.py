#!/usr/bin/env python3
"""Probe OpenAI model IDs returned by GET /v1/models.

Runs a minimal, low-cost call per model *type* and records whether it worked.

Supports probing either:
- OpenAI directly (default), or
- via a local agentgateway instance (e.g. http://localhost:3000)

Usage examples:
  # direct
  OPENAI_API_KEY=... \
    python3 probe_all_models.py --base-url https://api.openai.com --auth-mode bearer \
      --out-json probe-direct.json --out-md probe-direct.md

  # agentgateway (backendAuth injects upstream key, so no client auth)
  OPENAI_API_KEY=... \
    python3 probe_all_models.py --base-url http://localhost:3000 --auth-mode none \
      --out-json probe-agentgateway.json --out-md probe-agentgateway.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests


def now_iso(tz: str = "America/Toronto") -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz)).isoformat()
    except Exception:
        return datetime.now().isoformat()


def err_summary(j: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(j, dict):
        return None
    err = j.get("error")
    if not isinstance(err, dict):
        return None
    msg = err.get("message")
    if isinstance(msg, str) and len(msg) > 240:
        msg = msg[:237] + "..."
    return {
        "type": err.get("type"),
        "code": err.get("code"),
        "param": err.get("param"),
        "message": msg,
    }


def category_for(mid: str) -> str:
    m = mid.lower()

    if m.startswith("sora-"):
        return "video"
    if "realtime" in m:
        return "realtime"
    if "computer-use" in m:
        return "computer_use"
    if "moderation" in m:
        return "moderation"
    if "embedding" in m:
        return "embeddings"

    # audio: distinguish chat-audio vs tts vs transcribe
    if "transcribe" in m or m == "whisper-1":
        return "transcribe"
    if m.startswith("tts-") or "-tts" in m:
        return "tts"
    if "audio-preview" in m or m.startswith("gpt-audio"):
        return "audio_chat"

    # Deep research models (these are NOT the same as search-preview/search-api models)
    if "deep-research" in m:
        return "deep_research"

    # Search models
    if "search-api" in m or "search-preview" in m:
        return "search"
    if "search" in m:
        return "search"

    if m in {"dall-e-2", "dall-e-3"}:
        return "dalle"
    if "image" in m:
        return "image"

    return "text"


@dataclass
class Client:
    base_url: str
    api_key: Optional[str]
    auth_mode: str  # bearer|none

    def headers_json(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.auth_mode == "bearer":
            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is required for auth-mode=bearer")
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def headers_multipart(self) -> Dict[str, str]:
        # requests sets multipart boundary
        h = {}
        if self.auth_mode == "bearer":
            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is required for auth-mode=bearer")
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path


def get_models(client: Client) -> Tuple[int, Any]:
    r = requests.get(client.url("/v1/models"), headers=client.headers_json(), timeout=60)
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text[:500]}
    return r.status_code, j


def post_json(client: Client, path: str, payload: Dict[str, Any], timeout: int = 60) -> Tuple[int, Any, Dict[str, str]]:
    r = requests.post(client.url(path), headers=client.headers_json(), json=payload, timeout=timeout)
    hdrs = {k.lower(): v for k, v in r.headers.items()}
    # Some endpoints return binary on success; call-site should handle
    ct = hdrs.get("content-type", "")
    if ct.startswith("audio/"):
        return r.status_code, {"_binary": True}, hdrs
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text[:800]}
    return r.status_code, j, hdrs


def post_multipart(client: Client, path: str, fields: Dict[str, str], files: Optional[Dict[str, Any]] = None, timeout: int = 120) -> Tuple[int, Any, Dict[str, str]]:
    r = requests.post(
        client.url(path),
        headers=client.headers_multipart(),
        data=fields,
        files=files,
        timeout=timeout,
    )
    hdrs = {k.lower(): v for k, v in r.headers.items()}
    try:
        j = r.json()
    except Exception:
        j = {"_raw": r.text[:800]}
    return r.status_code, j, hdrs


def probe_text_like(client: Client, mid: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Try Responses → Chat Completions → Completions
    payload = {
        "model": mid,
        "input": "Reply with exactly: OK",
        "max_output_tokens": 16,
    }
    if extra:
        payload.update(extra)

    st, j, _ = post_json(client, "/v1/responses", payload, timeout=90)
    if st == 200 and not j.get("error"):
        return {"ok": True, "endpoint": "/v1/responses", "http": st, "error": None}

    es = err_summary(j)

    # Retry once on server_error
    if es and es.get("type") == "server_error":
        time.sleep(0.5)
        st2, j2, _ = post_json(client, "/v1/responses", payload, timeout=90)
        if st2 == 200 and not j2.get("error"):
            return {"ok": True, "endpoint": "/v1/responses", "http": st2, "error": None}
        st, j, es = st2, j2, err_summary(j2)

    # Chat completions
    st3, j3, _ = post_json(
        client,
        "/v1/chat/completions",
        {
            "model": mid,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 16,
        },
        timeout=90,
    )
    if st3 == 200 and not j3.get("error"):
        return {"ok": True, "endpoint": "/v1/chat/completions", "http": st3, "error": None}

    # Completions
    st4, j4, _ = post_json(
        client,
        "/v1/completions",
        {
            "model": mid,
            "prompt": "Reply with exactly: OK",
            "max_tokens": 16,
        },
        timeout=90,
    )
    if st4 == 200 and not j4.get("error"):
        return {"ok": True, "endpoint": "/v1/completions", "http": st4, "error": None}

    return {"ok": False, "endpoint": "/v1/responses|/v1/chat/completions|/v1/completions", "http": st, "error": es or err_summary(j3) or err_summary(j4) or {"message": "unknown"}}


def probe_one(client: Client, mid: str, wav_path: str) -> Dict[str, Any]:
    cat = category_for(mid)

    # video: do a validation-only probe to avoid expensive generation
    if cat == "video":
        # Use JSON to avoid multipart boundary issues; we deliberately send an invalid size.
        st, j, _ = post_json(
            client,
            "/v1/videos",
            {"model": mid, "prompt": "test", "size": "bad"},
            timeout=120,
        )
        es = err_summary(j)
        # Consider "ok" if we hit the endpoint and the error is about size
        ok = (st == 400 and isinstance(es, dict) and es.get("param") == "size") or (st == 200 and not j.get("error"))
        note = "validation-only (invalid size)" if st == 400 and ok else None
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/videos", "http": st, "error": None if ok else es, "note": note}

    if cat == "realtime":
        st, j, _ = post_json(client, "/v1/realtime/sessions", {"model": mid}, timeout=60)
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        # redact
        if isinstance(j, dict) and "client_secret" in j:
            j = {"_redacted": True, "id": j.get("id"), "expires_at": j.get("expires_at")}
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/realtime/sessions", "http": st, "error": None if ok else es}

    if cat == "embeddings":
        st, j, _ = post_json(client, "/v1/embeddings", {"model": mid, "input": "ping"}, timeout=60)
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/embeddings", "http": st, "error": None if ok else es}

    if cat == "moderation":
        st, j, _ = post_json(client, "/v1/moderations", {"model": mid, "input": "ping"}, timeout=60)
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/moderations", "http": st, "error": None if ok else es}

    if cat in {"image", "dalle"}:
        size = "auto"
        if mid == "dall-e-2":
            size = "256x256"
        elif mid == "dall-e-3":
            size = "1024x1024"
        st, j, _ = post_json(
            client,
            "/v1/images/generations",
            {"model": mid, "prompt": "A tiny red dot", "size": size, "n": 1},
            timeout=120,
        )
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        # drop base64/url
        if ok and isinstance(j, dict):
            j = {"dataCount": len(j.get("data") or [])}
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/images/generations", "http": st, "error": None if ok else es}

    if cat == "tts":
        st, j, hdrs = post_json(
            client,
            "/v1/audio/speech",
            {"model": mid, "input": "ping", "voice": "alloy"},
            timeout=120,
        )
        ok = st == 200 and hdrs.get("content-type", "").startswith("audio/")
        # on failure, best-effort parse
        err = None
        if not ok:
            err = err_summary(j) or {"message": f"http {st}", "content_type": hdrs.get("content-type")}
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/audio/speech", "http": st, "error": err}

    if cat == "transcribe":
        with open(wav_path, "rb") as f:
            st, j, _ = post_multipart(
                client,
                "/v1/audio/transcriptions",
                {"model": mid},
                files={"file": ("probe.wav", f, "audio/wav")},
                timeout=120,
            )
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/audio/transcriptions", "http": st, "error": None if ok else es}

    if cat == "audio_chat":
        st, j, _ = post_json(
            client,
            "/v1/chat/completions",
            {
                "model": mid,
                "modalities": ["text", "audio"],
                "audio": {"voice": "alloy", "format": "wav"},
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 16,
            },
            timeout=120,
        )
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/chat/completions", "http": st, "error": None if ok else es}

    if cat == "computer_use":
        # computer-use models want truncation=auto
        r = probe_text_like(client, mid, extra={"truncation": "auto"})
        return {"model": mid, "category": cat, "ok": r["ok"], "skipped": False, "endpoint": r["endpoint"], "http": r["http"], "error": r["error"]}

    if cat == "deep_research":
        # Deep research models require at least one of: web_search_preview, mcp, file_search.
        # We include web_search_preview to satisfy the requirement without wiring an MCP server.
        r = probe_text_like(client, mid, extra={"tools": [{"type": "web_search_preview"}]})
        return {"model": mid, "category": cat, "ok": r["ok"], "skipped": False, "endpoint": r["endpoint"], "http": r["http"], "error": r["error"]}

    if cat == "search":
        st, j, _ = post_json(
            client,
            "/v1/chat/completions",
            {
                "model": mid,
                "messages": [{"role": "user", "content": "What is 1+1? Reply with OK."}],
                "max_tokens": 32,
            },
            timeout=120,
        )
        es = err_summary(j)
        ok = st == 200 and not j.get("error")
        return {"model": mid, "category": cat, "ok": ok, "skipped": False, "endpoint": "/v1/chat/completions", "http": st, "error": None if ok else es}

    # default text
    r = probe_text_like(client, mid)
    return {"model": mid, "category": cat, "ok": r["ok"], "skipped": False, "endpoint": r["endpoint"], "http": r["http"], "error": r["error"]}


def write_md(path: str, report: Dict[str, Any]) -> None:
    results = report["results"]

    total = len(results)
    ok = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))
    fail = total - ok - skipped

    by_cat: Dict[str, Dict[str, int]] = {}
    for r in results:
        cat = r.get("category") or "unknown"
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "ok": 0, "fail": 0}
        by_cat[cat]["total"] += 1
        if r.get("ok"):
            by_cat[cat]["ok"] += 1
        elif r.get("skipped"):
            # ignore for fail counts here
            pass
        else:
            by_cat[cat]["fail"] += 1

    lines = []
    lines.append("# OpenAI model probe results\n")
    lines.append(f"**Generated:** {report['meta']['generatedAt']}  \n")
    lines.append(f"**Base URL:** `{report['meta']['baseUrl']}`  \n")
    lines.append(f"**Auth mode:** `{report['meta']['authMode']}`\n")

    lines.append("## Summary\n")
    lines.append(f"- Total models probed: **{total}**")
    lines.append(f"- Supported (probe OK): **{ok}**")
    lines.append(f"- Failed: **{fail}**")
    if skipped:
        lines.append(f"- Skipped: **{skipped}**")
    lines.append("")

    lines.append("## Results by category\n")
    lines.append("| Category | Total | OK | Fail |")
    lines.append("|---|---:|---:|---:|")
    for cat in sorted(by_cat.keys()):
        c = by_cat[cat]
        lines.append(f"| {cat} | {c['total']} | {c['ok']} | {c['fail']} |")
    lines.append("")

    fails = [r for r in results if (not r.get("ok") and not r.get("skipped"))]
    lines.append("## Failed models\n")
    if not fails:
        lines.append("_None._\n")
    else:
        lines.append("| Model | Category | Endpoint | HTTP | Error |")
        lines.append("|---|---|---|---:|---|")
        for r in sorted(fails, key=lambda x: (x.get("category", ""), x.get("model", ""))):
            err = r.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            msg = (msg or "").replace("|", "\\|")
            lines.append(f"| `{r.get('model')}` | {r.get('category')} | `{r.get('endpoint')}` | {r.get('http')} | {msg} |")
        lines.append("")

    lines.append("## Notes\n")
    lines.append("- This is a **smoke probe**, not a full capability test. It uses minimal payloads to confirm the model works on its likely endpoint.")
    lines.append("- Video models (`sora-*`) are probed using a **validation-only** request (invalid `size`) to avoid expensive generation.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://api.openai.com", help="Base URL (OpenAI or agentgateway)")
    ap.add_argument("--auth-mode", choices=["bearer", "none"], default="bearer", help="Send Authorization header or not")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--sleep-ms", type=int, default=50, help="Delay between requests (ms)")
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    client = Client(base_url=args.base_url, api_key=api_key, auth_mode=args.auth_mode)

    # Ensure we have a probe wav file
    wav_path = os.environ.get("OPENAI_PROBE_WAV", "/tmp/openai-probe.wav")
    if not os.path.exists(wav_path):
        sys.stderr.write(f"Missing probe wav file: {wav_path}\n")
        return 2

    st, models_resp = get_models(client)
    if st != 200:
        sys.stderr.write(f"GET /v1/models failed: HTTP {st} {models_resp}\n")
        return 3

    models = models_resp.get("data", []) if isinstance(models_resp, dict) else []
    model_ids = sorted({m.get("id").strip().lower() for m in models if isinstance(m, dict) and m.get("id")})

    results = []
    started = time.time()

    for i, mid in enumerate(model_ids, 1):
        t0 = time.time()
        try:
            r = probe_one(client, mid, wav_path)
            r["durationMs"] = int((time.time() - t0) * 1000)
        except Exception as e:
            r = {
                "model": mid,
                "category": category_for(mid),
                "ok": False,
                "skipped": False,
                "endpoint": None,
                "http": None,
                "error": {"message": f"exception: {type(e).__name__}: {e}"},
                "durationMs": int((time.time() - t0) * 1000),
            }
        results.append(r)

        if i % 10 == 0:
            ok = sum(1 for x in results if x.get("ok"))
            sys.stderr.write(f"{i}/{len(model_ids)} ok={ok}\n")

        time.sleep(max(0, args.sleep_ms) / 1000.0)

    meta = {
        "generatedAt": now_iso(),
        "baseUrl": args.base_url,
        "authMode": args.auth_mode,
        "totalModels": len(model_ids),
        "durationSeconds": round(time.time() - started, 1),
    }

    report = {"meta": meta, "results": results}

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    write_md(args.out_md, report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
