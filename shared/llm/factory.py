"""
LLM Provider Factory.
Returns the correct provider based on MODEL_PROVIDER environment variable.
"""
import logging
from shared.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_provider_instance: BaseLLMProvider | None = None


def get_llm_provider() -> BaseLLMProvider:
    """
    Get or create the configured LLM provider (singleton).

    Provider is selected by the MODEL_PROVIDER setting:
      - "ollama" (default) → local Ollama server
      - "groq"             → Groq cloud API

    If Groq is selected but GROQ_API_KEY is missing, falls back to Ollama.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    from config import settings

    provider_name = settings.MODEL_PROVIDER.lower()

    if provider_name == "groq":
        if not settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set — falling back to Ollama")
            provider_name = "ollama"
        else:
            from shared.llm.groq_provider import GroqProvider
            _provider_instance = GroqProvider(
                api_key=settings.GROQ_API_KEY,
                chat_model=settings.GROQ_MODEL,
                ollama_base_url=settings.OLLAMA_BASE_URL,
                ollama_embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
            )
            logger.info(f"LLM Provider: Groq ({settings.GROQ_MODEL})")
            return _provider_instance

    # Default: Ollama
    from shared.llm.ollama_provider import OllamaProvider
    _provider_instance = OllamaProvider(
        base_url=settings.OLLAMA_BASE_URL,
        chat_model=settings.OLLAMA_MODEL,
        embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
    )
    logger.info(
        f"LLM Provider: Ollama ({settings.OLLAMA_MODEL}) "
        f"at {settings.OLLAMA_BASE_URL}"
    )
    return _provider_instance
