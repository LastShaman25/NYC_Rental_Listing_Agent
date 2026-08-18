"""Local Qwen access for the post Studio (owner decision 2026-08-18).

Talks to any OpenAI-compatible LOCAL server (Ollama, LM Studio, llama.cpp
``--server``, vLLM). Configuration via environment variables:

- ``RENTAL_LOCAL_LLM_BASE_URL`` — default ``http://localhost:11434/v1`` (Ollama)
- ``RENTAL_LOCAL_LLM_MODEL``   — default ``qwen2.5``

The endpoint must be local (localhost/127.0.0.1): listing data never leaves
the machine for post generation. Posts are drafted from provided facts only —
the prompt forbids inventing amenities, prices, fees, or contact details, and
generated drafts are for human review before any use (no scores, 07).
"""

import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Defaults match scripts/start_local_llm.ps1, which serves the owner's
# Innerfy-packaged Qwen2.5-7B-Instruct GGUF via the MVP project's
# llama-cpp-python runtime (OpenAI-compatible llama_cpp.server).
DEFAULT_BASE_URL = "http://localhost:8601/v1"
DEFAULT_MODEL = "qwen2.5-7b-instruct"

# Owner-supplied system prompt (2026-08-18), verbatim, plus a bridging note:
# the local model cannot fetch links, so the listing facts arrive pre-fetched
# in the user message.
_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "xiaohongshu_post.txt").read_text(
    encoding="utf-8"
)


class LocalLlmUnavailable(RuntimeError):
    """The local model endpoint is not reachable or refused the request."""


def _endpoint() -> tuple[str, str]:
    base = os.environ.get("RENTAL_LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("RENTAL_LOCAL_LLM_MODEL", DEFAULT_MODEL)
    host = urlparse(base).hostname or ""
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise LocalLlmUnavailable(
            f"RENTAL_LOCAL_LLM_BASE_URL must point at this machine, got host {host!r} "
            "(listing data never leaves the device for post generation)."
        )
    return base, model


def generate_post(facts_block: str, extra_instructions: str = "") -> str:
    """Draft a marketing post from a listing facts block via the local model."""
    base, model = _endpoint()
    user_content = facts_block
    if extra_instructions.strip():
        user_content += (
            f"\n\nAdditional style instructions from the operator:\n{extra_instructions.strip()}"
        )
    try:
        response = httpx.post(
            f"{base}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                # Low temperature: a 7B model follows the no-fabrication rules
                # far better with less sampling freedom.
                "temperature": 0.4,
                "max_tokens": 600,
            },
            timeout=180.0,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"]).strip()
    except httpx.HTTPError as exc:
        raise LocalLlmUnavailable(
            f"Local model at {base} (model {model!r}) did not respond: {exc}. "
            "Start your local Qwen server (e.g. `ollama serve` + `ollama pull qwen2.5`), "
            "or set RENTAL_LOCAL_LLM_BASE_URL / RENTAL_LOCAL_LLM_MODEL."
        ) from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LocalLlmUnavailable(
            f"Local model at {base} returned an unexpected response shape: {exc}"
        ) from exc
