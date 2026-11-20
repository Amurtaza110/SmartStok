import logging
import os
import secrets
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("smartstock.ai_service")
app = FastAPI(title="SmartStock AI Service", version="1.0.0")

INVENTORY_URL = os.environ.get("INVENTORY_SERVICE_URL", "").rstrip("/")
INVENTORY_TOKEN = os.environ.get("INVENTORY_SERVICE_TOKEN", "")
AI_TOKEN = os.environ.get("AI_SERVICE_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))
DATABASE_PATH = os.environ.get(
    "AI_DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "data.sqlite3"),
)
_indexed_vectors = None
_indexed_fingerprint = None


@contextmanager
def database():
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_PATH)), exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with database() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legacy_id INTEGER UNIQUE,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS chat_session_idx
                ON chat_messages(user_id, session_id, id);
            CREATE TABLE IF NOT EXISTS forecast_results (
                product_id INTEGER PRIMARY KEY,
                forecast_dates_json TEXT NOT NULL,
                forecast_values_json TEXT NOT NULL,
                recommended_reorder INTEGER NOT NULL,
                model_used TEXT NOT NULL,
                mae REAL,
                generated_at TEXT NOT NULL
            );
        """)


initialize_database()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    user_id: int = Field(gt=0)
    session_id: str = Field(min_length=1, max_length=100)


class ForecastBatchRequest(BaseModel):
    product_ids: list[int] = Field(max_length=1000)


class LegacyChatRecord(BaseModel):
    id: int
    user_id: int
    session_id: str
    role: str
    message: str
    created_at: str


class LegacyForecastRecord(BaseModel):
    product_id: int
    dates: list[str]
    values: list[float]
    recommended_reorder: int
    model_used: str
    mae: float | None = None
    generated_at: str


class LegacyChatImport(BaseModel):
    records: list[LegacyChatRecord]


class LegacyForecastImport(BaseModel):
    records: list[LegacyForecastRecord]


def verify_service_token(x_service_token: str = Header(default="")):
    if not AI_TOKEN or not secrets.compare_digest(x_service_token, AI_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid service credentials")


def inventory_get(path: str, params: dict | None = None):
    if not INVENTORY_URL or not INVENTORY_TOKEN:
        raise HTTPException(status_code=503, detail="Inventory service is not configured")
    try:
        response = requests.get(
            f"{INVENTORY_URL}{path}",
            headers={"X-Service-Token": INVENTORY_TOKEN},
            params=params,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Inventory service request failed")
        raise HTTPException(status_code=502, detail="Inventory service is unavailable") from exc
    return response.json()


@lru_cache(maxsize=1)
def sentence_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    try:
        return SentenceTransformer(os.environ.get(
            "SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"
        ))
    except Exception:
        logger.exception("Could not load sentence transformer model")
        return None


@app.get("/health")
def health():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        response.raise_for_status()
        models = [model["name"] for model in response.json().get("models", [])]
    except (requests.RequestException, KeyError, ValueError):
        return {"status": "ok", "service": "ai", "ollama_running": False, "models": []}
    return {"status": "ok", "service": "ai", "ollama_running": True, "models": models}


@app.post("/v1/chat", dependencies=[Depends(verify_service_token)])
def chat(payload: ChatRequest):
    context = inventory_get("/internal/ai/context/")
    with database() as connection:
        history = connection.execute(
            "SELECT role, message FROM chat_messages "
            "WHERE user_id = ? AND session_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 20",
            (payload.user_id, payload.session_id),
        ).fetchall()
        connection.execute(
            "INSERT INTO chat_messages (user_id, session_id, role, message, created_at) "
            "VALUES (?, ?, 'user', ?, ?)",
            (
                payload.user_id,
                payload.session_id,
                payload.message,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    today = date.today().strftime("%A, %d %B %Y")
    system_message = (
        "You are SmartStock AI, an inventory assistant. Use only the live data "
        "provided below for business facts. If data is missing, say so. Be concise "
        "and give practical actions. Currency: PKR.\n\n"
        f"LIVE INVENTORY DATA:\n{context['context']}\n\nToday's date: {today}"
    )
    messages = [{"role": "system", "content": system_message}]
    messages.extend(
        {"role": item["role"], "content": item["message"]}
        for item in reversed(history[:10])
    )
    messages.append({"role": "user", "content": payload.message})
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 512},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Ollama request failed")
        raise HTTPException(status_code=502, detail="Ollama is unavailable") from exc
    content = response.json().get("message", {}).get("content")
    if not content:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response")
    with database() as connection:
        connection.execute(
            "INSERT INTO chat_messages (user_id, session_id, role, message, created_at) "
            "VALUES (?, ?, 'assistant', ?, ?)",
            (
                payload.user_id,
                payload.session_id,
                content,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return {"success": True, "response": content, "model": OLLAMA_MODEL}


@app.get("/v1/chat/history/{session_id}", dependencies=[Depends(verify_service_token)])
def chat_history(session_id: str, user_id: int = Query(gt=0)):
    with database() as connection:
        records = connection.execute(
            "SELECT role, message, created_at FROM chat_messages "
            "WHERE user_id = ? AND session_id = ? ORDER BY created_at, id",
            (user_id, session_id),
        ).fetchall()
    return [dict(record) for record in records]


@app.delete("/v1/chat/history/{session_id}", dependencies=[Depends(verify_service_token)])
def clear_chat_history(session_id: str, user_id: int = Query(gt=0)):
    with database() as connection:
        cursor = connection.execute(
            "DELETE FROM chat_messages WHERE user_id = ? AND session_id = ?",
            (user_id, session_id),
        )
    return {"deleted": cursor.rowcount}


@app.get("/v1/search", dependencies=[Depends(verify_service_token)])
def search(q: str = Query(min_length=1, max_length=300), limit: int = 12):
    global _indexed_vectors, _indexed_fingerprint
    products = inventory_get("/internal/ai/products/")
    if not products:
        return {"query": q, "results": [], "mode": "semantic"}

    model = sentence_model()
    if model is not None:
        fingerprint = hashlib.sha256(
            json.dumps(products, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if fingerprint != _indexed_fingerprint:
            texts = [product["searchable_text"] for product in products]
            _indexed_vectors = model.encode(texts, normalize_embeddings=True)
            _indexed_fingerprint = fingerprint
        vectors = _indexed_vectors
        query_vector = model.encode([q], normalize_embeddings=True)[0]
        scores = vectors @ query_vector
        ranked = sorted(
            ((float(score), product) for score, product in zip(scores, products)),
            key=lambda row: row[0],
            reverse=True,
        )
        results = [
            {"id": product["id"], "score": round(score * 100, 1)}
            for score, product in ranked[:max(1, min(limit, 50))]
            if score >= 0.2
        ]
        return {"query": q, "results": results, "mode": "semantic"}

    terms = q.casefold().split()
    ranked = []
    for product in products:
        searchable = product["searchable_text"].casefold()
        score = sum(term in searchable for term in terms)
        if score:
            ranked.append((score, product["id"]))
    ranked.sort(reverse=True)
    return {
        "query": q,
        "results": [{"id": product_id, "score": None}
                    for _, product_id in ranked[:max(1, min(limit, 50))]],
        "mode": "keyword",
    }


@app.post("/v1/reindex", dependencies=[Depends(verify_service_token)])
def reindex():
    global _indexed_vectors, _indexed_fingerprint
    model = sentence_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Semantic search model is unavailable")
    products = inventory_get("/internal/ai/products/")
    _indexed_vectors = model.encode(
        [product["searchable_text"] for product in products],
        normalize_embeddings=True,
    ) if products else None
    _indexed_fingerprint = hashlib.sha256(
        json.dumps(products, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"count": len(products)}


def calculate_forecast(product_id: int, days: int = 30):
    days = max(1, min(days, 90))
    history = inventory_get(f"/internal/ai/sales/{product_id}/", {"days": 120})
    values = history["values"]
    if not values or sum(values) <= 0:
        raise HTTPException(
            status_code=422,
            detail="Not enough recorded sales to generate a demand forecast",
        )

    daily_average = sum(values[-14:]) / min(len(values), 14)
    predicted = round(daily_average, 1)
    start = date.today() + timedelta(days=1)
    forecast_dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    forecast_values = [predicted] * days
    reorder = round(sum(forecast_values) * 1.2)
    return {
        "success": True,
        "dates": forecast_dates,
        "values": forecast_values,
        "recommended_reorder": reorder,
        "model": "14-day moving average",
        "mae": None,
    }


def cached_forecast(product_id: int):
    with database() as connection:
        record = connection.execute(
            "SELECT * FROM forecast_results WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    if not record:
        return None
    return {
        "success": True,
        "dates": json.loads(record["forecast_dates_json"]),
        "values": json.loads(record["forecast_values_json"]),
        "recommended_reorder": record["recommended_reorder"],
        "model": record["model_used"],
        "mae": record["mae"],
        "generated_at": record["generated_at"],
        "cached": True,
    }


def save_forecast(
    product_id: int,
    result: dict,
    generated_at: str | None = None,
    overwrite: bool = True,
):
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    query = """
        INSERT INTO forecast_results (
            product_id, forecast_dates_json, forecast_values_json,
            recommended_reorder, model_used, mae, generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    if overwrite:
        query += """
            ON CONFLICT(product_id) DO UPDATE SET
                forecast_dates_json = excluded.forecast_dates_json,
                forecast_values_json = excluded.forecast_values_json,
                recommended_reorder = excluded.recommended_reorder,
                model_used = excluded.model_used,
                mae = excluded.mae,
                generated_at = excluded.generated_at
        """
    else:
        query = query.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
    with database() as connection:
        connection.execute(
            query,
            (
                product_id,
                json.dumps(result["dates"]),
                json.dumps(result["values"]),
                result["recommended_reorder"],
                result["model"],
                result.get("mae"),
                generated_at,
            ),
        )
    return {**result, "generated_at": generated_at, "cached": False}


@app.get("/v1/forecast/{product_id}", dependencies=[Depends(verify_service_token)])
def get_forecast(product_id: int, days: int = 30):
    cached = cached_forecast(product_id)
    if cached:
        return cached
    return save_forecast(product_id, calculate_forecast(product_id, days))


@app.post("/v1/forecast/{product_id}", dependencies=[Depends(verify_service_token)])
def refresh_forecast(product_id: int, days: int = 30):
    return save_forecast(product_id, calculate_forecast(product_id, days))


@app.get("/v1/forecasts", dependencies=[Depends(verify_service_token)])
def list_forecasts():
    with database() as connection:
        records = connection.execute(
            "SELECT * FROM forecast_results ORDER BY recommended_reorder DESC"
        ).fetchall()
    return [
        {
            "product_id": record["product_id"],
            "dates": json.loads(record["forecast_dates_json"]),
            "values": json.loads(record["forecast_values_json"]),
            "recommended_reorder": record["recommended_reorder"],
            "model": record["model_used"],
            "mae": record["mae"],
            "generated_at": record["generated_at"],
        }
        for record in records
    ]


@app.post("/v1/forecasts", dependencies=[Depends(verify_service_token)])
def run_forecasts(payload: ForecastBatchRequest):
    generated = 0
    skipped = 0
    forecasts = []
    for product_id in dict.fromkeys(payload.product_ids):
        try:
            result = calculate_forecast(product_id)
        except HTTPException as exc:
            if exc.status_code == 422:
                skipped += 1
                continue
            raise
        saved = save_forecast(product_id, result)
        forecasts.append({
            "product_id": product_id,
            "recommended_reorder": saved["recommended_reorder"],
        })
        generated += 1
    return {
        "success": True,
        "generated": generated,
        "skipped": skipped,
        "forecasts": forecasts,
    }


@app.post("/v1/migrate/chat-history", dependencies=[Depends(verify_service_token)])
def import_legacy_chat(payload: LegacyChatImport):
    with database() as connection:
        for record in payload.records:
            connection.execute(
                """
                INSERT OR IGNORE INTO chat_messages
                    (legacy_id, user_id, session_id, role, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.user_id,
                    record.session_id,
                    record.role,
                    record.message,
                    record.created_at,
                ),
            )
    return {"received": len(payload.records)}


@app.post("/v1/migrate/forecasts", dependencies=[Depends(verify_service_token)])
def import_legacy_forecasts(payload: LegacyForecastImport):
    for record in payload.records:
        save_forecast(record.product_id, {
            "dates": record.dates,
            "values": record.values,
            "recommended_reorder": record.recommended_reorder,
            "model": record.model_used,
            "mae": record.mae,
        }, generated_at=record.generated_at, overwrite=False)
    return {"received": len(payload.records)}
