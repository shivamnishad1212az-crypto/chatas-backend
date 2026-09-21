"""
ChatAs / Satchel backend (Gemini version)
-------------------------------------------
One endpoint: POST /api/ask
Takes a student's question (+ optional subject), asks Gemini to explain
the *reasoning* (not just the answer), and returns it as structured JSON
that the frontend renders as a chat bubble.

Run locally:
    pip install -r requirements.txt
    export GEMINI_API_KEY=AIzaSy...      (or put it in a .env file)
    uvicorn main:app --reload --port 8000

Then point the frontend's API_URL at http://localhost:8000/api/ask
"""

import json
import os
import re
from typing import List

from google import genai
from google.genai import types
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = FastAPI(title="ChatAs / Satchel API")

# CORS: allows your frontend (served from a different origin/port) to call this API.
# BEFORE DEPLOYING: replace "*" with your real site's domain(s), e.g.
#   allow_origins=["https://chatas.com", "https://www.chatas.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # We don't crash on import (so the server can still start for local testing
    # of non-AI routes), but /api/ask will fail clearly if this is missing.
    print("WARNING: GEMINI_API_KEY is not set. /api/ask will fail until it is.")

client = genai.Client(api_key=api_key) if api_key else None

MODEL = "gemini-3.6-flash"
ALLOWED_SUBJECTS = {"math", "science", "languages", "history", "general"}

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1500)
    subject: str = Field(default="general")


class AskResponse(BaseModel):
    intro: str
    steps: List[str]
    followup: str


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """You are Satchel, the study tutor behind the ChatAs website.
A student has asked a {subject} question. Explain the REASONING behind the
answer, not just the final result -- the whole point is that the student
understands the "why," not just this one answer.

Respond with ONLY valid JSON (no markdown code fences, no commentary before
or after), in exactly this shape:

{{
  "intro": "one short, warm sentence introducing the explanation",
  "steps": ["step 1", "step 2", "step 3"],
  "followup": "one short sentence inviting them to try a similar problem"
}}

Rules:
- 3 to 6 steps, each 1-3 sentences, in plain language a student would understand.
- Build the explanation up logically -- each step should follow from the last.
- If the question looks like it's asking you to just do a graded assignment
  wholesale (e.g. "write my essay on X" or "solve all 10 problems below"),
  instead teach the underlying concept using one representative example from
  what they gave you, and say so gently in the intro.
- Do not use markdown formatting (no **, no #) inside the JSON string values.
- Do not include anything outside the JSON object.
"""


def build_system_prompt(subject: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(subject=subject)


def extract_json(text: str) -> dict:
    """Gemini is instructed to return raw JSON, but strip code fences defensively
    in case it wraps the response in ```json ... ``` anyway."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    if not client:
        raise HTTPException(
            status_code=500,
            detail="Server is missing its GEMINI_API_KEY. Set it and restart.",
        )

    subject = payload.subject.lower().strip()
    if subject not in ALLOWED_SUBJECTS:
        subject = "general"

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=build_system_prompt(subject),
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

    raw_text = response.text or ""

    try:
        parsed = extract_json(raw_text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="Couldn't parse the AI's response. Please try again.",
        )

    return AskResponse(
        intro=parsed.get("intro", "Here's the reasoning:"),
        steps=parsed.get("steps", []),
        followup=parsed.get("followup", ""),
    )
