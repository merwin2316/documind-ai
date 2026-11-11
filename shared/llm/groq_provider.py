"""
Groq LLM provider — free cloud fallback.
Uses the Groq REST API (OpenAI-compatible).
Groq does NOT support embeddings — falls back to Ollama for those.
"""
import json
import logging
from typing import AsyncIterator, List, Dict
import httpx
from shared.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1"


class GroqProvider(BaseLLMProvider):
    """LLM provider using the Groq cloud API."""

    def __init__(
        self,
        api_key: str,
        chat_model: str = "llama-3.3-70b-versatile",
        ollama_base_url: str = "http://localhost:11434",
        ollama_embedding_model: str = "nomic-embed-text",
    ):
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for Groq provider")
        self.api_key = api_key
        self.chat_model = chat_model
        # Groq has no embedding API → delegate to Ollama
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_embedding_model = ollama_embedding_model
        self._embedding_dims: int | None = None

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Chat — non-streaming
    # ------------------------------------------------------------------
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
    ) -> str:
        payload: dict = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{GROQ_API_URL}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "Groq HTTP error: status_code=%s error_type=%s",
                e.response.status_code,
                type(e).__name__,
            )
            raise
        except Exception as e:
            logger.error("Groq generate error: %s", type(e).__name__)
            raise

    # ------------------------------------------------------------------
    # Chat — streaming
    # ------------------------------------------------------------------
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{GROQ_API_URL}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]  # Strip "data: "
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(
                "Groq streaming HTTP error: status_code=%s error_type=%s",
                e.response.status_code,
                type(e).__name__,
            )
            raise
        except Exception as e:
            logger.error("Groq streaming error: %s", type(e).__name__)
            raise

    # ------------------------------------------------------------------
    # Embeddings — delegated to Ollama (Groq has no embedding endpoint)
    # ------------------------------------------------------------------
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                for text in texts:
                    resp = await client.post(
                        f"{self.ollama_base_url}/api/embed",
                        json={"model": self.ollama_embedding_model, "input": text},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    emb = data.get("embeddings", [[]])[0]
                    embeddings.append(emb)
                    if self._embedding_dims is None and emb:
                        self._embedding_dims = len(emb)
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.ollama_base_url} for embeddings. "
                "Groq does not provide embeddings — Ollama is required. "
                f"Run: `ollama pull {self.ollama_embedding_model}`"
            )
        except Exception as e:
            logger.error("Groq embedding error: %s", type(e).__name__)
            raise
        return embeddings

    @property
    def embedding_dimensions(self) -> int:
        if self._embedding_dims:
            return self._embedding_dims
        defaults = {"nomic-embed-text": 768, "mxbai-embed-large": 1024}
        return defaults.get(self.ollama_embedding_model, 768)
