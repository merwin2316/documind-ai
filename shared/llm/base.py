"""
Abstract base class for LLM providers.
All providers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, List, Dict


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            json_mode: If True, instruct the model to return valid JSON.

        Returns:
            Generated text string.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> AsyncIterator[str]:
        """
        Stream a response token-by-token.

        Yields:
            Text chunks as they are generated.
        """
        ...

    @abstractmethod
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create vector embeddings for a list of texts.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors.
        """
        ...

    @property
    @abstractmethod
    def embedding_dimensions(self) -> int:
        """Return the dimensionality of the embedding model."""
        ...
