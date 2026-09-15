import os
import duckdb
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.responses import JSONResponse
from datetime import datetime

# ============ CONFIG ============
API_KEY = os.environ.get("API_KEY", "psychoxd")
DEVELOPER = "@psychopathmc"
SUPPORT_MSG = "For API purchase, contact @psychopathmc"

PHONE_BASE = "https://archive.org/download/psycho-phone-db"
AADHAR_BASE = "https://archive.org/download/psycho-aadhar-db"

app = FastAPI(title="PsychopathMC OSINT API", version="17.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(FastAPIHTTPException)
async def custom_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    return JSONResponse(status_code=exc.status_code, content={
        "error": exc.detail, "developer": DEVELOPER, "support": SUPPORT_MSG
    })

# ============ DuckDB Connection ============
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        _conn = duckdb.connect()
        _conn.execute("SET home_directory='/tmp'")
        _conn.execute("SET extension_directory='/tmp/duckdb_extensions'")
        _conn.execute("INSTALL httpfs; LOAD httpfs;")
        _conn.execute("SET threads=2;")
    return _conn


def fetch_data(base_url: str, shard: int, column: str, value: str, limit: int = 15):
    """DuckDB se directly remote Parquet query karo — streaming, no full download"""
    try:
        file_url = f"{base_url}/idx_{'phone' if 'phone' in base_url else 'aadhar'}.{shard}.parquet"
        # Better: derive filename properly
        if "phone" in base_url:
            file_url = f"{base_url}/idx_phone.{shard}.parquet"
        else:
            file_url = f"{base_url}/idx_aadhar.{shard}.parquet"

        con = get_conn()
        sql = f"""
            SELECT name, fathersName, phoneNumber, aadharNumber, otherNumber, address
            FROM read_parquet('{file_url}')
            WHERE {column} = '{value}'
            LIMIT {limit}
        """
        rows = con.execute(sql).fetchall()
        cols = [d[0] for d in con.description]
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return []


@app.get("/")
def root():
    return {
        "app": "PsychopathMC OSINT API",
        "records": 2_504_793_870,
        "indexes": {"phone": True, "aadhar": True},
        "index_source": "internet_archive",
        "developer": DEVELOPER,
        "support": SUPPORT_MSG,
    }

@app.get("/health")
def health():
    return {"status": "ok", "developer": DEVELOPER, "support": SUPPORT_MSG}

@app.get("/search")
def search(
    q: str | None = Query(None),
    mobile: str | None = Query(None),
    key: str = Query(...),
    limit: int = Query(5, ge=1, le=20)
):
    if key != API_KEY:
        raise HTTPException(401, "Invalid or missing API key")
    query = (q or mobile or "").strip()
    if not query:
        raise HTTPException(422, "Provide q or mobile")

    shard = int(query[-1]) % 7

    # Phone first
    results = fetch_data(PHONE_BASE, shard, "phoneNumber", query, limit)

    # Aadhaar fallback
    if not results:
        results = fetch_data(AADHAR_BASE, shard, "aadharNumber", query, limit)

    # Deduplicate
    seen, unique = set(), []
    for row in results:
        a = row.get("aadharNumber")
        if a not in seen:
            seen.add(a); unique.append(row)

    return {
        "success": len(unique) > 0,
        "query": query,
        "count": len(unique),
        "results": unique,
        "developer": DEVELOPER,
        "support": SUPPORT_MSG,
    }        raise HTTPException(422, "Provide q or mobile")
    shard = int(query[-1]) % 7
    phone_url = PHONE_URLS.get(shard)
    results = fetch_data(phone_url, "phoneNumber", query, limit) if phone_url else []
    if not results:
        aadhar_url = AADHAR_URLS.get(shard)
        results = fetch_data(aadhar_url, "aadharNumber", query, limit) if aadhar_url else []
    seen, unique = set(), []
    for row in results:
        a = row.get("aadharNumber")
        if a not in seen:
            seen.add(a); unique.append(row)
    return {
        "success": len(unique) > 0,
        "query": query,
        "count": len(unique),
        "results": unique,
        "developer": DEVELOPER,
        "support": SUPPORT_MSG,
    }
