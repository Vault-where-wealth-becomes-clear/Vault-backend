import threading
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiter import limiter
from app.routers import (
    accounts,
    auth,
    category_rules,
    dashboard,
    exchange_rates,
    exports,
    health,
    installments,
    transactions,
    uploads,
    users,
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.run_worker_inline:
        # Hostings gratuitos no siempre ofrecen un segundo servicio (worker)
        # sin costo. Corremos el long-polling de SQS en un thread daemon dentro
        # del mismo proceso de la API en vez de exigir un proceso separado.
        import asyncio

        from worker.run import poll_loop

        thread = threading.Thread(
            target=lambda: asyncio.run(poll_loop()), daemon=True, name="sqs-worker"
        )
        thread.start()
        logger.info("inline_worker_started")
    yield


app = FastAPI(title="Vault API", version=settings.app_version, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": str(exc.status_code)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    response = JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "code": "500"},
    )
    # Los handlers de Exception "pelada" corren en ServerErrorMiddleware, por fuera
    # de CORSMiddleware — sin este header el browser muestra un falso error de CORS
    # en vez del 500 real. Ver: https://github.com/tiangolo/fastapi/discussions/4934
    origin = request.headers.get("origin")
    if origin in settings.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(uploads.router)
app.include_router(transactions.router)
app.include_router(installments.router)
app.include_router(exchange_rates.router)
app.include_router(category_rules.router)
app.include_router(dashboard.router)
app.include_router(exports.router)
