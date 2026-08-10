import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.models import CardOptions, Settings


@pytest.fixture(autouse=True)
def reset_db(tmp_path: Path):
    asyncio.run(db.close_db())
    db.DB_PATH = tmp_path / "test.db"
    yield
    asyncio.run(db.close_db())


def test_create_room():
    settings = Settings(cardSize=3)
    with TestClient(app) as client:
        response = client.post("/api/rooms", json={"settings": settings.model_dump()})
    assert response.status_code == 200
    data = response.json()
    assert "roomId" in data
    assert data["gameState"]["phase"] == "setup"


def test_join_and_start():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        r1 = creator.post(f"/api/rooms/{room_id}/join", json={"name": "太郎"})
        assert r1.status_code == 200
        pid1 = r1.json()["playerId"]
        assert r1.json()["isHost"] is True

        r2 = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "花子"})
        assert r2.status_code == 200

        start = creator.post(f"/api/rooms/{room_id}/start")
        assert start.status_code == 200
        gs = start.json()["gameState"]
        assert gs["phase"] == "playing"
        current = gs["currentPlayerId"]

        client = creator if current == pid1 else joiner
        free = gs["freeChar"]
        action = client.post(
            f"/api/rooms/{room_id}/action", json={"type": "word", "word": free + "い"}
        )
        assert action.status_code == 200
        assert len(action.json()["gameState"]["wordHistory"]) == 1


def test_reconnect_by_cookie_without_name():
    settings = Settings(cardSize=3)
    with TestClient(app) as client:
        room_id = client.post(
            "/api/rooms", json={"settings": settings.model_dump()}
        ).json()["roomId"]
        first = client.post(f"/api/rooms/{room_id}/join", json={"name": "太郎"})
        player_id = first.json()["playerId"]

        reconnected = client.post(f"/api/rooms/{room_id}/join", json={})

    assert reconnected.status_code == 200
    assert reconnected.json()["playerId"] == player_id
    assert reconnected.json()["gameState"]["players"][0]["name"] == "太郎"


def test_invalid_word_skips_turn():
    settings = Settings(cardSize=3, invalidAction="skip")
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        r1 = creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        pid1 = r1.json()["playerId"]
        joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})

        start = creator.post(f"/api/rooms/{room_id}/start")
        gs = start.json()["gameState"]
        current = gs["currentPlayerId"]

        client = creator if current == pid1 else joiner
        action = client.post(
            f"/api/rooms/{room_id}/action", json={"type": "word", "word": "ずるい"}
        )
        assert action.status_code == 200
        data = action.json()["gameState"]
        assert len(data["wordHistory"]) == 0
        assert data["currentPlayerId"] != current


def test_host_only_start():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})
        start = joiner.post(f"/api/rooms/{room_id}/start")
        assert start.status_code == 403


def test_name_change():
    settings = Settings(cardSize=3)
    with TestClient(app) as client:
        res = client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        r1 = client.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        pid1 = r1.json()["playerId"]
        name_change = client.put(
            f"/api/rooms/{room_id}/name", json={"name": "AA"}
        )
        assert name_change.status_code == 200
        players = name_change.json()["gameState"]["players"]
        assert any(p["id"] == pid1 and p["name"] == "AA" for p in players)


def test_settings_update():
    settings = Settings(cardSize=3)
    with TestClient(app) as client:
        res = client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        client.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        new_settings = Settings(cardSize=3, timeLimitSeconds=60)
        update = client.put(
            f"/api/rooms/{room_id}/settings",
            json={"settings": new_settings.model_dump()},
        )
        assert update.status_code == 200
        assert update.json()["gameState"]["settings"]["timeLimitSeconds"] == 60


def test_leave_room():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        r2 = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})
        pid2 = r2.json()["playerId"]
        leave = creator.post(f"/api/rooms/{room_id}/leave")
        assert leave.status_code == 200
        assert leave.json()["gameState"]["hostPlayerId"] == pid2


def test_change_host():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        r2 = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})
        pid2 = r2.json()["playerId"]

        # 親以外のプレイヤーは親変更できない
        fail = joiner.post(f"/api/rooms/{room_id}/host", json={"playerId": pid2})
        assert fail.status_code == 403

        # 親はホストを変更できる
        ok = creator.post(f"/api/rooms/{room_id}/host", json={"playerId": pid2})
        assert ok.status_code == 200
        assert ok.json()["gameState"]["hostPlayerId"] == pid2


def test_kick_player():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        r1 = creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        pid1 = r1.json()["playerId"]
        r2 = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})
        pid2 = r2.json()["playerId"]

        # 親以外のプレイヤーはキックできない
        fail = joiner.post(f"/api/rooms/{room_id}/kick", json={"playerId": pid2})
        assert fail.status_code == 403

        # 自分自身はキックできない
        self_kick = creator.post(f"/api/rooms/{room_id}/kick", json={"playerId": pid1})
        assert self_kick.status_code == 400

        # 親は参加者をキックできる
        ok = creator.post(f"/api/rooms/{room_id}/kick", json={"playerId": pid2})
        assert ok.status_code == 200
        assert len(ok.json()["gameState"]["players"]) == 1
        assert ok.json()["gameState"]["players"][0]["id"] == pid1


def test_undo():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        r1 = creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        pid1 = r1.json()["playerId"]
        joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})

        start = creator.post(f"/api/rooms/{room_id}/start")
        gs = start.json()["gameState"]
        current = gs["currentPlayerId"]

        client = creator if current == pid1 else joiner
        free = gs["freeChar"]
        action = client.post(
            f"/api/rooms/{room_id}/action", json={"type": "word", "word": free + "い"}
        )
        assert action.status_code == 200
        assert len(action.json()["gameState"]["wordHistory"]) == 1

        undo = creator.post(f"/api/rooms/{room_id}/action", json={"type": "undo"})
        assert undo.status_code == 200
        assert len(undo.json()["gameState"]["wordHistory"]) == 0


def test_team_mode():
    settings = Settings(
        cardSize=3,
        mode="team",
        teamCount=2,
        cardOptions=CardOptions(dakuten=True),
    )
    with TestClient(app) as creator, TestClient(app) as joiner:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        r1 = creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        pid1 = r1.json()["playerId"]
        r2 = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})
        pid2 = r2.json()["playerId"]

        teams = res.json()["gameState"]["teams"]
        assert len(teams) == 2
        team_a = teams[0]["id"]
        team_b = teams[1]["id"]
        creator.put(f"/api/rooms/{room_id}/team", json={"teamId": team_a})
        joiner.put(f"/api/rooms/{room_id}/team", json={"teamId": team_b})

        start = creator.post(f"/api/rooms/{room_id}/start")
        assert start.status_code == 200
        gs = start.json()["gameState"]
        assert gs["phase"] == "playing"
        current_team = gs["currentTeamId"]
        # チームメンバーどちらかが入力可能
        client = creator if current_team == team_a else joiner
        free = gs["freeChar"]
        action = client.post(
            f"/api/rooms/{room_id}/action", json={"type": "word", "word": free + "う"}
        )
        assert action.status_code == 200
        history = action.json()["gameState"]["wordHistory"]
        assert len(history) == 1
        assert history[0]["playerId"] in {pid1, pid2}


def test_reconnect_without_name():
    """Cookie がある場合、名前入力なし（空文字またはNone）で再接続できる。"""
    settings = Settings(cardSize=3)
    with TestClient(app) as client:
        res = client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        # 初回参加でCookie発行
        r1 = client.post(f"/api/rooms/{room_id}/join", json={"name": "太郎"})
        assert r1.status_code == 200
        pid1 = r1.json()["playerId"]

        # 再接続：名前を空文字で送信
        reconnect = client.post(f"/api/rooms/{room_id}/join", json={"name": ""})
        assert reconnect.status_code == 200
        assert reconnect.json()["playerId"] == pid1

        # 新規クライアント（Cookieなし）：名前が空なら400エラー
        with TestClient(app) as new_client:
            fail_join = new_client.post(
                f"/api/rooms/{room_id}/join", json={"name": ""}
            )
            assert fail_join.status_code == 400


def test_team_leave_and_rejoin():
    """チーム戦でチームに参加後、抜ける（未所属に戻る）ことができる。"""
    settings = Settings(
        cardSize=3,
        mode="team",
        teamCount=2,
    )
    with TestClient(app) as client:
        res = client.post("/api/rooms", json={"settings": settings.model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]
        r1 = client.post(f"/api/rooms/{room_id}/join", json={"name": "Player1"})
        assert r1.status_code == 200
        pid1 = r1.json()["playerId"]

        teams = res.json()["gameState"]["teams"]
        assert len(teams) == 2
        team_a = teams[0]["id"]
        team_b = teams[1]["id"]

        # チームAに参加
        r_join_team = client.put(
            f"/api/rooms/{room_id}/team", json={"teamId": team_a}
        )
        assert r_join_team.status_code == 200
        gs = r_join_team.json()["gameState"]
        player1 = next(p for p in gs["players"] if p["id"] == pid1)
        assert player1["teamId"] == team_a
        team1 = next(t for t in gs["teams"] if t["id"] == team_a)
        assert pid1 in team1["memberPlayerIds"]

        # チームから抜ける (teamId: null)
        r_leave_team = client.put(
            f"/api/rooms/{room_id}/team", json={"teamId": None}
        )
        assert r_leave_team.status_code == 200
        gs_leave = r_leave_team.json()["gameState"]
        player1_after = next(p for p in gs_leave["players"] if p["id"] == pid1)
        assert player1_after["teamId"] is None
        team1_after = next(t for t in gs_leave["teams"] if t["id"] == team_a)
        assert pid1 not in team1_after["memberPlayerIds"]

        # 別のチームBに参加
        r_rejoin_team = client.put(
            f"/api/rooms/{room_id}/team", json={"teamId": team_b}
        )
        assert r_rejoin_team.status_code == 200
        gs_rejoin = r_rejoin_team.json()["gameState"]
        player1_rejoin = next(p for p in gs_rejoin["players"] if p["id"] == pid1)
        assert player1_rejoin["teamId"] == team_b
        team2 = next(t for t in gs_rejoin["teams"] if t["id"] == team_b)
        assert pid1 in team2["memberPlayerIds"]


def test_delete_room_by_host():
    settings = Settings(cardSize=3)
    with TestClient(app) as host, TestClient(app) as guest:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        r_host = host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        assert r_host.status_code == 200
        assert r_host.json()["isHost"] is True

        r_guest = guest.post(f"/api/rooms/{room_id}/join", json={"name": "GuestPlayer"})
        assert r_guest.status_code == 200

        # ホストが部屋を解散
        del_res = host.delete(f"/api/rooms/{room_id}")
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        # ルームが存在しないことを確認
        get_res = host.get(f"/api/rooms/{room_id}")
        assert get_res.status_code == 404


def test_delete_room_by_non_host_forbidden():
    settings = Settings(cardSize=3)
    with TestClient(app) as host, TestClient(app) as guest:
        res = host.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        host.post(f"/api/rooms/{room_id}/join", json={"name": "HostPlayer"})
        guest.post(f"/api/rooms/{room_id}/join", json={"name": "GuestPlayer"})

        # 非ホストが解散を試みる -> 403
        del_res = guest.delete(f"/api/rooms/{room_id}")
        assert del_res.status_code == 403


def test_cookie_secure_and_samesite_attributes(monkeypatch):
    from app import security

    # 1. デフォルト (HTTP/ローカル): secure=False, samesite=lax
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    assert security.is_cookie_secure() is False
    assert security.get_cookie_samesite() == "lax"

    # 2. FRONTEND_ORIGIN が https の場合: secure=True, samesite=lax
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://example.com")
    assert security.is_cookie_secure() is True
    assert security.get_cookie_samesite() == "lax"

    # 3. COOKIE_SECURE 明示指定
    monkeypatch.setenv("COOKIE_SECURE", "true")
    assert security.is_cookie_secure() is True
    monkeypatch.setenv("COOKIE_SECURE", "false")
    assert security.is_cookie_secure() is False

    # 4. COOKIE_SAMESITE 明示指定
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    assert security.get_cookie_samesite() == "none"

    # 5. 実際のAPIレスポンスCookieの属性検証
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("COOKIE_SAMESITE", "lax")
    settings = Settings(cardSize=3)
    with TestClient(app) as client:
        res = client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        join_res = client.post(f"/api/rooms/{room_id}/join", json={"name": "テスト太郎"})
        assert join_res.status_code == 200
        cookie_header = join_res.headers.get("set-cookie", "")
        assert "shiritori_session=" in cookie_header
        assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()
        assert "Secure" in cookie_header or "secure" in cookie_header.lower()
        assert "samesite=lax" in cookie_header.lower()


def test_join_during_playing_or_result():
    settings = Settings(cardSize=3)
    with TestClient(app) as creator, TestClient(app) as joiner, TestClient(app) as late_comer:
        res = creator.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        creator.post(f"/api/rooms/{room_id}/join", json={"name": "A"})
        joiner.post(f"/api/rooms/{room_id}/join", json={"name": "B"})
        start = creator.post(f"/api/rooms/{room_id}/start")
        assert start.status_code == 200

        # ゲーム中に新規プレイヤーが参加しようとすると「ゲーム中のため参加できません」
        late_join = late_comer.post(f"/api/rooms/{room_id}/join", json={"name": "C"})
        assert late_join.status_code == 403
        assert late_join.json()["detail"] == "ゲーム中のため参加できません"

