"""
vLLM inference client.
Calls the OpenAI-compatible /v1/chat/completions endpoint
with streaming enabled. Returns an async generator of SSE chunks.
"""

import json
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("zgx-bridge.inference")


@dataclass
class InferenceResult:
    """Accumulated result after streaming completes."""
    full_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int


class VLLMClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 120):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def health_check(self) -> dict:
        """Check if vLLM is reachable and serving."""
        try:
            # Try the models endpoint (OpenAI-compatible)
            resp = await self._client.get(
                f"{self._base_url}/models",
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return {"status": "ok", "models": models}
            return {"status": "error", "code": resp.status_code}
        except httpx.ConnectError:
            return {"status": "unreachable"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def stream_chat(
        self,
        messages: list[dict],
    ):
        """
        Stream a chat completion from vLLM.
        Yields dicts: {"type": "token", "content": "..."} or {"type": "done", ...}
        """
        start_time = time.time()
        full_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.7,
        }

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                timeout=httpx.Timeout(self._timeout),
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    logger.error("vLLM returned %d: %s", resp.status_code, body.decode())
                    yield {
                        "type": "error",
                        "message": f"Inference service returned status {resp.status_code}.",
                    }
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Extract token content
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content")

                    if content:
                        full_text += content
                        yield {"type": "token", "content": content}

                    # Some vLLM versions include usage in the final chunk
                    usage = chunk.get("usage")
                    if usage:
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)

        except httpx.ConnectError:
            logger.error("Cannot connect to vLLM at %s", self._base_url)
            yield {
                "type": "error",
                "message": "AI assistant is temporarily unavailable. Cannot reach inference service.",
            }
            return
        except httpx.ReadTimeout:
            logger.error("vLLM request timed out after %ds", self._timeout)
            yield {
                "type": "error",
                "message": "AI assistant timed out. Please try a shorter question.",
            }
            return
        except Exception as e:
            logger.error("Unexpected inference error: %s", e)
            yield {
                "type": "error",
                "message": "An unexpected error occurred. Please try again.",
            }
            return

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Estimate tokens if vLLM didn't report usage
        # (rough: 1 token per 4 chars)
        if completion_tokens == 0 and full_text:
            completion_tokens = max(1, len(full_text) // 4)

        yield {
            "type": "done",
            "full_text": full_text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "latency_ms": elapsed_ms,
        }

    async def close(self):
        await self._client.aclose()
