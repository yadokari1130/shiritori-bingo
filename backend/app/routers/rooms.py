from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import broadcast, cleanup, cpu, dao, db, engine, security
from app.models import (
    ActionRequest,
    ChangeHostRequest,
    ChangeTeamRequest,
    CreateRoomRequest,
    DisqualifyAction,
    GameState,
    JoinRoomRequest,
    KickPlayerRequest,
    NameChangeRequest,
    Player,
    Settings,
    SettingsUpdateRequest,
    SkipAction,
    StartGameRequest,
    Team,
    UndoAction,
    WordAction,
)

router = APIRouter()


async def _get_current_player_id(request: Request) -> str | None:
    """Cookie からプレイヤーIDを特定する。"""
    token = request.cookies.get(security.SESSION_COOKIE_NAME)
    if not token:
        return None
    session = await dao.get_session_by_token_hash(security.hash_token(token))
    if session is None:
        return None
    return session["player_id"]


async def _require_player(request: Request) -> str:
    player_id = await _get_current_player_id(request)
    if player_id is None:
        raise HTTPException(status_code=403, detail="操作権限がありません")
    return player_id


_public_state = broadcast.public_state


async def _elect_new_host_if_needed(state: GameState) -> bool:
    """ホストが不在、CPU、または切断中の場合、接続中の先頭参加者をホストにする。変更があれば True。"""
    current_host = next((p for p in state.players if p.id == state.hostPlayerId), None)
    is_invalid_host = (
        state.hostPlayerId is None
        or current_host is None
        or current_host.isCpu
        or current_host.connectionStatus != "connected"
    )
    if is_invalid_host:
        new_host = cleanup.elect_host(state.players)
        if new_host != state.hostPlayerId:
            state.hostPlayerId = new_host
            return True
    return False


def _is_subject_cpu(state: GameState, subject_id: str | None) -> tuple[bool, str | None]:
    """指定された subject_id (プレイヤーまたはチーム) が CPU かどうかと、入力実行プレイヤーIDを返す。"""
    if not subject_id:
        return False, None
    if state.settings.mode == "individual":
        p = next((p for p in state.players if p.id == subject_id), None)
        if p and p.isCpu:
            return True, p.id
        return False, None
    else:
        team = next((t for t in state.teams if t.id == subject_id), None)
        if not team:
            return False, None
        members = [p for p in state.players if p.id in team.memberPlayerIds]
        if members and all(m.isCpu for m in members):
            return True, members[0].id
        return False, None


def _trigger_cpu_turn_if_needed(room_id: str, state: GameState) -> None:
    """現在手番がCPUの場合、非同期タスクで自動手番を実行する。"""
    if state.phase != "playing":
        return
    current_subject = (
        state.currentPlayerId
        if state.settings.mode == "individual"
        else state.currentTeamId
    )
    is_cpu, _ = _is_subject_cpu(state, current_subject)
    if is_cpu:
        asyncio.create_task(_run_cpu_turn(room_id, state.round, state.orderIndex))


async def _run_cpu_turn(room_id: str, expected_round: int, expected_order_index: int) -> None:
    """CPUの手番を思考ウェイトを挟んで実行する。"""
    await asyncio.sleep(1.0)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None or state.phase != "playing":
            return
        if state.round != expected_round or state.orderIndex != expected_order_index:
            return

        current_subject = (
            state.currentPlayerId
            if state.settings.mode == "individual"
            else state.currentTeamId
        )
        is_cpu, cpu_player_id = _is_subject_cpu(state, current_subject)
        if not is_cpu or cpu_player_id is None or current_subject is None:
            return

        now = dao.now_ms()
        best_word = await asyncio.to_thread(cpu.select_best_word, state, current_subject)
        notice: str | None = None

        if best_word is not None:
            try:
                engine.process_word(state, cpu_player_id, best_word, now)
                opened_count = len(state.wordHistory[-1].openedChars)
                p_name = next((p.name for p in state.players if p.id == cpu_player_id), "CPU")
                notice = f"🤖 {p_name} が「{best_word}」を入力しました（{opened_count}マス開放）。"
            except Exception:
                engine.process_skip(state, now)
                notice = "🤖 手詰まりのためスキップしました。"
        else:
            engine.process_skip(state, now)
            notice = "🤖 出せる単語がないためスキップしました。"

        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state, notice=notice)

        _trigger_cpu_turn_if_needed(room_id, state)



@router.post("/api/rooms")
async def create_room(request: Request, body: CreateRoomRequest):
    room_id = secrets.token_urlsafe(12)
    password_hash = (
        await security.hash_password_async(body.password) if body.password else None
    )
    creator_token = security.generate_session_token()
    creator_token_hash = security.hash_token(creator_token)
    state = await dao.create_room(
        room_id,
        password_hash,
        body.settings,
        creator_token_hash=creator_token_hash,
    )
    url = f"{request.url.scheme}://{request.url.netloc}/game/{room_id}"
    response = JSONResponse(
        status_code=200,
        content={"roomId": room_id, "url": url, "gameState": _public_state(state)},
    )
    security.set_creator_cookie(response, creator_token)
    return response


@router.get("/api/rooms/{room_id}")
async def get_room_info(room_id: str):
    row = await dao.get_room(room_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ルームが存在しません")
    return {
        "roomId": room_id,
        "phase": row["phase"],
        "hasPassword": bool(row["password_hash"]),
    }


@router.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str, request: Request, body: JoinRoomRequest):
    row = await dao.get_room(room_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ルームが存在しません")

    state = await dao.load_room_state(room_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ルームが存在しません")

    token = request.cookies.get(security.SESSION_COOKIE_NAME)
    session = None
    if token:
        session = await dao.get_session_by_token_hash(
            security.hash_token(token)
        )
        if session and session["room_id"] != room_id:
            session = None

    # 作成者Cookieの検証（部屋作成者はパスワード入力不要）
    creator_token = request.cookies.get(security.CREATOR_COOKIE_NAME)
    is_creator = False
    if (
        creator_token
        and row["creator_token_hash"]
        and security.hash_token(creator_token) == row["creator_token_hash"]
    ):
        is_creator = True

    # 有効な再接続Cookieがあれば、名前やパスワードの再入力なしで復帰する。
    if session is None:
        password_hash = row["password_hash"]
        # 作成者本人でない場合のみパスワードを検証
        if not is_creator and password_hash and not await security.verify_password_async(body.password or "", password_hash):
            raise HTTPException(status_code=403, detail="パスワードが違います")
        if not body.name:
            raise HTTPException(status_code=400, detail="名前を入力してください")

    is_host = False

    if session is not None:
        # 再接続
        player_id = session["player_id"]
        player = next((p for p in state.players if p.id == player_id), None)
        if player is None:
            if state.phase != "setup":
                raise HTTPException(
                    status_code=403,
                    detail="ゲーム中のため参加できません" if state.phase == "playing" else "ゲームが終了しているため参加できません",
                )
            db_p = await dao.get_player(player_id)
            if db_p is None:
                raise HTTPException(status_code=403, detail="参加者が見つかりません")
            status = "active" if state.settings.mode == "individual" else None
            valid_team_id = (
                db_p["team_id"]
                if db_p["team_id"] in {t.id for t in state.teams}
                else None
            )
            player = Player(
                id=player_id,
                name=db_p["name"],
                status=status,  # type: ignore[arg-type]
                connectionStatus="connected",
                sortOrder=db_p["sort_order"],
                teamId=valid_team_id,
            )
            state.players.append(player)
            for team in state.teams:
                team.memberPlayerIds = [
                    p.id for p in state.players if p.teamId == team.id
                ]
        else:
            if state.phase == "result" and player_id not in {p.id for p in state.players}:
                raise HTTPException(status_code=403, detail="参加できませんでした。ゲーム開始前のみ参加できます")
            player.connectionStatus = "connected"
            player.disconnectedAt = None

        await dao.set_player_connection_status(player_id, True)
        host_changed = False
        if state.hostPlayerId is None or any(
            p.id == state.hostPlayerId and p.isCpu for p in state.players
        ):
            state.hostPlayerId = player_id
            host_changed = True
        is_host = state.hostPlayerId == player_id
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(
            room_id,
            state,
            notice="親が変更されました。" if host_changed else None,
        )
        response = JSONResponse(
            status_code=200,
            content={
                "gameState": _public_state(state),
                "playerId": player_id,
                "isHost": is_host,
            },
        )
        security.set_session_cookie(response, token)
        return response

    if state.phase == "playing":
        raise HTTPException(status_code=403, detail="ゲーム中のため参加できません")
    if state.phase == "result":
        raise HTTPException(status_code=403, detail="ゲームが終了しているため参加できません")

    # 新規参加
    player_id = dao.generate_uuid()
    sort_order = await dao.get_next_player_sort_order(room_id)
    status = "active" if state.settings.mode == "individual" else None
    player = Player(
        id=player_id,
        name=body.name,
        status=status,  # type: ignore[arg-type]
        connectionStatus="connected",
        sortOrder=sort_order,
    )
    state.players.append(player)
    host_changed = False
    if state.hostPlayerId is None or any(
        p.id == state.hostPlayerId and p.isCpu for p in state.players
    ):
        state.hostPlayerId = player_id
        is_host = True
    elif is_creator:
        state.hostPlayerId = player_id
        is_host = True
        host_changed = True

    await dao.save_room_state(room_id, state)
    session_id = dao.generate_uuid()
    new_token = security.generate_session_token()
    await dao.create_session(
        session_id, room_id, player_id, security.hash_token(new_token)
    )
    await broadcast.broadcast(
        room_id,
        state,
        notice="親が変更されました。" if host_changed else None,
    )
    response = JSONResponse(
        status_code=200,
        content={
            "gameState": _public_state(state),
            "playerId": player_id,
            "isHost": is_host,
        },
    )
    security.set_session_cookie(response, new_token)
    security.clear_creator_cookie(response)
    return response


@router.post("/api/rooms/{room_id}/cpu")
async def add_cpu(room_id: str, request: Request):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけがCPUを追加できます")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="ロビー中のみ追加できます")

        cpu_count = sum(1 for p in state.players if p.isCpu)
        name = f"CPU {cpu_count + 1}"
        cpu_id = dao.generate_uuid()
        sort_order = await dao.get_next_player_sort_order(room_id)
        status = "active" if state.settings.mode == "individual" else None
        new_cpu = Player(
            id=cpu_id,
            name=name,
            status=status,  # type: ignore[arg-type]
            connectionStatus="connected",
            sortOrder=sort_order,
            isCpu=True,
        )
        state.players.append(new_cpu)

        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(
            room_id, state, notice=f"🤖 {name} が追加されました。"
        )
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.get("/api/rooms/{room_id}/assist")
async def get_assist(room_id: str, request: Request):
    state = await dao.load_room_state(room_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ルームが存在しません")
    if state.phase != "playing":
        return JSONResponse(status_code=200, content={"suggestions": []})

    current_subject = (
        state.currentPlayerId
        if state.settings.mode == "individual"
        else state.currentTeamId
    )
    if not current_subject:
        return JSONResponse(status_code=200, content={"suggestions": []})

    suggestions = await asyncio.to_thread(
        cpu.get_assist_suggestions, state, current_subject, count=3
    )
    return JSONResponse(status_code=200, content={"suggestions": suggestions})


@router.put("/api/rooms/{room_id}/name")
async def change_name(room_id: str, request: Request, body: NameChangeRequest):
    if not body.name:
        raise HTTPException(status_code=400, detail="名前を入力してください")
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="名前はロビー中のみ変更できます")
        player = next((p for p in state.players if p.id == player_id), None)
        if player is None:
            raise HTTPException(status_code=403, detail="参加者が見つかりません")
        player.name = body.name
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state)
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/leave")
async def leave_room(room_id: str, request: Request):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.phase not in ("setup", "result"):
            raise HTTPException(
                status_code=403, detail="このフェーズでは退出できません"
            )
        if player_id not in {p.id for p in state.players}:
            raise HTTPException(status_code=403, detail="参加者が見つかりません")

        host_changed = await cleanup_remove_player(room_id, state, player_id)
        response = JSONResponse(status_code=200, content={"gameState": _public_state(state)})
        security.clear_session_cookie(response)
        await broadcast.broadcast(
            room_id,
            state,
            notice="親が変更されました。" if host_changed else None,
        )
        return response


@router.post("/api/rooms/{room_id}/disconnect")
async def disconnect_room(room_id: str, request: Request):
    """タブ閉じ・画面離脱時の即時切断通知。"""
    token = request.cookies.get(security.SESSION_COOKIE_NAME)
    if not token:
        return JSONResponse(status_code=200, content={"success": True})
    session = await dao.get_session_by_token_hash(security.hash_token(token))
    if session is None or session["room_id"] != room_id:
        return JSONResponse(status_code=200, content={"success": True})

    player_id = session["player_id"]
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            return JSONResponse(status_code=200, content={"success": True})

        await dao.update_session_connections(session["id"], -100)
        await dao.set_player_connection_status(player_id, False)

        host_changed = False
        if state.phase == "setup":
            state.players = [p for p in state.players if p.id != player_id]
            for team in state.teams:
                team.memberPlayerIds = [
                    p.id for p in state.players if p.teamId == team.id
                ]
            if state.hostPlayerId == player_id or (
                state.hostPlayerId is not None
                and any(p.id == state.hostPlayerId and p.isCpu for p in state.players)
            ):
                state.hostPlayerId = cleanup.elect_host(state.players)
                host_changed = True
        else:
            player = next((p for p in state.players if p.id == player_id), None)
            if player is not None:
                player.connectionStatus = "disconnected"
                player.disconnectedAt = dao.now_ms()
            if state.hostPlayerId == player_id or (
                state.hostPlayerId is not None
                and any(p.id == state.hostPlayerId and p.isCpu for p in state.players)
            ):
                state.hostPlayerId = cleanup.elect_host(state.players)
                host_changed = True

        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(
            room_id,
            state,
            notice="親が変更されました。" if host_changed else None,
        )

    return JSONResponse(status_code=200, content={"success": True})


@router.delete("/api/rooms/{room_id}")
async def delete_room(room_id: str, request: Request):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけが部屋を解散できます")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="ロビー中のみ解散できます")

        # SSEで参加者全員に解散を通知
        await broadcast.broadcast_event(
            room_id,
            event="dissolved",
            payload={"message": "部屋が解散されました。"},
        )
        await dao.delete_room(room_id)
        broadcast._rooms.pop(room_id, None)

        response = JSONResponse(status_code=200, content={"success": True})
        security.clear_session_cookie(response)
        return response


async def cleanup_remove_player(
    room_id: str, state: GameState, player_id: str
) -> bool:
    """プレイヤー削除と空ルーム処理を行う。ホスト変更があれば True。"""
    before_host = state.hostPlayerId
    state.players = [p for p in state.players if p.id != player_id]
    if state.hostPlayerId == player_id or (
        state.hostPlayerId is not None
        and any(p.id == state.hostPlayerId and p.isCpu for p in state.players)
    ):
        state.hostPlayerId = cleanup.elect_host(state.players)
    for team in state.teams:
        team.memberPlayerIds = [
            p.id for p in state.players if p.teamId == team.id
        ]
    if not state.players:
        await dao.delete_room(room_id)
        broadcast._rooms.pop(room_id, None)
        return before_host != state.hostPlayerId
    await dao.delete_player(player_id)
    await dao.save_room_state(room_id, state)
    return before_host != state.hostPlayerId


async def _apply_settings(
    room_id: str, state: GameState, new_settings: Settings
) -> None:
    """設定値の検証と適用（チーム再作成含む）。"""
    try:
        candidates = engine.get_candidate_chars(new_settings)
        max_size = engine.max_card_size(candidates)
        if new_settings.cardSize > max_size:
            raise ValueError("カードサイズが文字候補数の上限を超えています")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    old_mode = state.settings.mode
    old_team_count = state.settings.teamCount
    state.settings = new_settings

    # モードやチーム数が変わった場合はチームを再作成
    if (
        state.settings.mode == "team"
        and (old_mode != "team" or old_team_count != state.settings.teamCount)
    ):
        await dao.delete_teams(room_id)
        state.teams = []
        for i in range(state.settings.teamCount):
            team_id = dao.generate_uuid()
            await dao.create_team(room_id, team_id, i)
            state.teams.append(Team(id=team_id, sortOrder=i))
        for player in state.players:
            player.teamId = None
    elif state.settings.mode == "individual" and old_mode != "individual":
        await dao.delete_teams(room_id)
        state.teams = []
        for player in state.players:
            player.teamId = None
            player.status = "active"


@router.put("/api/rooms/{room_id}/settings")
async def update_settings(room_id: str, request: Request, body: SettingsUpdateRequest):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけが設定を変更できます")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="設定はロビー中のみ変更できます")

        await _apply_settings(room_id, state, body.settings)
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state)
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/start")
async def start_game(
    room_id: str, request: Request, body: StartGameRequest | None = None
):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけが開始できます")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="ロビー中のみ開始できます")

        if body is not None and body.settings is not None:
            await _apply_settings(room_id, state, body.settings)

        if len(state.players) < 2:
            raise HTTPException(
                status_code=400, detail="参加者が2人以上必要です"
            )
        human_players = [p for p in state.players if not p.isCpu]
        if not human_players:
            raise HTTPException(
                status_code=400, detail="人間プレイヤーが1人以上必要です"
            )
        if state.settings.mode == "team":
            for team in state.teams:
                team.memberPlayerIds = [
                    p.id for p in state.players if p.teamId == team.id
                ]
                if not team.memberPlayerIds:
                    raise HTTPException(
                        status_code=400, detail="所属者がいないチームがあります"
                    )

        try:
            engine.start_game(state, dao.now_ms())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        await dao.delete_undo_snapshots_for_room(room_id)
        await dao.delete_word_history_for_room(room_id)
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state)
        _trigger_cpu_turn_if_needed(room_id, state)
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/lobby")
async def return_to_lobby(room_id: str, request: Request):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけがロビーに戻せます")
        if state.phase != "result":
            raise HTTPException(status_code=403, detail="結果画面からのみ戻れます")

        state.phase = "setup"
        state.freeChar = ""
        state.playOrder = []
        state.roundRoster = []
        state.round = 0
        state.orderIndex = 0
        state.currentPlayerId = None
        state.currentTeamId = None
        state.requiredStartChar = ""
        state.usedWords = []
        state.wordHistory = []
        state.remainingTimeMs = 0
        state.currentTurnTimeLimitMs = 0
        state.currentTurnInputPlayerId = None
        state.turnStartedAt = None
        state.result = None
        state.undoHistory = []

        # 切断中のプレイヤーをロビーから除外する
        state.players = [
            p for p in state.players if p.connectionStatus == "connected"
        ]

        for player in state.players:
            player.card = None
            player.bingoLineIds = [] if state.settings.mode == "individual" else None
            player.openedCellCount = None
            player.status = "active" if state.settings.mode == "individual" else None
        for team in state.teams:
            team.status = "active"
            team.card = None
            team.bingoLineIds = []
            team.openedCellCount = 0
            team.memberPlayerIds = [
                p.id for p in state.players if p.teamId == team.id
            ]

        host_changed = False
        current_host = next((p for p in state.players if p.id == state.hostPlayerId), None)
        if current_host is None or current_host.isCpu:
            new_host = cleanup.elect_host(state.players)
            if new_host != state.hostPlayerId:
                state.hostPlayerId = new_host
                host_changed = True

        await dao.delete_undo_snapshots_for_room(room_id)
        await dao.delete_word_history_for_room(room_id)
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(
            room_id,
            state,
            notice="親が変更されました。" if host_changed else None,
        )
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/host")
async def change_host(room_id: str, request: Request, body: ChangeHostRequest):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけが変更できます")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="ロビー中のみ変更できます")
        target_player = next((p for p in state.players if p.id == body.playerId), None)
        if target_player is None:
            raise HTTPException(status_code=400, detail="対象の参加者が存在しません")
        if target_player.isCpu:
            raise HTTPException(status_code=400, detail="CPUを親に指定することはできません")
        if target_player.connectionStatus != "connected":
            raise HTTPException(status_code=400, detail="切断中の参加者を親に指定することはできません")
        state.hostPlayerId = body.playerId
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(
            room_id, state, notice="親が変更されました。"
        )
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/kick")
async def kick_player(room_id: str, request: Request, body: KickPlayerRequest):
    operator_player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != operator_player_id:
            raise HTTPException(status_code=403, detail="親だけが退出させることができます")
        if state.phase != "setup":
            raise HTTPException(
                status_code=403, detail="ロビー中のみ退出させることができます"
            )
        if body.playerId not in {p.id for p in state.players}:
            raise HTTPException(status_code=400, detail="対象の参加者が存在しません")
        if body.playerId == operator_player_id:
            raise HTTPException(
                status_code=400, detail="自分自身を強制退出させることはできません"
            )

        target_player = next((p for p in state.players if p.id == body.playerId), None)
        target_name = target_player.name if target_player else "参加者"

        await cleanup_remove_player(room_id, state, body.playerId)
        await broadcast.broadcast(
            room_id,
            state,
            notice=f"{target_name} さんが退出させられました。",
        )
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.put("/api/rooms/{room_id}/team")
async def change_team(room_id: str, request: Request, body: ChangeTeamRequest):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="ロビー中のみ変更できます")
        if state.settings.mode != "team":
            raise HTTPException(status_code=400, detail="チーム戦ではありません")
        if body.teamId is not None and body.teamId not in {t.id for t in state.teams}:
            raise HTTPException(status_code=400, detail="チームが存在しません")
        player = next((p for p in state.players if p.id == player_id), None)
        if player is None:
            raise HTTPException(status_code=403, detail="参加者が見つかりません")
        player.teamId = body.teamId
        for team in state.teams:
            team.memberPlayerIds = [
                p.id for p in state.players if p.teamId == team.id
            ]
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state)
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/teams/randomize")
async def randomize_teams(room_id: str, request: Request):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.hostPlayerId != player_id:
            raise HTTPException(status_code=403, detail="親だけが実行できます")
        if state.phase != "setup":
            raise HTTPException(status_code=403, detail="ロビー中のみ実行できます")
        if state.settings.mode != "team":
            raise HTTPException(status_code=400, detail="チーム戦ではありません")
        engine.randomize_teams(state.players, state.teams)
        for team in state.teams:
            team.memberPlayerIds = [
                p.id for p in state.players if p.teamId == team.id
            ]
        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state)
    return JSONResponse(status_code=200, content={"gameState": _public_state(state)})


@router.post("/api/rooms/{room_id}/action")
async def action(room_id: str, request: Request, body: ActionRequest):
    player_id = await _require_player(request)
    async with db._write_lock:
        state = await dao.load_room_state(room_id)
        if state is None:
            raise HTTPException(status_code=404, detail="ルームが存在しません")
        if state.phase != "playing":
            raise HTTPException(status_code=409, detail="対戦中ではありません")

        now = dao.now_ms()
        notice: str | None = None

        if isinstance(body, WordAction):
            if not engine.is_valid_word_input(body.word):
                raise HTTPException(
                    status_code=400, detail="ひらがなと伸ばし棒で入力してください"
                )
            try:
                old_history_len = len(state.wordHistory)
                invalid_reason = engine.get_word_invalid_reason(state, body.word)
                engine.process_word(state, player_id, body.word, now)
                if len(state.wordHistory) > old_history_len:
                    await dao.add_word_history(room_id, state.wordHistory[-1])
                if state.undoHistory:
                    await dao.add_undo_snapshot(
                        room_id, state.undoHistory[-1]
                    )
                if invalid_reason:
                    action_name = (
                        "失格"
                        if state.settings.invalidAction == "disqualify"
                        else "ターンスキップ"
                    )
                    notice = f"{invalid_reason} {action_name}しました。"
                else:
                    opened_count = len(state.wordHistory[-1].openedChars)
                    notice = f"「{body.word}」を受け付けました。{opened_count}マス開放。"
            except ValueError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

        elif isinstance(body, (SkipAction, DisqualifyAction)):
            if state.hostPlayerId != player_id:
                raise HTTPException(
                    status_code=403, detail="親だけが実行できます"
                )
            current_id = (
                state.currentPlayerId
                if state.settings.mode == "individual"
                else state.currentTeamId
            )
            subject_id = body.subjectId
            if subject_id != current_id:
                raise HTTPException(
                    status_code=400, detail="現在手番の対象ではありません"
                )
            try:
                if isinstance(body, SkipAction):
                    engine.process_skip(state, now)
                else:
                    engine.process_disqualify(state, now)
                if state.undoHistory:
                    await dao.add_undo_snapshot(
                        room_id, state.undoHistory[-1]
                    )
                notice = (
                    "手番をスキップしました。"
                    if isinstance(body, SkipAction)
                    else "手番を失格にしました。"
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        elif isinstance(body, UndoAction):
            if state.hostPlayerId != player_id:
                raise HTTPException(
                    status_code=403, detail="親だけが実行できます"
                )
            try:
                state = engine.undo(state, now)
                await dao.pop_undo_snapshot(room_id)
                await dao.sync_word_history(room_id, state.wordHistory)
                notice = "直前の操作を取り消しました。"
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        await dao.save_room_state(room_id, state)
        await broadcast.broadcast(room_id, state, notice=notice)
        _trigger_cpu_turn_if_needed(room_id, state)
    return JSONResponse(
        status_code=200, content={"success": True, "gameState": _public_state(state)}
    )


async def _wait_for_disconnect(request: Request) -> None:
    """クライアントの切断（http.disconnect）を待機する。"""
    while True:
        try:
            message = await request._receive()
            if message.get("type") == "http.disconnect":
                return
        except Exception:
            return


@router.get("/api/rooms/{room_id}/events")
async def events(room_id: str, request: Request):
    token = request.cookies.get(security.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=403, detail="セッションがありません")
    session = await dao.get_session_by_token_hash(security.hash_token(token))
    if session is None or session["room_id"] != room_id:
        raise HTTPException(status_code=403, detail="セッションが無効です")

    player_id = session["player_id"]

    async def event_generator():
        queue = broadcast.subscribe(room_id)
        disconnect_task = asyncio.create_task(_wait_for_disconnect(request))
        try:
            async with db._write_lock:
                state = await dao.load_room_state(room_id)
                if state is None:
                    yield broadcast.format_sse(
                        {
                            "event": "error",
                            "timestamp": dao.now_ms(),
                            "message": "ルームが存在しません",
                        }
                    )
                    return
                player = next(
                    (p for p in state.players if p.id == player_id), None
                )
                if player is not None:
                    player.connectionStatus = "connected"
                    player.disconnectedAt = None
                    await dao.set_player_connection_status(player_id, True)
                elif state.phase == "setup":
                    db_p = await dao.get_player(player_id)
                    if db_p is not None:
                        status = "active" if state.settings.mode == "individual" else None
                        valid_team_id = (
                            db_p["team_id"]
                            if db_p["team_id"] in {t.id for t in state.teams}
                            else None
                        )
                        player = Player(
                            id=player_id,
                            name=db_p["name"],
                            status=status,  # type: ignore[arg-type]
                            connectionStatus="connected",
                            sortOrder=db_p["sort_order"],
                            teamId=valid_team_id,
                        )
                        state.players.append(player)
                        for team in state.teams:
                            team.memberPlayerIds = [
                                p.id for p in state.players if p.teamId == team.id
                            ]
                        await dao.set_player_connection_status(player_id, True)
                await dao.update_session_connections(session["id"], 1)
                state.remainingTimeMs = engine.get_remaining_time_ms(
                    state, dao.now_ms()
                )
                await dao.save_room_state(room_id, state)
                host_changed = await _elect_new_host_if_needed(state)
                await dao.save_room_state(room_id, state)
                await broadcast.broadcast(
                    room_id,
                    state,
                    event="initial",
                    notice="親が変更されました。" if host_changed else None,
                )

            while not disconnect_task.done():
                get_task = asyncio.create_task(queue.get())
                done, pending = await asyncio.wait(
                    [get_task, disconnect_task],
                    timeout=3.0,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if disconnect_task in done:
                    get_task.cancel()
                    break

                now_touch = dao.now_ms()
                await dao.touch_session(session["id"])

                if get_task in done:
                    payload = get_task.result()
                    yield broadcast.format_sse(payload)
                else:
                    get_task.cancel()
                    yield broadcast.format_sse(
                        {
                            "event": "ping",
                            "timestamp": now_touch,
                        }
                    )
        finally:
            disconnect_task.cancel()
            broadcast.unsubscribe(room_id, queue)
            async with db._write_lock:
                new_count = await dao.update_session_connections(session["id"], -1)
                if new_count == 0:
                    await dao.set_player_connection_status(player_id, False)
                    state = await dao.load_room_state(room_id)
                    if state is not None:
                        host_changed = False
                        if state.phase == "setup":
                            state.players = [
                                p for p in state.players if p.id != player_id
                            ]
                            for team in state.teams:
                                team.memberPlayerIds = [
                                    p.id
                                    for p in state.players
                                    if p.teamId == team.id
                                ]
                            if state.hostPlayerId == player_id or (
                                state.hostPlayerId is not None
                                and any(p.id == state.hostPlayerId and p.isCpu for p in state.players)
                            ):
                                state.hostPlayerId = cleanup.elect_host(state.players)
                                host_changed = True
                        else:
                            player = next(
                                (p for p in state.players if p.id == player_id), None
                            )
                            if player is not None:
                                player.connectionStatus = "disconnected"
                                player.disconnectedAt = dao.now_ms()
                            if state.hostPlayerId == player_id or (
                                state.hostPlayerId is not None
                                and any(p.id == state.hostPlayerId and p.isCpu for p in state.players)
                            ):
                                state.hostPlayerId = cleanup.elect_host(state.players)
                                host_changed = True
                        await dao.save_room_state(room_id, state)
                        await broadcast.broadcast(
                            room_id,
                            state,
                            notice="親が変更されました。" if host_changed else None,
                        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
