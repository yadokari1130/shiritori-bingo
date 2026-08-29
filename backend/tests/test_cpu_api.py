"""CPU対戦および補助モードのAPI統合テスト。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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

        # CPU 1 をキック（削除）
        cpu1_id = next(p["id"] for p in players2 if p["name"] == "CPU 1")
        r_kick = host.post(f"/api/rooms/{room_id}/kick", json={"playerId": cpu1_id})
        assert r_kick.status_code == 200
        players_after_kick = r_kick.json()["gameState"]["players"]
        assert len(players_after_kick) == 3
        assert [p["name"] for p in players_after_kick if p.get("isCpu")] == ["CPU 2"]

        # CPUを再度追加 -> 残っている最大番号(2)+1の「CPU 3」が割り振られ、CPU 2と被らない（欠番OK）
        r_readd = host.post(f"/api/rooms/{room_id}/cpu")
        assert r_readd.status_code == 200
        players_readded = r_readd.json()["gameState"]["players"]
        assert len(players_readded) == 4
        readded_cpu_names = [p["name"] for p in players_readded if p.get("isCpu")]
        assert "CPU 2" in readded_cpu_names
        assert "CPU 3" in readded_cpu_names
        assert len(set(readded_cpu_names)) == 2  # 被りなし

        # もう1体追加 -> 「CPU 4」が割り振られる
        r_cpu4 = host.post(f"/api/rooms/{room_id}/cpu")
        assert r_cpu4.status_code == 200
        players_cpu4 = r_cpu4.json()["gameState"]["players"]
        assert len(players_cpu4) == 5
        cpu4_names = [p["name"] for p in players_cpu4 if p.get("isCpu")]
        assert set(cpu4_names) == {"CPU 2", "CPU 3", "CPU 4"}


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
    """GET /api/rooms/{room_id}/assist および GameState.assistSuggestions で全員共通の候補単語が取得できることを確認。"""
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
        r_start = host.post(f"/api/rooms/{room_id}/start")
        assert r_start.status_code == 200
        start_state = r_start.json()["gameState"]
        assert "assistSuggestions" in start_state
        assert isinstance(start_state["assistSuggestions"], list)
        assert len(start_state["assistSuggestions"]) > 0

        # ホストとゲストで同一の候補単語が返る
        r_assist_host = host.get(f"/api/rooms/{room_id}/assist")
        r_assist_guest = guest.get(f"/api/rooms/{room_id}/assist")
        assert r_assist_host.status_code == 200
        assert r_assist_guest.status_code == 200
        assert r_assist_host.json()["suggestions"] == start_state["assistSuggestions"]
        assert r_assist_guest.json()["suggestions"] == start_state["assistSuggestions"]

        # スキップして手番交代
        current_player_id = start_state["currentPlayerId"]
        r_skip = host.post(
            f"/api/rooms/{room_id}/action",
            json={"type": "skip", "subjectId": current_player_id},
        )
        assert r_skip.status_code == 200
        next_state = r_skip.json()["gameState"]
        assert "assistSuggestions" in next_state
        assert isinstance(next_state["assistSuggestions"], list)
        assert len(next_state["assistSuggestions"]) > 0

        # 次の手番でもホストとゲストで共通の候補が返る
        r_assist_next_host = host.get(f"/api/rooms/{room_id}/assist")
        r_assist_next_guest = guest.get(f"/api/rooms/{room_id}/assist")
        assert r_assist_next_host.json()["suggestions"] == next_state["assistSuggestions"]
        assert r_assist_next_guest.json()["suggestions"] == next_state["assistSuggestions"]


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


def test_cpu_never_becomes_host_on_leave():
    """ホストが退出した際、CPUではなく次の人間プレイヤーが親になり、人間がいない場合はNoneになることを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host, TestClient(app) as guest:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        r_host = host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        assert r_host.status_code == 200

        # CPUを追加（参加順: HostPlayer -> CPU 1）
        r_cpu = host.post(f"/api/rooms/{room_id}/cpu")
        cpu_pid = next(p["id"] for p in r_cpu.json()["gameState"]["players"] if p.get("isCpu"))

        # 人間ゲストが参加（参加順: HostPlayer -> CPU 1 -> GuestPlayer）
        r_guest = guest.post(f"/api/rooms/{room_id}/join", json={"name": "GuestPlayer"})
        guest_pid = r_guest.json()["playerId"]

        # ホスト（HostPlayer）が退出 -> CPU 1ではなくGuestPlayerがホストになること
        r_leave = host.post(f"/api/rooms/{room_id}/leave")
        assert r_leave.status_code == 200

        state = asyncio.run(dao.load_room_state(room_id))
        assert state is not None
        assert state.hostPlayerId == guest_pid
        assert state.hostPlayerId != cpu_pid

        # 唯一の人間であるGuestPlayerも退出 -> ホストはNoneになり、CPUがホストにならないこと
        r_guest_leave = guest.post(f"/api/rooms/{room_id}/leave")
        assert r_guest_leave.status_code == 200

        state2 = asyncio.run(dao.load_room_state(room_id))
        assert state2 is not None
        assert state2.hostPlayerId is None


def test_change_host_to_cpu_forbidden():
    """親変更APIでCPUプレイヤーを指定した場合に400エラーで拒絶されることを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host, TestClient(app) as guest:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        guest.post(f"/api/rooms/{room_id}/join", json={"name": "GuestPlayer"})

        r_cpu = host.post(f"/api/rooms/{room_id}/cpu")
        cpu_pid = next(p["id"] for p in r_cpu.json()["gameState"]["players"] if p.get("isCpu"))

        # CPUを指定して親変更を試みる -> 400
        r_fail = host.post(f"/api/rooms/{room_id}/host", json={"playerId": cpu_pid})
        assert r_fail.status_code == 400
        assert "CPU" in r_fail.json()["detail"]


def test_return_to_lobby_cpu_never_becomes_host():
    """ロビーに戻る際、CPUが親に選出されないことを確認。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as host:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        r_host = host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        host_pid = r_host.json()["playerId"]

        # CPU追加して開始
        host.post(f"/api/rooms/{room_id}/cpu")
        host.post(f"/api/rooms/{room_id}/start")

        # 状態を強制的にresultに変更
        async def set_result_phase():
            st = await dao.load_room_state(room_id)
            assert st is not None
            st.phase = "result"
            await dao.save_room_state(room_id, st)

        asyncio.run(set_result_phase())

        # ロビーに戻る
        r_lobby = host.post(f"/api/rooms/{room_id}/lobby")
        assert r_lobby.status_code == 200
        gs = r_lobby.json()["gameState"]
        assert gs["hostPlayerId"] == host_pid
        assert not any(p["id"] == gs["hostPlayerId"] and p.get("isCpu") for p in gs["players"])
