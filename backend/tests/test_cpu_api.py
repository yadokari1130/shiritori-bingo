"""CPU対戦および補助モードのAPI統合テスト。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import dao, db
from app.main import app
from app.models import Settings
from app.routers import rooms


@pytest.fixture(autouse=True)
def reset_db(tmp_path: Path):
    asyncio.run(db.close_db())
    db.DB_PATH = tmp_path / "test.db"
    yield
    asyncio.run(db.close_db())


def test_add_cpu_by_host():
    """ホストがロビーでCPUを追加できることを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host, TestClient(app) as guest:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        guest.post(f"/api/rooms/{room_id}/join", json={"name": "GuestPlayer"})

        # ゲストがCPU追加を試みる -> 403
        r_forbidden = guest.post(f"/api/rooms/{room_id}/cpu")
        assert r_forbidden.status_code == 403

        # ホストがCPUを追加
        r_cpu1 = host.post(f"/api/rooms/{room_id}/cpu")
        assert r_cpu1.status_code == 200
        players = r_cpu1.json()["gameState"]["players"]
        assert len(players) == 3
        cpu_p = next(p for p in players if p.get("isCpu"))
        assert cpu_p["name"] == "CPU 1"
        assert cpu_p["isCpu"] is True

        # 2体目のCPUを追加
        r_cpu2 = host.post(f"/api/rooms/{room_id}/cpu")
        assert r_cpu2.status_code == 200
        players2 = r_cpu2.json()["gameState"]["players"]
        assert len(players2) == 4
        cpu_names = [p["name"] for p in players2 if p.get("isCpu")]
        assert "CPU 1" in cpu_names
        assert "CPU 2" in cpu_names


def test_start_game_with_human_and_cpu():
    """人間1人＋CPU1人でゲームが開始できることを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})

        # CPU未追加の状態では開始できない（参加者不足）
        r_fail = host.post(f"/api/rooms/{room_id}/start")
        assert r_fail.status_code == 400

        # CPUを追加
        host.post(f"/api/rooms/{room_id}/cpu")

        # 人間1人 + CPU1人でゲーム開始可能
        r_start = host.post(f"/api/rooms/{room_id}/start")
        assert r_start.status_code == 200
        gs = r_start.json()["gameState"]
        assert gs["phase"] == "playing"
        assert len(gs["players"]) == 2


def test_assist_suggestions_api():
    """GET /api/rooms/{room_id}/assist で候補単語が取得できることを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host, TestClient(app) as guest:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        guest.post(f"/api/rooms/{room_id}/join", json={"name": "GuestPlayer"})

        # 対戦前は空リスト
        r_assist_pre = host.get(f"/api/rooms/{room_id}/assist")
        assert r_assist_pre.status_code == 200
        assert r_assist_pre.json()["suggestions"] == []

        # 開始
        host.post(f"/api/rooms/{room_id}/start")

        # 対戦中は候補単語が返る
        r_assist = host.get(f"/api/rooms/{room_id}/assist")
        assert r_assist.status_code == 200
        data = r_assist.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) > 0


def test_kick_cpu_by_host():
    """親がCPUプレイヤーをキックできることを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        r_cpu = host.post(f"/api/rooms/{room_id}/cpu")
        cpu_player = next(p for p in r_cpu.json()["gameState"]["players"] if p.get("isCpu"))

        # キック
        r_kick = host.post(f"/api/rooms/{room_id}/kick", json={"playerId": cpu_player["id"]})
        assert r_kick.status_code == 200
        players_after = r_kick.json()["gameState"]["players"]
        assert len(players_after) == 1
        assert not any(p.get("isCpu") for p in players_after)


@pytest.mark.anyio
async def test_run_cpu_turn_execution():
    """_run_cpu_turn がCPU手番で自動的に単語を確定して手番を進めることを確認。"""
    settings = Settings(cardSize=3)
    room_id = "test_cpu_turn_room"
    await dao.create_room(room_id, None, settings)

    state = await dao.load_room_state(room_id)
    assert state is not None

    # 人間1人とCPU1人
    p1 = rooms.Player(id="p_human", name="Human", isCpu=False, status="active", sortOrder=1)
    p2 = rooms.Player(id="p_cpu", name="CPU 1", isCpu=True, status="active", sortOrder=2)
    state.players = [p1, p2]
    state.hostPlayerId = "p_human"

    rooms.engine.start_game(state, dao.now_ms())
    # 手番をCPUに設定
    state.currentPlayerId = "p_cpu"
    state.roundRoster = ["p_cpu", "p_human"]
    state.orderIndex = 0
    state.round = 1
    await dao.save_room_state(room_id, state)

    # CPUターンを手動実行
    await rooms._run_cpu_turn(room_id, expected_round=1, expected_order_index=0)

    # 実行後の状態を確認
    new_state = await dao.load_room_state(room_id)
    assert new_state is not None
    # 単語履歴またはスキップにより手番が進んでいること
    assert new_state.orderIndex != 0 or new_state.round > 1 or new_state.currentPlayerId != "p_cpu"
    assert len(new_state.wordHistory) > 0 or len(new_state.undoHistory) > 0
