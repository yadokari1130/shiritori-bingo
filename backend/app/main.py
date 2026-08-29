import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from secure import (
    ReferrerPolicy,
    Secure,
    StrictTransportSecurity,
    XContentTypeOptions,
    XFrameOptions,
)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from tortoise import Tortoise

from app import cleanup, db
from app.limiter import limiter
from app.routers import rooms

logger = logging.getLogger("shiritori_bingo")

secure_headers = Secure(
    hsts=StrictTransportSecurity().include_subdomains().preload().max_age(31536000),
    xcto=XContentTypeOptions().nosniff(),
    xfo=XFrameOptions().deny(),
    referrer=ReferrerPolicy().strict_origin_when_cross_origin(),
)


def _load_allowed_origins() -> list[str]:
    """環境変数 FRONTEND_ORIGIN から許可オリジン一覧を読み込む。"""
    raw = os.environ.get("FRONTEND_ORIGIN", "")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    # ローカル開発用・テスト用のデフォルト
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """アプリケーション起動/終了時の処理。"""
    await db.init_db()
    cleanup_task = asyncio.create_task(cleanup.run_cleanup_loop())
    forced_skip_task = asyncio.create_task(cleanup.run_forced_skip_loop())
    yield
    cleanup_task.cancel()
    forced_skip_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await forced_skip_task
    except asyncio.CancelledError:
        pass
    await db.close_db()


app = FastAPI(title="しりとりビンゴ API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # 1. Request ID の生成とコンテキスト付与
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]

    # 2. Origin チェック（状態変更リクエストのみ）
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        if origin:
            allowed = _load_allowed_origins()
            # ワイルドカードでない場合のみチェック
            if allowed and "*" not in allowed and origin not in allowed:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "不正なオリジンからのリクエストです。"},
                    headers={"X-Request-ID": request_id},
                )

    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    secure_headers.set_headers(response)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """起動確認およびデータベース導通確認用ヘルスチェック。"""
    try:
        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Health check DB failed: {exc}")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "Database connection failed"},
        )
