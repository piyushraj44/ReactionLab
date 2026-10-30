from abc import ABC, abstractmethod

from app.schemas import ReactionRecord


class ExtractorNotConfigured(Exception):
    """Provider credentials/config missing (HTTP 503)."""


class ExtractionFailed(Exception):
    """Provider call failed or returned unusable output (HTTP 502)."""


class RequestDeclined(Exception):
    """The model declined the request for safety reasons (HTTP 422)."""


class ReactionExtractor(ABC):
    @abstractmethod
    async def extract(self, image_bytes: bytes, mime_type: str) -> ReactionRecord:
        ...

    @abstractmethod
    async def predict(self, reactants: str, conditions: str) -> ReactionRecord:
        ...
