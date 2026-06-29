"""
Ollama LLM provider — local, free, default.
Connects to a running Ollama instance at http://localhost:11434.
"""
import json
import logging
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
                print("Calling Ollama...")
                logger.warning("=" * 80)
                logger.warning(f"URL: {self.base_url}/api/chat")
                logger.warning(f"MODEL: {self.chat_model}")
                logger.warning(f"JSON MODE: {json_mode}")
                logger.warning(messages)
                logger.warning("=" * 80)
                import time
                start = time.time()
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                print(f"Ollama took {time.time()-start:.2f} sec")
                print(f"Ollama took {time.time()-start:.2f} sec")
                logger.warning("OLLAMA RETURNED SUCCESS")
                data = resp.json()
                return data["message"]["content"]
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} — {e.response.text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Ollama generate error: {type(e).__name__}: {e}")
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
                print("Calling Ollama...")
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                for text in texts:
                    logger.warning(f"Ollama URL: {self.base_url}/api/chat")
                    logger.warning(f"Payload: {payload}")
                    resp = await client.post(
                        f"{self.base_url}/api/embed",
                        json={"model": self.embedding_model, "input": text},
                    )
                    resp.raise_for_status()
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
