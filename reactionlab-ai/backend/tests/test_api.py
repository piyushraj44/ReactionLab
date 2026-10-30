import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.extractors.base import (
    ExtractionFailed,
    ExtractorNotConfigured,
    ReactionExtractor,
    RequestDeclined,
)
from app.extractors.gemini import (
    DetailedExtraction,
    GeminiExtractor,
    PredictionResult,
    SourcedValue,
    to_prediction_record,
    to_record,
)
from app.main import MAX_BYTES, app, get_extractor_dep
from app.schemas import Field, LabeledField, ReactionRecord

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

COND = ["Reagents / catalysts", "Solvent", "Temperature", "Time", "Atmosphere", "Other"]
OUT = ["Yield / result", "Observations"]
PROD = ["Main product", "By-products", "Possible side products", "Confirmatory test"]


def fake_record(mode="notebook") -> ReactionRecord:
    src = "page" if mode == "notebook" else "ai"
    return ReactionRecord(
        mode=mode,
        equation=Field(value="A → B", source=src),
        reactants=[Field(value="A 1 g", source=src)],
        products=[LabeledField(label=l, value="Not provided", source=src) for l in PROD],
        conditions=[LabeledField(label=l, value="Not provided", source=src) for l in COND],
        procedure=Field(value="1. do\n2. thing", source=src),
        outcome=[LabeledField(label=l, value="Not provided", source=src) for l in OUT],
    )


class FakeExtractor(ReactionExtractor):
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.predict_args = None

    async def extract(self, image_bytes, mime_type):
        if self.error:
            raise self.error
        return fake_record("notebook")

    async def predict(self, reactants, conditions):
        self.predict_args = (reactants, conditions)
        if self.error:
            raise self.error
        return fake_record("prediction")


def client_with(ext=None, dep_error=None):
    def dep():
        if dep_error:
            raise dep_error
        return ext or FakeExtractor()

    app.dependency_overrides[get_extractor_dep] = dep
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


def post(c, content=PNG, ctype="image/png", name="x.png"):
    return c.post("/api/extract", files={"file": (name, content, ctype)})


# ---------------- API: health / extract ----------------


def test_health():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_extract_happy_path_shape():
    r = post(client_with())
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"mode", "equation", "reactants", "products", "conditions", "procedure", "outcome"}
    assert j["mode"] == "notebook"
    assert j["equation"] == {"value": "A → B", "source": "page"}
    assert j["reactants"] == [{"value": "A 1 g", "source": "page"}]
    assert [p["label"] for p in j["products"]] == PROD
    assert [c["label"] for c in j["conditions"]] == COND
    assert [o["label"] for o in j["outcome"]] == OUT
    assert j["procedure"]["value"] == "1. do\n2. thing"


def test_generic_content_type_sniffed():
    assert post(client_with(), ctype="application/octet-stream").status_code == 200


def test_non_image_400():
    r = post(client_with(), b"hello world, not an image", "text/plain", "a.txt")
    assert r.status_code == 400 and "detail" in r.json()


def test_image_type_with_text_bytes_400():
    assert post(client_with(), b"just text", "image/png").status_code == 400


def test_empty_400():
    assert post(client_with(), b"").status_code == 400


def test_missing_file_400():
    r = client_with().post("/api/extract")
    assert r.status_code == 400 and isinstance(r.json()["detail"], str)


def test_oversize_413():
    assert post(client_with(), PNG + b"\x00" * MAX_BYTES).status_code == 413


def test_not_configured_503_from_dependency():
    r = post(client_with(dep_error=HTTPException(503, "no key")))
    assert r.status_code == 503 and r.json() == {"detail": "no key"}


def test_not_configured_503_from_extract():
    assert post(client_with(FakeExtractor(ExtractorNotConfigured("nokey")))).status_code == 503


def test_extraction_failed_502():
    r = post(client_with(FakeExtractor(ExtractionFailed("boom"))))
    assert r.status_code == 502 and r.json() == {"detail": "boom"}


def test_no_key_validation_order(monkeypatch):
    from app.extractors import get_extractor

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("EXTRACTOR", "gemini")
    get_extractor.cache_clear()
    try:
        c = TestClient(app)  # real dependency, no override
        assert post(c, b"not an image", "text/plain", "a.txt").status_code == 400
        assert post(c).status_code == 503
    finally:
        get_extractor.cache_clear()


# ---------------- API: predict ----------------


def test_predict_happy_path():
    ext = FakeExtractor()
    r = client_with(ext).post("/api/predict", json={"reactants": "  salicylic acid + acetic anhydride ", "conditions": "H2SO4"})
    assert r.status_code == 200
    j = r.json()
    assert j["mode"] == "prediction"
    assert j["equation"]["source"] == "ai"
    assert [p["label"] for p in j["products"]] == PROD
    assert ext.predict_args == ("salicylic acid + acetic anhydride", "H2SO4")


def test_predict_conditions_optional():
    ext = FakeExtractor()
    assert client_with(ext).post("/api/predict", json={"reactants": "A + B"}).status_code == 200
    assert ext.predict_args == ("A + B", "")


@pytest.mark.parametrize(
    "body",
    [
        {"reactants": ""},
        {"reactants": "   "},
        {"reactants": "x" * 501},
        {"reactants": "A", "conditions": "y" * 301},
        {},
        {"reactants": 5},
    ],
)
def test_predict_invalid_422_string_detail(body):
    r = client_with().post("/api/predict", json=body)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]


def test_predict_bad_json_422_string_detail():
    r = client_with().post("/api/predict", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_predict_declined_422():
    r = client_with(FakeExtractor(RequestDeclined("dangerous"))).post("/api/predict", json={"reactants": "x"})
    assert r.status_code == 422
    assert r.json() == {"detail": "This request can't be processed: dangerous"}


def test_predict_502_and_503():
    c = client_with(FakeExtractor(ExtractionFailed("boom")))
    assert c.post("/api/predict", json={"reactants": "x"}).status_code == 502
    c = client_with(FakeExtractor(ExtractorNotConfigured("k")))
    assert c.post("/api/predict", json={"reactants": "x"}).status_code == 503


# ---------------- mapping / provenance ----------------


def sv(value="", source="page"):
    return SourcedValue(value=value, source=source)


def make_detail(**over):
    base = dict(
        reactants=["  ", " benzaldehyde 1 g "],
        equation=sv(),
        main_product=sv(),
        by_products=sv(),
        possible_side_products=sv(),
        confirmatory_test=sv(),
        reagents_catalysts=" NaOH ",
        solvent="",
        temperature="\n",
        time="2 h",
        atmosphere="",
        other_conditions="",
        procedure=" 1. mix ",
        yield_result="",
        observations="Not clearly identified",
    )
    base.update(over)
    return DetailedExtraction(**base)


def test_mapping_normalization_and_labels():
    r = to_record(make_detail())
    assert r.mode == "notebook"
    assert [x.value for x in r.reactants] == ["benzaldehyde 1 g"]
    assert [p.label for p in r.products] == PROD
    assert [c.label for c in r.conditions] == COND
    assert [c.value for c in r.conditions] == [
        "NaOH", "Not provided", "Not provided", "2 h", "Not provided", "Not provided",
    ]
    assert [o.label for o in r.outcome] == OUT
    assert [o.value for o in r.outcome] == ["Not provided", "Not clearly identified"]
    assert r.procedure.value == "1. mix"
    assert r.equation == Field(value="Not provided", source="page")


def test_provenance_forced_to_page_for_copy_fields():
    # Model wrongly claims "ai" for copy-only data: only the sourced fields may carry "ai".
    r = to_record(make_detail(
        equation=sv("A → B", "ai"),
        main_product=sv("Aspirin", "ai"),
        by_products=sv("Acetic acid", "page"),
        possible_side_products=sv("", "ai"),
        confirmatory_test=sv("FeCl3 test", "ai"),
    ))
    assert all(x.source == "page" for x in r.reactants)
    assert all(x.source == "page" for x in r.conditions)
    assert all(x.source == "page" for x in r.outcome)
    assert r.procedure.source == "page"
    assert r.equation == Field(value="A → B", source="ai")
    srcs = {p.label: (p.value, p.source) for p in r.products}
    assert srcs["Main product"] == ("Aspirin", "ai")
    assert srcs["By-products"] == ("Acetic acid", "page")
    assert srcs["Possible side products"] == ("Not provided", "page")  # sentinel => page
    assert srcs["Confirmatory test"] == ("FeCl3 test", "ai")


def test_empty_reactants():
    assert [x.value for x in to_record(make_detail(reactants=[])).reactants] == ["Not provided"]


def test_literal_backslash_n_converted():
    r = to_record(make_detail(reactants=["A 1 g\\nB 2 g"], procedure="1. Mix\\n2. Heat\\r\\n3. Cool "))
    assert r.procedure.value == "1. Mix\n2. Heat\n3. Cool"
    assert r.reactants[0].value == "A 1 g\nB 2 g"


def make_pred(**over):
    base = dict(
        declined=False, decline_reason="", equation="A + B → C", reactants=["A", "B"],
        main_product="C", by_products="", possible_side_products="D", confirmatory_test="TLC",
        reagents_catalysts="", solvent="EtOH", temperature="", time="", atmosphere="",
        other_conditions="", procedure="1. a\\n2. b", yield_result="60-80%", observations="",
    )
    base.update(over)
    return PredictionResult(**base)


def test_prediction_mapping_all_ai():
    r = to_prediction_record(make_pred())
    assert r.mode == "prediction"
    assert r.equation == Field(value="A + B → C", source="ai")
    assert [p.label for p in r.products] == PROD
    assert [c.label for c in r.conditions] == COND
    assert [o.label for o in r.outcome] == OUT
    assert r.procedure.value == "1. a\n2. b"
    every = [r.equation, *r.reactants, *r.products, *r.conditions, r.procedure, *r.outcome]
    assert all(x.source == "ai" for x in every)
    assert r.products[1].value == "Not provided"


def test_prediction_declined_raises():
    with pytest.raises(RequestDeclined, match="weapon"):
        to_prediction_record(make_pred(declined=True, decline_reason="chemical weapon"))


# ---------------- Gemini fallback (mocked client, no network) ----------------

_GOOD = make_detail()
_GOOD_PRED = make_pred()


class _FakeModels:
    def __init__(self, behaviour):
        self.behaviour = behaviour  # model -> exception or parsed result
        self.calls = []

    async def generate_content(self, model, contents, config):
        self.calls.append(model)
        b = self.behaviour[model]
        if isinstance(b, Exception):
            raise b
        return SimpleNamespace(parsed=b, text=None)


def _extractor(behaviour, monkeypatch, fallback="fb"):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "primary")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", fallback)
    ext = GeminiExtractor()
    models = _FakeModels(behaviour)
    ext._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return ext, models


def _err(cls, code, status):
    return cls(code, {"error": {"code": code, "status": status, "message": "x"}})


def test_fallback_used_on_503(monkeypatch):
    ext, m = _extractor(
        {"primary": _err(genai_errors.ServerError, 503, "UNAVAILABLE"), "fb": _GOOD}, monkeypatch
    )
    r = asyncio.run(ext.extract(PNG, "image/png"))
    assert m.calls == ["primary", "fb"] and r.mode == "notebook"


def test_predict_fallback_used_on_503(monkeypatch):
    ext, m = _extractor(
        {"primary": _err(genai_errors.ServerError, 503, "UNAVAILABLE"), "fb": _GOOD_PRED}, monkeypatch
    )
    r = asyncio.run(ext.predict("A + B", ""))
    assert m.calls == ["primary", "fb"] and r.mode == "prediction"


def test_predict_declined_through_extractor(monkeypatch):
    ext, m = _extractor(
        {"primary": make_pred(declined=True, decline_reason="nope"), "fb": _GOOD_PRED}, monkeypatch
    )
    with pytest.raises(RequestDeclined):
        asyncio.run(ext.predict("x", ""))
    assert m.calls == ["primary"]


def test_both_overloaded_busy_message(monkeypatch):
    e = _err(genai_errors.ServerError, 503, "UNAVAILABLE")
    ext, m = _extractor(
        {"primary": e, "fb": _err(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED")}, monkeypatch
    )
    with pytest.raises(ExtractionFailed) as ei:
        asyncio.run(ext.extract(PNG, "image/png"))
    assert "busy" in str(ei.value) and m.calls == ["primary", "fb"]
    c = client_with(FakeExtractor(ExtractionFailed(str(ei.value))))
    assert post(c).status_code == 502


def test_non_overload_error_no_fallback(monkeypatch):
    ext, m = _extractor(
        {"primary": _err(genai_errors.ClientError, 400, "INVALID_ARGUMENT"), "fb": _GOOD}, monkeypatch
    )
    with pytest.raises(ExtractionFailed) as ei:
        asyncio.run(ext.extract(PNG, "image/png"))
    assert m.calls == ["primary"] and "busy" not in str(ei.value)


def test_fallback_disabled(monkeypatch):
    ext, m = _extractor(
        {"primary": _err(genai_errors.ServerError, 503, "UNAVAILABLE"), "fb": _GOOD}, monkeypatch, fallback=""
    )
    with pytest.raises(ExtractionFailed):
        asyncio.run(ext.extract(PNG, "image/png"))
    assert m.calls == ["primary"]
