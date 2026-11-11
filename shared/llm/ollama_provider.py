"""
Ollama LLM provider — local, free, default.
Connects to a running Ollama instance at http://localhost:11434.
"""
import json
import logging
import time
from typing import AsyncIterator, List, Dict
import httpx
from shared.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """LLM provider using a local Ollama server."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        chat_model: str = "llama3",
        embedding_model: str = "nomic-embed-text",
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self._embedding_dims: int | None = None

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
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                start = time.time()
                logger.info(
                    "LLM HTTP START OllamaProvider.generate url=%s model=%s json_mode=%s max_tokens=%s messages=%s",
                    f"{self.base_url}/api/chat",
                    self.chat_model,
                    json_mode,
                    max_tokens,
                    len(messages),
                )
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                logger.info(
                    "LLM HTTP END OllamaProvider.generate elapsed=%.2fs status=%s bytes=%s",
                    time.time() - start,
                    resp.status_code,
                    len(resp.content),
                )
                data = resp.json()
                return data["message"]["content"]
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama HTTP error: status_code=%s error_type=%s",
                e.response.status_code,
                type(e).__name__,
            )
            raise
        except Exception as e:
            logger.exception("Ollama generate error: %s", type(e).__name__)
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
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }   

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                start = time.perf_counter()
                line_count = 0
                logger.info(
                    "LLM HTTP START OllamaProvider.generate_stream url=%s model=%s max_tokens=%s messages=%s",
                    f"{self.base_url}/api/chat",
                    self.chat_model,
                    max_tokens,
                    len(messages),
                )
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        line_count += 1
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                logger.info(
                    "LLM HTTP END OllamaProvider.generate_stream elapsed=%.2fs status=%s lines=%s",
                    time.perf_counter() - start,
                    resp.status_code,
                    line_count,
                )
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama streaming HTTP error: status_code=%s error_type=%s",
                e.response.status_code,
                type(e).__name__,
            )
            raise
        except Exception as e:
            logger.exception("Ollama generate_stream error: %s", type(e).__name__)
            raise

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                for index, text in enumerate(texts):
                    start = time.perf_counter()
                    logger.info(
                        "LLM HTTP START OllamaProvider.create_embeddings index=%s/%s url=%s model=%s text_len=%s",
                        index + 1,
                        len(texts),
                        f"{self.base_url}/api/embed",
                        self.embedding_model,
                        len(text),
                    )
                    resp = await client.post(
                        f"{self.base_url}/api/embed",
                        json={"model": self.embedding_model, "input": text},
                    )
                    resp.raise_for_status()
                    logger.info(
                        "LLM HTTP END OllamaProvider.create_embeddings index=%s/%s elapsed=%.2fs status=%s bytes=%s",
                        index + 1,
                        len(texts),
                        time.perf_counter() - start,
                        resp.status_code,
                        len(resp.content),
                    )
                    data = resp.json()
                    emb = data.get("embeddings", [[]])[0]
                    embeddings.append(emb)

                    # Cache dimensions from first result
                    if self._embedding_dims is None and emb:
                        self._embedding_dims = len(emb)
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running and the embedding model is pulled: "
                f"`ollama pull {self.embedding_model}`"
            )
        except Exception as e:
            logger.exception("Ollama create_embeddings error: %s", type(e).__name__)
            raise
        return embeddings

    @property
    def embedding_dimensions(self) -> int:
        """nomic-embed-text = 768, mxbai-embed-large = 1024."""
        if self._embedding_dims:
            return self._embedding_dims
        # Defaults per known model
        defaults = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
        }
        return defaults.get(self.embedding_model, 768)
