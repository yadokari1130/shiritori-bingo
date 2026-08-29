from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import db
from app.limiter import get_client_ip, limiter
from app.main import app
from app.models import Settings


@pytest.fixture(autouse=True)
def reset_db(tmp_path: Path):
    db.DB_PATH = tmp_path / "test.db"
    yield


def _make_clients(base_client: TestClient, count: int = 1):
    """単一のTestClientトランスポートを共有する独立クライアントを生成する。"""
    clients = [
        httpx.Client(
            transport=base_client._transport,
            base_url=str(base_client.base_url),
            follow_redirects=True,
        )
        for _ in range(count)
    ]
    return clients[0] if count == 1 else tuple(clients)


def test_team_count_large_number_validation():
    """teamCountに過大な数値（100万など）や10より大きい値を指定した場合に422バリデーションエラーとなること。"""
    with TestClient(app) as client:
        # 100万の指定
        res = client.post(
            "/api/rooms",
            json={"settings": {"mode": "team", "teamCount": 1000000}},
        )
        assert res.status_code == 422

        # 11の指定
        res = client.post(
            "/api/rooms",
            json={"settings": {"mode": "team", "teamCount": 11}},
        )
        assert res.status_code == 422

        # 1の指定 (2未満)
        res = client.post(
            "/api/rooms",
            json={"settings": {"mode": "team", "teamCount": 1}},
        )
        assert res.status_code == 422


def test_invalid_card_size_and_limits():
    """不正なカードサイズや設定値が422で拒否されること。"""
    with TestClient(app) as client:
        # 偶数カードサイズ
        res = client.post(
            "/api/rooms",
            json={"settings": {"cardSize": 4}},
        )
        assert res.status_code == 422

        # 9超のカードサイズ
        res = client.post(
            "/api/rooms",
            json={"settings": {"cardSize": 11}},
        )
        assert res.status_code == 422

        # 5秒未満の制限時間
        res = client.post(
            "/api/rooms",
            json={"settings": {"timeLimitSeconds": 3}},
        )
        assert res.status_code == 422

        # 100超の目標ターン数
        res = client.post(
            "/api/rooms",
            json={"settings": {"targetTurns": 101}},
        )
        assert res.status_code == 422


def test_target_bingos_dynamic_limit():
    """ビンゴ数がカードサイズに対する上限（2N+2）を超える場合に422エラーとなること。"""
    with TestClient(app) as client:
        # cardSize=3 の場合、最大ビンゴ数は 3*2+2=8
        res = client.post(
            "/api/rooms",
            json={
                "settings": {
                    "cardSize": 3,
                    "endCondition": "bingos",
                    "targetBingos": 9,
                }
            },
        )
        assert res.status_code == 422

        # cardSize=5 の場合、最大ビンゴ数は 5*2+2=12
        res = client.post(
            "/api/rooms",
            json={
                "settings": {
                    "cardSize": 5,
                    "endCondition": "bingos",
                    "targetBingos": 13,
                }
            },
        )
        assert res.status_code == 422

        # 上限ぎりぎりは許可される
        res = client.post(
            "/api/rooms",
            json={
                "settings": {
                    "cardSize": 3,
                    "endCondition": "bingos",
                    "targetBingos": 8,
                }
            },
        )
        assert res.status_code == 200


def test_max_players_limit():
    """1部屋あたりの最大参加人数（20名）に達した状態で参加しようとすると400エラーとなること。"""
    with TestClient(app) as base:
        host_client = _make_clients(base)
        res = host_client.post("/api/rooms", json={"settings": Settings().model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        # 20人参加可能（独立したクライアントインスタンスを使用）
        for i in range(20):
            client = _make_clients(base)
            join_res = client.post(f"/api/rooms/{room_id}/join", json={"name": f"P{i+1}"})
            assert join_res.status_code == 200

        # 21人目の参加は拒否されること
        excess_client = _make_clients(base)
        excess_res = excess_client.post(f"/api/rooms/{room_id}/join", json={"name": "P21"})
        assert excess_res.status_code == 400
        assert "定員" in excess_res.json()["detail"]


def test_max_cpus_limit():
    """CPU追加が上限（10体）で拒否されること。"""
    with TestClient(app) as base:
        client = _make_clients(base)
        res = client.post("/api/rooms", json={"settings": Settings().model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]
        host_join = client.post(f"/api/rooms/{room_id}/join", json={"name": "ホスト"})
        assert host_join.status_code == 200

        # 10体追加
        for _ in range(10):
            cpu_res = client.post(f"/api/rooms/{room_id}/cpu")
            assert cpu_res.status_code == 200

        # 11体目の追加は拒否されること
        excess_res = client.post(f"/api/rooms/{room_id}/cpu")
        assert excess_res.status_code == 400
        assert "上限" in excess_res.json()["detail"]


def test_name_and_word_html_sanitization():
    """プレイヤー名や単語入力に含まれるHTMLタグがサニタイズ（scriptやタグの完全除去）されること。"""
    with TestClient(app) as base:
        client = _make_clients(base)
        res = client.post("/api/rooms", json={"settings": Settings().model_dump()})
        assert res.status_code == 200
        room_id = res.json()["roomId"]

        # XSSペイロードを含む名前で参加
        malicious_name = "<script>alert('xss')</script><b>太郎</b>"
        join_res = client.post(f"/api/rooms/{room_id}/join", json={"name": malicious_name})
        assert join_res.status_code == 200

        # 参加者名一覧を確認 (scriptタグとその内部テキスト、bタグが安全に完全除去されること)
        player_name = join_res.json()["gameState"]["players"][0]["name"]
        assert player_name == "太郎"

        # 名前変更でのサニタイズ (Cookieセッションを保持した同じクライアントインスタンスを使用)
        update_res = client.put(
            f"/api/rooms/{room_id}/name",
            json={"name": "<img src=x onerror=alert(1)>次郎"},
        )
        assert update_res.status_code == 200
        updated_name = update_res.json()["gameState"]["players"][0]["name"]
        assert "<img" not in updated_name
        assert "次郎" in updated_name


def test_security_headers_present():
    """レスポンスにセキュリティヘッダーが付与されていること。"""
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("x-frame-options") == "DENY"
        assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_rate_limiting_enforcement():
    """レートリミットが有効な場合、短時間の過剰リクエストで429が返ること。"""
    limiter.enabled = True
    try:
        with TestClient(app) as client:
            # 部屋作成の制限は 10/minute
            status_codes = []
            for _ in range(15):
                res = client.post("/api/rooms", json={"settings": Settings().model_dump()})
                status_codes.append(res.status_code)

            assert 429 in status_codes
    finally:
        limiter.enabled = False


def test_get_client_ip_resolution():
    """get_client_ip が CF-Connecting-IP を優先し、偽装可能な X-Forwarded-For は無視して client.host にフォールバックすること。"""
    # 1. CF-Connecting-IP が最優先で取得されること
    req_cf = Request(
        scope={
            "type": "http",
            "headers": [
                (b"cf-connecting-ip", b"203.0.113.195"),
                (b"x-forwarded-for", b"198.51.100.1, 198.51.100.2"),
            ],
            "client": ("192.0.2.1", 12345),
        }
    )
    assert get_client_ip(req_cf) == "203.0.113.195"

    # 2. X-Forwarded-For はクライアントが偽装可能なため無視し、client.host が使われること
    req_xff = Request(
        scope={
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"198.51.100.1, 198.51.100.2"),
            ],
            "client": ("192.0.2.1", 12345),
        }
    )
    assert get_client_ip(req_xff) == "192.0.2.1"

    # 3. ヘッダーがない場合は直接接続の client.host が使われること
    req_direct = Request(
        scope={
            "type": "http",
            "headers": [],
            "client": ("192.0.2.1", 12345),
        }
    )
    assert get_client_ip(req_direct) == "192.0.2.1"


def test_rate_limiting_with_cf_connecting_ip():
    """CF-Connecting-IP ヘッダーごとにレートリミット枠が独立して管理されること。"""
    limiter.enabled = True
    try:
        with TestClient(app) as client:
            # IP A からは10回リクエストを送信 (制限内)
            for _ in range(10):
                res = client.post(
                    "/api/rooms",
                    json={"settings": Settings().model_dump()},
                    headers={"CF-Connecting-IP": "198.51.100.10"},
                )
                assert res.status_code == 200

            # IP A からの11回目は 429
            res_a = client.post(
                "/api/rooms",
                json={"settings": Settings().model_dump()},
                headers={"CF-Connecting-IP": "198.51.100.10"},
            )
            assert res_a.status_code == 429

            # 別の IP B からのリクエストは影響を受けず成功すること
            res_b = client.post(
                "/api/rooms",
                json={"settings": Settings().model_dump()},
                headers={"CF-Connecting-IP": "198.51.100.20"},
            )
            assert res_b.status_code == 200
    finally:
        limiter.enabled = False

