import os
from functools import lru_cache

from .base import ExtractionFailed, ExtractorNotConfigured, ReactionExtractor, RequestDeclined


@lru_cache(maxsize=1)
def get_extractor() -> ReactionExtractor:
    """Factory selected by env EXTRACTOR (default 'gemini').

    To add a provider: implement ReactionExtractor and register it here.
    """
    name = os.getenv("EXTRACTOR", "gemini").strip().lower()
    if name == "gemini":
        from .gemini import GeminiExtractor

        return GeminiExtractor()
    raise ExtractorNotConfigured(f"Unknown EXTRACTOR '{name}'.")


__all__ = ["get_extractor", "RequestDeclined", "ReactionExtractor", "ExtractionFailed", "ExtractorNotConfigured"]
