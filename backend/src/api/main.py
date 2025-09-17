from typing import List, Optional

import os
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# App metadata and tags for OpenAPI
openapi_tags = [
    {"name": "Health", "description": "Service health and documentation helpers."},
    {"name": "Quotes", "description": "Quotable API proxy and normalization."},
    {"name": "Recipes", "description": "MealDB API proxy and normalization for recipes."},
]

app = FastAPI(
    title="Recipe Journal Backend API",
    description="Proxy endpoints for MealDB and Quotable with normalized responses for the frontend.",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# CORS config (allow all origins by default; can be restricted via env)
ALLOWED_ORIGINS = os.getenv("BACKEND_CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in ALLOWED_ORIGINS.split(",")] if ALLOWED_ORIGINS else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- External API constants ---------
MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"
QUOTABLE_BASE = "https://api.quotable.io"


# --------- Pydantic Models (Normalized) ---------
class Quote(BaseModel):
    text: str = Field(..., description="Quote text")
    author: str = Field(..., description="Author of the quote")
    tags: List[str] = Field(default_factory=list, description="Tags associated with the quote")
    source: str = Field(default="quotable", description="Source identifier")


class Recipe(BaseModel):
    id: str = Field(..., description="Unique ID of the recipe (MealDB idMeal)")
    title: str = Field(..., description="Recipe title (strMeal)")
    category: Optional[str] = Field(None, description="Meal category")
    area: Optional[str] = Field(None, description="Cuisine area/region")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL")
    tags: List[str] = Field(default_factory=list, description="List of tags")
    source_url: Optional[str] = Field(None, description="Original source URL for the recipe")
    youtube_url: Optional[str] = Field(None, description="YouTube video URL if available")
    instructions: Optional[str] = Field(None, description="Cooking instructions")
    ingredients: List[str] = Field(
        default_factory=list,
        description="List of ingredients with measures in the form 'ingredient - measure'",
    )
    raw: Optional[dict] = Field(default=None, description="Raw MealDB item for debugging")


class RecipesResponse(BaseModel):
    count: int = Field(..., description="Number of recipes")
    recipes: List[Recipe] = Field(..., description="List of normalized recipes")


# --------- Normalization helpers ---------
def _extract_ingredients(meal: dict) -> List[str]:
    """Extract non-empty ingredient/measure pairs from MealDB item."""
    ingredients: List[str] = []
    # MealDB uses strIngredient1..20 and strMeasure1..20
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        meas = (meal.get(f"strMeasure{i}") or "").strip()
        if not ing:
            continue
        if meas:
            ingredients.append(f"{ing} - {meas}")
        else:
            ingredients.append(ing)
    return ingredients


def _normalize_meal(meal: dict, include_raw: bool = False) -> Recipe:
    tags = []
    raw_tags = meal.get("strTags")
    if isinstance(raw_tags, str) and raw_tags.strip():
        # MealDB tags are comma separated string
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    normalized = Recipe(
        id=str(meal.get("idMeal", "")),
        title=meal.get("strMeal") or "",
        category=meal.get("strCategory"),
        area=meal.get("strArea"),
        thumbnail_url=meal.get("strMealThumb"),
        tags=tags,
        source_url=meal.get("strSource"),
        youtube_url=meal.get("strYoutube"),
        instructions=meal.get("strInstructions"),
        ingredients=_extract_ingredients(meal),
        raw=meal if include_raw else None,
    )
    return normalized


# --------- Health and Docs helpers ---------
@app.get("/", tags=["Health"], summary="Health check", description="Basic health check for the backend service.")
def health_check():
    """PUBLIC_INTERFACE
    Health check endpoint.
    Returns a simple message to verify the service is running.
    """
    return {"message": "Healthy"}


@app.get(
    "/docs/websocket-usage",
    tags=["Health"],
    summary="WebSocket usage notes",
    description="This project currently uses only HTTP endpoints; no WebSocket endpoints are exposed.",
)
def websocket_usage_notes():
    """PUBLIC_INTERFACE
    Returns a note indicating no websocket endpoints exist.
    """
    return {
        "websocket": False,
        "notes": "No websocket endpoints in this backend. Real-time interactions are not required for this project.",
    }


# --------- Quotable Proxy ---------
@app.get(
    "/api/quotes/random",
    response_model=Quote,
    tags=["Quotes"],
    summary="Get a random quote",
    description="Fetches a random quote from Quotable.io and returns a normalized payload.",
)
async def get_random_quote():
    """PUBLIC_INTERFACE
    Get a random quote from Quotable and normalize fields.

    Returns:
        Quote: Normalized quote with text, author, tags, and source.
    """
    url = f"{QUOTABLE_BASE}/random"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch quote: {e}") from e

    data = r.json()
    return Quote(
        text=data.get("content") or "",
        author=data.get("author") or "Unknown",
        tags=data.get("tags") or [],
        source="quotable",
    )


# --------- MealDB Proxies ---------
@app.get(
    "/api/recipes/search",
    response_model=RecipesResponse,
    tags=["Recipes"],
    summary="Search recipes by name",
    description="Proxies MealDB search API (search.php?s=) and returns normalized recipes.",
)
async def search_recipes(
    q: str = Query(..., description="Search query for recipe name (MealDB search by name)"),
    include_raw: bool = Query(False, description="Include raw MealDB response item for each recipe"),
):
    """PUBLIC_INTERFACE
    Search recipes by name.

    Parameters:
        q (str): The text to search for (maps to MealDB search.php?s=).
        include_raw (bool): If true, include the raw MealDB item for each recipe.

    Returns:
        RecipesResponse: Normalized recipes and count.
    """
    url = f"{MEALDB_BASE}/search.php"
    params = {"s": q}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to search recipes: {e}") from e
    payload = r.json()
    meals = payload.get("meals") or []
    recipes = [_normalize_meal(m, include_raw=include_raw) for m in meals]
    return RecipesResponse(count=len(recipes), recipes=recipes)


@app.get(
    "/api/recipes/{meal_id}",
    response_model=Recipe,
    tags=["Recipes"],
    summary="Get recipe by MealDB ID",
    description="Proxies MealDB lookup API (lookup.php?i=) to fetch a recipe by id.",
)
async def get_recipe_by_id(
    meal_id: str,
    include_raw: bool = Query(False, description="Include raw MealDB response item"),
):
    """PUBLIC_INTERFACE
    Look up a specific recipe by MealDB id.

    Parameters:
        meal_id (str): The MealDB idMeal to look up.
        include_raw (bool): If true, include raw MealDB item in the response.

    Returns:
        Recipe: Normalized recipe.
    """
    url = f"{MEALDB_BASE}/lookup.php"
    params = {"i": meal_id}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch recipe: {e}") from e
    payload = r.json()
    meals = payload.get("meals") or []
    if not meals:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _normalize_meal(meals[0], include_raw=include_raw)


@app.get(
    "/api/recipes/random",
    response_model=Recipe,
    tags=["Recipes"],
    summary="Get a random recipe",
    description="Proxies MealDB random selection API (random.php) and returns a normalized recipe.",
)
async def get_random_recipe(
    include_raw: bool = Query(False, description="Include raw MealDB response item"),
):
    """PUBLIC_INTERFACE
    Get a random recipe from MealDB and normalize fields.

    Parameters:
        include_raw (bool): If true, include raw MealDB item in the response.

    Returns:
        Recipe: Normalized recipe.
    """
    url = f"{MEALDB_BASE}/random.php"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch random recipe: {e}") from e
    payload = r.json()
    meals = payload.get("meals") or []
    if not meals:
        raise HTTPException(status_code=502, detail="Malformed response from MealDB")
    return _normalize_meal(meals[0], include_raw=include_raw)
