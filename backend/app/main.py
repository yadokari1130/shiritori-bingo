from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import cleanup, db
from app.routers import rooms


def _load_allowed_origins() -> list[str]:
    """環境変数 FRONTEND_ORIGIN から許可オリジン一覧を読み込む。"""
    raw = os.environ.get("FRONTEND_ORIGIN", "")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    # ローカル開発用のデフォルト
    return ["http://localhost:5173"]


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """起動確認用のヘルスチェックを返す。"""
    return {"status": "ok"}
