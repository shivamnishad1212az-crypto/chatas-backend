# ChatAs / Satchel backend

A single-endpoint FastAPI service that powers the `#try` question box on the
ChatAs site. It sends the student's question to the Claude API and returns
a structured, step-by-step explanation.

## 1. Install dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Add your API key

```bash
cp .env.example .env
# then edit .env and paste your real Anthropic API key
```

The app reads `ANTHROPIC_API_KEY` from the environment. If you're not using
a tool that auto-loads `.env` files, export it manually instead:

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## 3. Run it

```bash
uvicorn main:app --reload --port 8000
```

Check it's alive:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

## 4. Test the endpoint directly

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why does dividing by a fraction flip it?", "subject": "math"}'
```

You should get back JSON like:

```json
{
  "intro": "Good question — here's the reasoning:",
  "steps": ["...", "...", "..."],
  "followup": "Want to try one yourself?"
}
```

## 5. Point the frontend at it

In your site's `<script>` (see the `#try` section snippet), set:

```js
const API_URL = "http://localhost:8000/api/ask";
```

## Before deploying to production

- **CORS**: in `main.py`, replace `allow_origins=["*"]` with your real
  domain(s), e.g. `["https://chatas.com"]`. Leaving it wide open lets any
  website call your API and burn your Claude API credits.
- **Rate limiting**: this version has none. Anyone who finds the endpoint
  can call it repeatedly. Consider adding a rate limiter (e.g.
  `slowapi`) or putting the API behind a gateway that limits requests
  per IP before launch.
- **Hosting**: this runs anywhere that runs Python (Render, Railway, Fly.io,
  a VPS, etc.). Set `ANTHROPIC_API_KEY` as an environment variable /
  secret in whichever platform you use — never commit your real key to git.
- **HTTPS**: serve this over HTTPS in production; most hosting platforms
  handle this for you automatically.
