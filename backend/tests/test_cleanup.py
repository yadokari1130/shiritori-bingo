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


@pytest.mark.anyio
async def test_active_session_not_expired_under_30s():
    """30秒未満の生存セッションはクリーンアップで失効されないことを確認。"""
    settings = Settings(cardSize=3)
    await dao.create_room("room_active", None, settings)
    state = await dao.load_room_state("room_active")
    assert state is not None
    player = Player(id="player_active", name="Host", connectionStatus="connected", sortOrder=1)
    state.players.append(player)
    state.hostPlayerId = player.id
    await dao.save_room_state("room_active", state)
    await dao.create_session("session_active", "room_active", player.id, "token-active")
    await dao.update_session_connections("session_active", 1)

    # 15秒前の更新時刻を設定（10秒以上経過しているが30秒未満）
    now = dao.now_ms()
    from app.orm_models import PlayerSession
    await PlayerSession.filter(id="session_active").update(last_seen_at=now - 15 * 1000)

    await cleanup._cleanup_once()

    # 切断されていないこと
    refreshed_state = await dao.load_room_state("room_active")
    assert refreshed_state is not None
    assert refreshed_state.players[0].connectionStatus == "connected"
    assert refreshed_state.hostPlayerId == player.id


@pytest.mark.anyio
async def test_result_phase_host_retained_with_cpu():
    """リザルトフェーズでCPUが存在する状態でクリーンアップが走っても人間ホストが維持されること。"""
    settings = Settings(cardSize=3)
    await dao.create_room("room_result_cpu", None, settings)
    state = await dao.load_room_state("room_result_cpu")
    assert state is not None
    state.phase = "result"

    human = Player(id="p_human", name="HumanHost", connectionStatus="connected", sortOrder=1, isCpu=False)
    cpu = Player(id="p_cpu", name="CPU 1", connectionStatus="connected", sortOrder=2, isCpu=True)
    state.players.extend([human, cpu])
    state.hostPlayerId = human.id
    await dao.save_room_state("room_result_cpu", state)

    await dao.create_session("session_human", "room_result_cpu", human.id, "token-human")
    await dao.update_session_connections("session_human", 1)

    await cleanup._cleanup_once()

    refreshed = await dao.load_room_state("room_result_cpu")
    assert refreshed is not None
    assert refreshed.hostPlayerId == human.id
    assert refreshed.hostPlayerId != cpu.id
    assert not any(p.id == refreshed.hostPlayerId and p.isCpu for p in refreshed.players)


def test_elect_host_never_picks_cpu():
    """elect_host がCPUを絶対に選出しないことの確認。"""
    cpu1 = Player(id="cpu1", name="CPU 1", connectionStatus="connected", sortOrder=1, isCpu=True)
    cpu2 = Player(id="cpu2", name="CPU 2", connectionStatus="connected", sortOrder=2, isCpu=True)
    human1 = Player(id="human1", name="Human", connectionStatus="connected", sortOrder=3, isCpu=False)

    # CPUが先頭にあっても人間が選出される
    assert cleanup.elect_host([cpu1, cpu2, human1]) == "human1"

    # 人間が切断中の場合は選出されない
    human1_disc = Player(id="human1", name="Human", connectionStatus="disconnected", sortOrder=3, isCpu=False)
    assert cleanup.elect_host([cpu1, cpu2, human1_disc]) is None

    # 人間が0人の場合はNone
    assert cleanup.elect_host([cpu1, cpu2]) is None

