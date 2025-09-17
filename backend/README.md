# Recipe Journal Backend (FastAPI)

This backend exposes proxy endpoints for MealDB and Quotable with normalized data models suitable for the React frontend.

Run locally:
- Install dependencies: `pip install -r requirements.txt`
- Start server: `uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000`

OpenAPI docs:
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

Environment variables:
- BACKEND_CORS_ALLOW_ORIGINS (optional): comma-separated list of allowed origins. Example: `http://localhost:3000,https://yourapp.com`
  - Defaults to "*" for development.

Endpoints:

Health
- GET / -> { message: "Healthy" }
- GET /docs/websocket-usage -> notes about websockets (none used)

Quotes
- GET /api/quotes/random -> Normalized random quote from Quotable
  Response:
  {
    "text": "...",
    "author": "...",
    "tags": [],
    "source": "quotable"
  }

Recipes (MealDB)
- GET /api/recipes/search?q=chicken&include_raw=false
  Returns: { count, recipes: Recipe[] }

- GET /api/recipes/{meal_id}?include_raw=false
  Returns: Recipe

- GET /api/recipes/random?include_raw=false
  Returns: Recipe

Normalized Recipe fields:
- id, title, category, area, thumbnail_url, tags[], source_url, youtube_url, instructions, ingredients[]

Notes:
- include_raw=true appends the original MealDB item to each recipe for debugging.
- All endpoints have CORS enabled using BACKEND_CORS_ALLOW_ORIGINS.
