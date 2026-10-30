import logging

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app import config  # noqa: F401  (loads .env)
from app.extractors import (
    ExtractionFailed,
    ExtractorNotConfigured,
    ReactionExtractor,
    RequestDeclined,
    get_extractor,
)
from app.schemas import ReactionRecord

logger = logging.getLogger(__name__)

MAX_BYTES = 10 * 1024 * 1024

app = FastAPI(title="ReactionLab AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    reactants: str
    conditions: str = ""

    @field_validator("reactants")
    @classmethod
    def _reactants(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please enter at least one reactant.")
        if len(v) > 500:
            raise ValueError("Reactants must be at most 500 characters.")
        return v

    @field_validator("conditions")
    @classmethod
    def _conditions(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 300:
            raise ValueError("Conditions must be at most 300 characters.")
        return v


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Keep every error as {"detail": "<string>"}."""
    errors = exc.errors()
    if not errors:
        return JSONResponse(status_code=422, content={"detail": "Invalid request."})
    err = errors[0]
    loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query")]
    msg = str(err.get("msg", "Invalid request.")).removeprefix("Value error, ")
    if err.get("type") == "missing":
        msg = f"Field '{loc[-1]}' is required." if loc else "Invalid request."
    elif err.get("type") in ("json_invalid", "model_attributes_type"):
        msg = "Request body must be valid JSON with a 'reactants' string."
    elif err.get("type") == "string_type" and loc:
        msg = f"Field '{loc[-1]}' must be a string."
    return JSONResponse(status_code=422, content={"detail": msg})


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis"):
            return "image/heic"
        if brand in (b"mif1", b"msf1"):
            return "image/heif"
    return None


def get_extractor_dep() -> ReactionExtractor:
    try:
        return get_extractor()
    except ExtractorNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/extract", response_model=ReactionRecord)
async def extract(
    file: UploadFile | None = File(None),
    extractor: ReactionExtractor = Depends(get_extractor_dep),
) -> ReactionRecord:
    if file is None:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    declared = (file.content_type or "").lower()
    if declared and not declared.startswith("image/") and declared != "application/octet-stream":
        raise HTTPException(status_code=400, detail="File must be an image.")
    sniffed = sniff_mime(data)
    if sniffed is None:
        raise HTTPException(
            status_code=400, detail="Unsupported file. Upload a JPEG, PNG, WebP or HEIC image."
        )

    try:
        return await extractor.extract(data, sniffed)
    except ExtractorNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ExtractionFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception:
        logger.exception("Unexpected extraction error")
        raise HTTPException(status_code=502, detail="Extraction failed unexpectedly.")


@app.post("/api/predict", response_model=ReactionRecord)
async def predict(
    body: PredictRequest, extractor: ReactionExtractor = Depends(get_extractor_dep)
) -> ReactionRecord:
    try:
        return await extractor.predict(body.reactants, body.conditions)
    except RequestDeclined as exc:
        raise HTTPException(status_code=422, detail=f"This request can't be processed: {exc}")
    except ExtractorNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ExtractionFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception:
        logger.exception("Unexpected prediction error")
        raise HTTPException(status_code=502, detail="Prediction failed unexpectedly.")
