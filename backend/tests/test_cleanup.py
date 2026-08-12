import asyncio
from pathlib import Path

import pytest

from app import cleanup, dao, db
from app.models import Player, Settings
from app.orm_models import Room


@pytest.fixture(autouse=True)
def reset_db(tmp_path: Path):
    asyncio.run(db.close_db())
    db.DB_PATH = tmp_path / "test.db"
    asyncio.run(db.init_db())
    yield
    asyncio.run(db.close_db())


@pytest.mark.anyio
async def test_empty_room_cleanup():
    settings = Settings(cardSize=3)

    # 1. 作成直後の0人ルーム (room_recent)
    await dao.create_room("room_recent", None, settings)

    # 2. 35分前（30分以上前）に作成された0人ルーム (room_old_empty)
    await dao.create_room("room_old_empty", None, settings)
    now = dao.now_ms()
    old_time = now - 35 * 60 * 1000
    await Room.filter(id="room_old_empty").update(created_at=old_time, updated_at=old_time)

    # クリーンアップを実行
    await cleanup._cleanup_once()

    # room_recent は削除されず残っていること
    assert await dao.get_room("room_recent") is not None

    # room_old_empty は削除されていること
    assert await dao.get_room("room_old_empty") is None


@pytest.mark.anyio
async def test_stale_sse_session_is_disconnected():
    settings = Settings(cardSize=3)
    await dao.create_room("room_stale", None, settings)
    state = await dao.load_room_state("room_stale")
    assert state is not None
    player = Player(id="player_stale", name="ccc", connectionStatus="connected")
    state.players.append(player)
    await dao.save_room_state("room_stale", state)
    await dao.create_session("session_stale", "room_stale", player.id, "token-stale")
    await dao.update_session_connections("session_stale", 1)

    stale_before = dao.now_ms() + 1
    expired = await dao.expire_stale_sessions(stale_before)

    assert expired == [("room_stale", player.id)]
    players = await dao.list_players("room_stale")
    assert players[0]["connection_status"] == "disconnected"
