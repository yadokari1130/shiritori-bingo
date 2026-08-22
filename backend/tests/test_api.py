from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import dao, db
from app.main import app
from app.models import CardOptions, Settings


@pytest.fixture(autouse=True)
def reset_db(tmp_path: Path):
    db.DB_PATH = tmp_path / "test.db"
    yield


def make_clients(base_client: TestClient, count: int = 1):
    """単一のTestClientトランスポート（同一イベントループ）を共有する独立クライアントを生成する。"""
    clients = [
        httpx.Client(
            transport=base_client._transport,
            base_url=str(base_client.base_url),
            follow_redirects=True,
        )
        for _ in range(count)
    ]
    return clients[0] if count == 1 else tuple(clients)


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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
            f"/api/rooms/{room_id}/action", json={"type": "word", "word": "きりん"}
        )
        assert action.status_code == 200
        data = action.json()["gameState"]
        assert len(data["wordHistory"]) == 0
        assert data["currentPlayerId"] != current


def test_host_only_start():
    settings = Settings(cardSize=3)
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
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
    with TestClient(app) as base:
        client, new_client = make_clients(base, 2)
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
    with TestClient(app) as base:
        host, guest = make_clients(base, 2)
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
    with TestClient(app) as base:
        host, guest = make_clients(base, 2)
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
    with TestClient(app) as base:
        creator, joiner, late_comer = make_clients(base, 3)
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


def test_room_with_password():
    settings = Settings(cardSize=3)
    with TestClient(app) as base:
        creator, joiner1, joiner2 = make_clients(base, 3)
        # パスワード付きルームを作成
        res = creator.post(
            "/api/rooms",
            json={"settings": settings.model_dump(), "password": "mypassword123"},
        )
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        # ルーム情報を取得 -> hasPassword が True
        info_res = creator.get(f"/api/rooms/{room_id}")
        assert info_res.status_code == 200
        assert info_res.json()["hasPassword"] is True

        # パスワード未指定で参加 -> 403 パスワードが違います
        r_nopass = joiner1.post(f"/api/rooms/{room_id}/join", json={"name": "花子"})
        assert r_nopass.status_code == 403
        assert r_nopass.json()["detail"] == "パスワードが違います"

        # 誤ったパスワードで参加 -> 403 パスワードが違います
        r_wrongpass = joiner1.post(
            f"/api/rooms/{room_id}/join",
            json={"name": "花子", "password": "wrongpassword"},
        )
        assert r_wrongpass.status_code == 403
        assert r_wrongpass.json()["detail"] == "パスワードが違います"

        # ホスト（部屋作成者）はパスワード未指定（またはnull）でも認証スキップで参加できる
        r_creator = creator.post(
            f"/api/rooms/{room_id}/join",
            json={"name": "太郎"},
        )
        assert r_creator.status_code == 200
        assert r_creator.json()["isHost"] is True

        # 正しいパスワードで参加者が参加
        r_joiner = joiner2.post(
            f"/api/rooms/{room_id}/join",
            json={"name": "次郎", "password": "mypassword123"},
        )
        assert r_joiner.status_code == 200

        # 再接続時（Cookie保持）はパスワードなしでも復帰できる
        r_reconnect = joiner2.post(
            f"/api/rooms/{room_id}/join",
            json={"name": ""},
        )
        assert r_reconnect.status_code == 200


def test_room_without_password():
    settings = Settings(cardSize=3)
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
        # パスワードなしでルーム作成
        res = creator.post(
            "/api/rooms",
            json={"settings": settings.model_dump(), "password": None},
        )
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        # ルーム情報を取得 -> hasPassword が False
        info_res = creator.get(f"/api/rooms/{room_id}")
        assert info_res.status_code == 200
        assert info_res.json()["hasPassword"] is False

        # パスワードなしで正常に参加できる
        join_res = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "花子"})
        assert join_res.status_code == 200


def test_creator_late_join_takes_host():
    settings = Settings(cardSize=3)
    with TestClient(app) as base:
        creator, joiner = make_clients(base, 2)
        # 作成者がルームを作成
        res = creator.post(
            "/api/rooms",
            json={"settings": settings.model_dump()},
        )
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        # 他の参加者が先に部屋に参加 -> 一時的にホストになる
        r1 = joiner.post(f"/api/rooms/{room_id}/join", json={"name": "一般参加者"})
        assert r1.status_code == 200
        joiner_pid = r1.json()["playerId"]
        assert r1.json()["isHost"] is True
        assert r1.json()["gameState"]["hostPlayerId"] == joiner_pid

        # 部屋の作成者が後から参加 -> 自動的にホストが作成者に切り替わる
        r2 = creator.post(f"/api/rooms/{room_id}/join", json={"name": "部屋作成者"})
        assert r2.status_code == 200
        creator_pid = r2.json()["playerId"]
        assert r2.json()["isHost"] is True
        assert r2.json()["gameState"]["hostPlayerId"] == creator_pid


def test_lobby_disconnect_removes_player_and_allows_reconnect_without_name():
    settings = Settings(cardSize=3)
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post(
            "/api/rooms", json={"settings": settings.model_dump()}
        )
        room_id = res.json()["roomId"]

        # ホストと参加者が参加
        r1 = host_client.post(f"/api/rooms/{room_id}/join", json={"name": "ホスト"})
        assert r1.status_code == 200
        r2 = joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "参加者1"})
        assert r2.status_code == 200
        joiner_pid = r2.json()["playerId"]

        # 参加者が切断通知を送信（タブを閉じる動作をシミュレート）
        dc_res = joiner_client.post(f"/api/rooms/{room_id}/disconnect")
        assert dc_res.status_code == 200

        # ホスト視点でゲーム状態を確認
        state = base.portal.call(dao.load_room_state, room_id)
        assert state is not None
        # ロビー（setup）のため、切断された参加者はプレイヤー一覧から即座に削除されている
        player_ids = [p.id for p in state.players]
        assert joiner_pid not in player_ids
        assert len(state.players) == 1

        # ホストがゲームを開始しようとしても参加者不足（1人）で開始できない
        start_res = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res.status_code == 400
        assert "参加者が2人以上必要です" in start_res.json()["detail"]

        # 切断された参加者がCookieを持って再接続（名前入力不要）
        reconnect_res = joiner_client.post(
            f"/api/rooms/{room_id}/join", json={"name": ""}
        )
        assert reconnect_res.status_code == 200
        reconnect_data = reconnect_res.json()
        assert reconnect_data["playerId"] == joiner_pid
        # 名前「参加者1」が復元されてプレイヤー一覧に再度追加されている
        reconnected_players = reconnect_data["gameState"]["players"]
        assert len(reconnected_players) == 2
        joined_p = next(p for p in reconnected_players if p["id"] == joiner_pid)
        assert joined_p["name"] == "参加者1"
        assert joined_p["connectionStatus"] == "connected"

        # 再度ゲーム開始 -> 2人で正常にゲームが開始される
        start_res2 = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res2.status_code == 200
        gs = start_res2.json()["gameState"]
        assert gs["phase"] == "playing"
        assert len(gs["players"]) == 2


def test_playing_disconnect_and_reconnect():
    """対戦中に切断された場合、connectionStatusがdisconnectedになり、再接続で復帰する。"""
    settings = Settings(cardSize=3, mode="individual")
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        # ホストと参加者が参加
        r1 = host_client.post(f"/api/rooms/{room_id}/join", json={"name": "ホスト"})
        assert r1.status_code == 200
        r2 = joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "参加者1"})
        assert r2.status_code == 200
        joiner_pid = r2.json()["playerId"]

        # ゲーム開始
        start_res = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["gameState"]["phase"] == "playing"

        # 参加者が切断通知を送信
        dc_res = joiner_client.post(f"/api/rooms/{room_id}/disconnect")
        assert dc_res.status_code == 200

        # 切断後：対戦中のためプレイヤーは削除されず、connectionStatusがdisconnectedになる
        state = base.portal.call(dao.load_room_state, room_id)
        assert state is not None
        assert len(state.players) == 2
        p2 = next(p for p in state.players if p.id == joiner_pid)
        assert p2.connectionStatus == "disconnected"
        assert p2.disconnectedAt is not None

        # 参加者が再接続（join API）
        reconnect_res = joiner_client.post(
            f"/api/rooms/{room_id}/join", json={"name": ""}
        )
        assert reconnect_res.status_code == 200
        state2 = base.portal.call(dao.load_room_state, room_id)
        assert state2 is not None
        p2_reconnected = next(p for p in state2.players if p.id == joiner_pid)
        assert p2_reconnected.connectionStatus == "connected"
        assert p2_reconnected.disconnectedAt is None


def test_notify_disconnect_endpoint():
    """POST /api/rooms/{room_id}/disconnect による即時切断通知の検証。"""
    settings = Settings(cardSize=3, mode="individual")
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        # ロビー参加
        host_client.post(f"/api/rooms/{room_id}/join", json={"name": "ホスト"})
        r2 = joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "参加者1"})
        joiner_pid = r2.json()["playerId"]

        # ロビー時に切断通知を送信 -> プレイヤーがロビーから即時除外される
        dc_res = joiner_client.post(f"/api/rooms/{room_id}/disconnect")
        assert dc_res.status_code == 200
        state = base.portal.call(dao.load_room_state, room_id)
        assert state is not None
        assert joiner_pid not in [p.id for p in state.players]

        # 再接続してゲーム開始
        joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": ""})
        start_res = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res.status_code == 200

        # 対戦中に切断通知を送信 -> connectionStatusがdisconnectedになる
        dc_res2 = joiner_client.post(f"/api/rooms/{room_id}/disconnect")
        assert dc_res2.status_code == 200
        state2 = base.portal.call(dao.load_room_state, room_id)
        assert state2 is not None
        p2 = next(p for p in state2.players if p.id == joiner_pid)
        assert p2.connectionStatus == "disconnected"


def test_result_disconnect_and_return_to_lobby_removes_disconnected_player():
    """リザルト画面で切断したプレイヤーが、ロビーに戻った際にプレイヤー一覧から削除されることを検証する。"""
    settings = Settings(cardSize=3, mode="individual", targetTurns=1, endCondition="turns")
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]

        # ホストと参加者が参加
        r1 = host_client.post(f"/api/rooms/{room_id}/join", json={"name": "ホスト"})
        assert r1.status_code == 200
        host_pid = r1.json()["playerId"]
        r2 = joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "参加者1"})
        assert r2.status_code == 200
        joiner_pid = r2.json()["playerId"]

        # ゲーム開始
        start_res = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res.status_code == 200

        # 1ターンで終了させるため、2手番スキップまたは単語入力を行う
        state = base.portal.call(dao.load_room_state, room_id)
        assert state is not None
        # 1人目スキップ
        s1 = host_client.post(
            f"/api/rooms/{room_id}/action",
            json={"type": "skip", "subjectId": state.currentPlayerId},
        )
        assert s1.status_code == 200
        state = base.portal.call(dao.load_room_state, room_id)
        # 2人目スキップ
        s2 = host_client.post(
            f"/api/rooms/{room_id}/action",
            json={"type": "skip", "subjectId": state.currentPlayerId},
        )
        assert s2.status_code == 200

        # リザルト画面に遷移していることを確認
        state = base.portal.call(dao.load_room_state, room_id)
        assert state is not None
        assert state.phase == "result"
        assert len(state.players) == 2

        # 参加者がリザルト画面で切断通知を送信
        dc_res = joiner_client.post(f"/api/rooms/{room_id}/disconnect")
        assert dc_res.status_code == 200

        # リザルト画面ではプレイヤー一覧に切断状態で残っている（結果表示のため）
        state_in_result = base.portal.call(dao.load_room_state, room_id)
        assert state_in_result is not None
        assert state_in_result.phase == "result"
        assert len(state_in_result.players) == 2
        p2_in_result = next(p for p in state_in_result.players if p.id == joiner_pid)
        assert p2_in_result.connectionStatus == "disconnected"

        # ホストが「ゲーム終了（ロビーへ戻る）」を実行
        lobby_res = host_client.post(f"/api/rooms/{room_id}/lobby")
        assert lobby_res.status_code == 200
        lobby_gs = lobby_res.json()["gameState"]
        assert lobby_gs["phase"] == "setup"

        # ロビーに戻った時点で、切断していたプレイヤーが除外されていること
        assert len(lobby_gs["players"]) == 1
        assert lobby_gs["players"][0]["id"] == host_pid

        # DB上の状態も確認
        state_in_lobby = base.portal.call(dao.load_room_state, room_id)
        assert state_in_lobby is not None
        assert state_in_lobby.phase == "setup"
        assert len(state_in_lobby.players) == 1
        assert state_in_lobby.players[0].id == host_pid

        # 参加者1人なのでゲーム開始できない
        start_res2 = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res2.status_code == 400
        assert "参加者が2人以上必要です" in start_res2.json()["detail"]

        # 切断していた参加者が再接続
        reconnect_res = joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": ""})
        assert reconnect_res.status_code == 200
        reconnect_gs = reconnect_res.json()["gameState"]
        assert len(reconnect_gs["players"]) == 2


def test_input_word_check_setting_and_invalid_word_action():
    """inputWordCheck設定の反映と、無効単語送信時のバックエンドでのスキップ・失格判定テスト"""
    settings = Settings(cardSize=3, invalidAction="skip", inputWordCheck=False)
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post("/api/rooms", json={"settings": settings.model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]
        assert res.json()["gameState"]["settings"]["inputWordCheck"] is False

        # 参加
        h_join = host_client.post(f"/api/rooms/{room_id}/join", json={"name": "Host"})
        host_pid = h_join.json()["playerId"]
        j_join = joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "Joiner"})
        joiner_pid = j_join.json()["playerId"]

        # ゲーム開始
        start_res = host_client.post(f"/api/rooms/{room_id}/start")
        assert start_res.status_code == 200
        state = start_res.json()["gameState"]
        assert state["phase"] == "playing"

        current_pid = state["currentPlayerId"]
        current_client = host_client if current_pid == host_pid else joiner_client
        other_pid = joiner_pid if current_pid == host_pid else host_pid

        # 不正な文字種（漢字など）は400で弾かれ、手番は変わらない
        act_invalid_chars = current_client.post(
            f"/api/rooms/{room_id}/action",
            json={"type": "word", "word": "漢字"},
        )
        assert act_invalid_chars.status_code == 400

        # 空文字も400/422で弾かれる
        act_empty = current_client.post(
            f"/api/rooms/{room_id}/action",
            json={"type": "word", "word": ""},
        )
        assert act_empty.status_code in (400, 422)

        # ゲームルール上無効な単語（「ん」で終わる）を送信 -> ターンスキップが適用され手番が進む
        act_invalid_rule = current_client.post(
            f"/api/rooms/{room_id}/action",
            json={"type": "word", "word": "きりん"},
        )
        assert act_invalid_rule.status_code == 200
        after_state = act_invalid_rule.json()["gameState"]
        assert after_state["currentPlayerId"] == other_pid


def test_start_game_with_updated_settings():
    """設定反映ボタンを押さずに、ゲーム開始リクエストに新しい設定を渡した場合に設定が反映されてゲームが開始されることのテスト"""
    init_settings = Settings(cardSize=5, timeLimitSeconds=30, minWordLength=None)
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post("/api/rooms", json={"settings": init_settings.model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        # 参加
        host_client.post(f"/api/rooms/{room_id}/join", json={"name": "Host"})
        joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "Joiner"})

        # 設定反映APIを呼ばず、start APIに直接変更後の設定を渡す
        new_settings = Settings(cardSize=3, timeLimitSeconds=15, minWordLength=3, maxWordLength=5)
        start_res = host_client.post(
            f"/api/rooms/{room_id}/start",
            json={"settings": new_settings.model_dump()},
        )
        assert start_res.status_code == 200
        state = start_res.json()["gameState"]
        assert state["phase"] == "playing"
        assert state["settings"]["cardSize"] == 3
        assert state["settings"]["timeLimitSeconds"] == 15
        assert state["settings"]["minWordLength"] == 3
        assert state["settings"]["maxWordLength"] == 5

        # プレイヤーのカードサイズも 3x3 になっていること
        for p in state["players"]:
            assert p["card"]["size"] == 3
            assert len(p["card"]["cells"]) == 9


def test_request_id_and_origin_security():
    """Request-IDの付与と不正Originの拒否テスト"""
    with TestClient(app) as client:
        # 正常なリクエストには X-Request-ID が付与される
        res = client.get("/api/health")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers

        # 不正なOriginからの状態変更POSTは403で拒否される
        bad_origin_res = client.post(
            "/api/rooms",
            json={"settings": Settings().model_dump()},
            headers={"Origin": "https://malicious-site.com"},
        )
        assert bad_origin_res.status_code == 403


def test_undo_max_history_limit():
    """undoHistoryが最大5件に制限され無限に肥大化しないことのテスト"""
    settings = Settings(cardSize=3, endCondition="turns", targetTurns=10)
    with TestClient(app) as base:
        host_client, joiner_client = make_clients(base, 2)
        res = host_client.post("/api/rooms", json={"settings": settings.model_dump()})
        room_id = res.json()["roomId"]
        host_client.post(f"/api/rooms/{room_id}/join", json={"name": "P1"})
        joiner_client.post(f"/api/rooms/{room_id}/join", json={"name": "P2"})

        start_res = host_client.post(f"/api/rooms/{room_id}/start")
        state = start_res.json()["gameState"]

        # 6回以上親が手番をスキップ
        for i in range(7):
            current_pid = state["currentPlayerId"]
            act = host_client.post(
                f"/api/rooms/{room_id}/action",
                json={"type": "skip", "subjectId": current_pid},
            )
            assert act.status_code == 200
            state = act.json()["gameState"]

        # undoHistoryが最大5件以内であること（内部状態の検証）
        import asyncio

        from app import dao
        loaded = asyncio.run(dao.load_room_state(room_id))
        assert loaded is not None
        assert len(loaded.undoHistory) <= 5
