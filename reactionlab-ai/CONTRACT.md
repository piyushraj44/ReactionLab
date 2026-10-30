# ReactionLab AI — API contract v2 (source of truth for frontend + backend)

## Shared types
Field        = {"value": "string", "source": "page" | "ai"}
LabeledField = {"label": "string", "value": "string", "source": "page" | "ai"}

source = "page" -> copied from what is visible in the uploaded image
source = "ai"   -> inferred / predicted by the model from chemistry knowledge (UI shows an "AI-suggested" tag)

Sentinel values (exact strings, always source "page" in notebook mode, "ai" in prediction mode):
  "Not provided"           — information is absent
  "Not clearly identified" — present but illegible / ambiguous

## ReactionRecord (response of both endpoints)
{
  "mode":       "notebook" | "prediction",
  "equation":   Field,              // one-line scheme, e.g. "Salicylic acid + Acetic anhydride → Acetylsalicylic acid + Acetic acid (H2SO4, 85 C)"
  "reactants":  [Field, ...],       // never empty; ["Not provided"] if none
  "products":   [LabeledField x4],  // labels, exact order: "Main product", "By-products", "Possible side products", "Confirmatory test"
  "conditions": [LabeledField x6],  // labels, exact order: "Reagents / catalysts", "Solvent", "Temperature", "Time", "Atmosphere", "Other"
  "procedure":  Field,              // may contain real newlines between steps
  "outcome":    [LabeledField x2]   // labels, exact order: "Yield / result", "Observations"
}

### Provenance rules — notebook mode
- reactants, conditions, procedure, outcome: ALWAYS source "page". Never inferred. (Lab record integrity.)
- equation, and each of the 4 products rows: source "page" if written on the page; otherwise the model MAY infer it
  from chemistry knowledge with source "ai" (or "Not provided" if it cannot reasonably infer).
- Confirmatory test: "page" if a test is written; otherwise a standard test may be suggested with source "ai".

### Prediction mode
- Every field has source "ai".

## Endpoints
POST /api/extract   multipart/form-data, field `file` (jpeg/png/webp/heic, max 10 MB) -> ReactionRecord (mode "notebook")
POST /api/predict   application/json {"reactants": "string (required, 1-500 chars)", "conditions": "string (optional, 0-300 chars)"}
                    -> ReactionRecord (mode "prediction")
GET  /api/health    -> {"status": "ok"}

## Errors — any non-2xx returns {"detail": "human readable message"}
400 — bad upload (no file / not an image / empty)
413 — file too large
422 — invalid predict input (empty/too long), OR the model declined (safety) — detail explains
502 — model call failed / unparseable / busy
503 — GEMINI_API_KEY not configured

## Ports
Backend http://127.0.0.1:8000 ; Frontend Vite 5173 proxies /api -> backend
