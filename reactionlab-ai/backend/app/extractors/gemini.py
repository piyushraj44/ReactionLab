import logging
import os
from typing import Callable, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.schemas import Field, LabeledField, ReactionRecord

from .base import ExtractionFailed, ExtractorNotConfigured, ReactionExtractor, RequestDeclined
from .prompt import EXTRACTION_PROMPT, PREDICTION_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_MS = 60_000
DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash"
BUSY_MESSAGE = "The AI model is busy right now. Please try again in a minute."
NOT_PROVIDED = "Not provided"
NOT_CLEAR = "Not clearly identified"
SENTINELS = {NOT_PROVIDED, NOT_CLEAR}

T = TypeVar("T", bound=BaseModel)


class SourcedValue(BaseModel):
    value: str
    source: str  # "page" | "ai" (enforced in code)


class DetailedExtraction(BaseModel):
    """Notebook-mode schema the model fills (internal; mapped to ReactionRecord)."""

    reactants: list[str]
    equation: SourcedValue
    main_product: SourcedValue
    by_products: SourcedValue
    possible_side_products: SourcedValue
    confirmatory_test: SourcedValue
    reagents_catalysts: str
    solvent: str
    temperature: str
    time: str
    atmosphere: str
    other_conditions: str
    procedure: str
    yield_result: str
    observations: str


class PredictionResult(BaseModel):
    """Prediction-mode schema the model fills (internal)."""

    declined: bool
    decline_reason: str
    equation: str
    reactants: list[str]
    main_product: str
    by_products: str
    possible_side_products: str
    confirmatory_test: str
    reagents_catalysts: str
    solvent: str
    temperature: str
    time: str
    atmosphere: str
    other_conditions: str
    procedure: str
    yield_result: str
    observations: str


def _clean(value: str | None) -> str:
    """Turn literal backslash-n sequences into real newlines, then strip."""
    text = (value or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    return text.strip()


def _norm(value: str | None) -> str:
    return _clean(value) or NOT_PROVIDED


def _sourced(sv: SourcedValue) -> Field:
    """Model-supplied provenance; sentinels are always 'page' in notebook mode."""
    value = _norm(sv.value)
    source = "ai" if (sv.source or "").strip().lower() == "ai" and value not in SENTINELS else "page"
    return Field(value=value, source=source)


def _build(
    mode: str,
    source_for_copy: str,
    equation: Field,
    reactants: list[str],
    products: list[tuple[str, Field]],
    d,
) -> ReactionRecord:
    src = source_for_copy

    def lf(label: str, value: str) -> LabeledField:
        return LabeledField(label=label, value=_norm(value), source=src)

    return ReactionRecord(
        mode=mode,
        equation=equation,
        reactants=[
            Field(value=r, source=src)
            for r in ([c for c in (_clean(x) for x in reactants) if c] or [NOT_PROVIDED])
        ],
        products=[LabeledField(label=l, value=f.value, source=f.source) for l, f in products],
        conditions=[
            lf("Reagents / catalysts", d.reagents_catalysts),
            lf("Solvent", d.solvent),
            lf("Temperature", d.temperature),
            lf("Time", d.time),
            lf("Atmosphere", d.atmosphere),
            lf("Other", d.other_conditions),
        ],
        procedure=Field(value=_norm(d.procedure), source=src),
        outcome=[lf("Yield / result", d.yield_result), lf("Observations", d.observations)],
    )


def to_record(d: DetailedExtraction) -> ReactionRecord:
    """Notebook mode: copy-only fields are forced to source 'page'."""
    return _build(
        "notebook",
        "page",
        _sourced(d.equation),
        d.reactants,
        [
            ("Main product", _sourced(d.main_product)),
            ("By-products", _sourced(d.by_products)),
            ("Possible side products", _sourced(d.possible_side_products)),
            ("Confirmatory test", _sourced(d.confirmatory_test)),
        ],
        d,
    )


def to_prediction_record(p: PredictionResult) -> ReactionRecord:
    """Prediction mode: every field is forced to source 'ai'."""

    def ai(v: str) -> Field:
        return Field(value=_norm(v), source="ai")

    if p.declined:
        raise RequestDeclined(_clean(p.decline_reason) or "This request is not supported.")
    return _build(
        "prediction",
        "ai",
        ai(p.equation),
        p.reactants,
        [
            ("Main product", ai(p.main_product)),
            ("By-products", ai(p.by_products)),
            ("Possible side products", ai(p.possible_side_products)),
            ("Confirmatory test", ai(p.confirmatory_test)),
        ],
        p,
    )


def is_overloaded(exc: Exception) -> bool:
    """True for overload / rate-limit errors (HTTP 503 / 429)."""
    if not isinstance(exc, genai_errors.APIError):
        return False
    status = str(getattr(exc, "status", "") or "").upper()
    return exc.code in (503, 429) or status in ("UNAVAILABLE", "RESOURCE_EXHAUSTED")


class GeminiExtractor(ReactionExtractor):
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise ExtractorNotConfigured("GEMINI_API_KEY is not configured on the server.")
        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS)
            )
        return self._client

    async def _generate(
        self,
        client: genai.Client,
        model: str,
        contents: list,
        schema: type[T],
        mapper: Callable[[T], ReactionRecord],
    ) -> ReactionRecord:
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        parsed = response.parsed
        if not isinstance(parsed, schema):
            if not response.text:
                raise ValueError("Empty model response")
            parsed = schema.model_validate_json(response.text)
        return mapper(parsed)

    async def _run(
        self, contents: list, schema: type[T], mapper: Callable[[T], ReactionRecord]
    ) -> ReactionRecord:
        """Primary model, one retry on the fallback model if overloaded; error mapping."""
        client = self._get_client()
        try:
            try:
                record = await self._generate(client, self.model, contents, schema, mapper)
                logger.info("Request served by model %s", self.model)
                return record
            except Exception as exc:
                if not (is_overloaded(exc) and self.fallback_model):
                    raise
                logger.warning(
                    "Model %s overloaded (%s); retrying on %s", self.model, exc, self.fallback_model
                )
            try:
                record = await self._generate(
                    client, self.fallback_model, contents, schema, mapper
                )
            except Exception as exc:
                if is_overloaded(exc):
                    logger.error("Fallback model %s also overloaded: %s", self.fallback_model, exc)
                    raise ExtractionFailed(BUSY_MESSAGE) from exc
                raise
            logger.info("Request served by fallback model %s", self.fallback_model)
            return record
        except (ExtractionFailed, ExtractorNotConfigured, RequestDeclined):
            raise
        except (ValidationError, ValueError) as exc:
            logger.exception("Unparseable model output")
            raise ExtractionFailed("The model returned output that could not be parsed.") from exc
        except Exception as exc:  # SDK / network errors
            logger.exception("Gemini call failed")
            raise ExtractionFailed("The vision model call failed. Please try again.") from exc

    async def extract(self, image_bytes: bytes, mime_type: str) -> ReactionRecord:
        contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), EXTRACTION_PROMPT]
        return await self._run(contents, DetailedExtraction, to_record)

    async def predict(self, reactants: str, conditions: str) -> ReactionRecord:
        user = f"Reactants: {reactants}\nConditions: {conditions or '(none given)'}"
        return await self._run([PREDICTION_PROMPT, user], PredictionResult, to_prediction_record)
