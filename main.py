import os
import requests
import pyarrow.parquet as pq
import io
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.responses import JSONResponse
from datetime import datetime, timedelta

# ============ CONFIG ============
API_KEY = os.environ.get("API_KEY", "psychoxd")
DEVELOPER = "@psychopathmc"
SUPPORT_MSG = "For API purchase, contact @psychopathmc"

# 🎯 Internet Archive URLs (Phone)
PHONE_URLS = {
    0: "https://archive.org/download/psycho-phone-db/idx_phone.0.parquet",
    1: "https://archive.org/download/psycho-phone-db/idx_phone.1.parquet",
    2: "https://archive.org/download/psycho-phone-db/idx_phone.2.parquet",
    3: "https://archive.org/download/psycho-phone-db/idx_phone.3.parquet",
    4: "https://archive.org/download/psycho-phone-db/idx_phone.4.parquet",
    5: "https://archive.org/download/psycho-phone-db/idx_phone.5.parquet",
    6: "https://archive.org/download/psycho-phone-db/idx_phone.6.parquet",
}

# 🎯 Internet Archive URLs (Aadhaar)
AADHAR_URLS = {
    0: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.0.parquet",
    1: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.1.parquet",
    2: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.2.parquet",
    3: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.3.parquet",
    4: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.4.parquet",
    5: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.5.parquet",
    6: "https://archive.org/download/psycho-aadhar-db/idx_aadhar.6.parquet",
}

CACHE_TTL = 300

app = FastAPI(title="PsychopathMC OSINT API", version="16.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(FastAPIHTTPException)
async def custom_http_exception_handler(request: Request, exc: FastAPIHTTPException):
    return JSONResponse(status_code=exc.status_code, content={
        "error": exc.detail, "developer": DEVELOPER, "support": SUPPORT_MSG
    })

_cache, _cache_time = {}, {}

def get_cache(key):
    if key in _cache and (datetime.now() - _cache_time[key]).seconds < CACHE_TTL:
        return _cache[key]
    return None

def set_cache(key, data):
    _cache[key] = data
    _cache_time[key] = datetime.now()
    if len(_cache) > 100:
        oldest = min(_cache_time, key=_cache_time.get)
        del _cache[oldest]
        del _cache_time[oldest]

def fetch_data(url: str, column: str, value: str, limit: int = 15):
    if not url:
        return []
    cached_df = get_cache(url)
    if cached_df is not None:
        df = cached_df
    else:
        try:
            print(f"[FETCH] {url}")
            resp = requests.get(url, timeout=180, stream=True)
            if resp.status_code != 200:
                return []
            needed_cols = ["name", "fathersName", "phoneNumber",
                          "aadharNumber", "otherNumber", "address"]
            table = pq.read_table(io.BytesIO(resp.content), columns=needed_cols)
            df = table.to_pandas()
            set_cache(url, df)
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            return []
    if column not in df.columns:
        return []
    filtered = df[df[column] == value]
    return filtered.head(limit).to_dict(orient="records")

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
