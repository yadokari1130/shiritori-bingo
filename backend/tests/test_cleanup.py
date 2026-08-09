import asyncio
from pathlib import Path

import pytest

from app import cleanup, dao, db
from app.models import Settings


@pytest.fixture(autouse=True)
def reset_db(tmp_path: Path):
    asyncio.run(db.close_db())
    db.DB_PATH = tmp_path / "test.db"
    asyncio.run(db.init_db())
    yield
    asyncio.run(db.close_db())


@pytest.mark.anyio
async def test_empty_room_cleanup():
    conn = await db.get_db()
    settings = Settings(cardSize=3)

    # 1. 作成直後の0人ルーム (room_recent)
    await dao.create_room(conn, "room_recent", None, settings)

    # 2. 35分前（30分以上前）に作成された0人ルーム (room_old_empty)
    await dao.create_room(conn, "room_old_empty", None, settings)
    now = dao.now_ms()
    old_time = now - 35 * 60 * 1000
    await conn.execute(
        "UPDATE rooms SET created_at = ?, updated_at = ? WHERE id = ?",
        (old_time, old_time, "room_old_empty"),
    )
    await conn.commit()

    # クリーンアップを実行
    await cleanup._cleanup_once()

    # room_recent は削除されず残っていること
    assert await dao.get_room(conn, "room_recent") is not None

    # room_old_empty は削除されていること
    assert await dao.get_room(conn, "room_old_empty") is None
