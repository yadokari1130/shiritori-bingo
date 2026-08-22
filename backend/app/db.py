import asyncio
import os
import subprocess
import sys
from pathlib import Path

from tortoise import Tortoise

from app import dao
from app.config import get_tortoise_config

DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).resolve().parent.parent / "data" / "shiritori-bingo.db"))
_write_lock = asyncio.Lock()


def _run_migrations() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(DB_PATH)
    subprocess.run(
        [sys.executable, "-m", "aerich", "upgrade"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        check=True,
    )


async def init_db() -> None:
    """Aerichでスキーマを適用してからTortoiseを初期化する。"""
    global _write_lock
    _write_lock = asyncio.Lock()
    _run_migrations()
    await Tortoise.init(config=get_tortoise_config(DB_PATH))
    conn = Tortoise.get_connection("default")
    await conn.execute_script("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;")
    await dao.reset_connection_statuses()


async def close_db() -> None:
    """Tortoiseの接続を閉じる。"""
    if Tortoise._inited:
        await Tortoise.close_connections()
