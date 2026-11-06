"""LedgerLine FastAPI application entry point."""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import connect_db, close_db

import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ledgerline")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await connect_db()
    logger.info("Connected to MongoDB")
    yield
    await close_db()
    logger.info("Disconnected from MongoDB")


app = FastAPI(
    title="LedgerLine",
    description="Money-movement system with integrity over features.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request_id to every request for structured logging."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "method=%s path=%s status=%s elapsed_ms=%.1f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return consistent error format; never leak stack traces."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled error request_id=%s", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred.",
            "request_id": request_id,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ledgerline"}
