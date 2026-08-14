from __future__ import annotations

import random
import secrets

from app.models import (
    BingoCard,
    Cell,
    GameResult,
    GameState,
    Player,
    PlayerResult,
    Ranking,
    ResultSnapshot,
    Settings,
    Team,
    TeamResult,
    UndoSnapshot,
    WordEntry,
)

# 清音候補
BASE_CHARS = list(
    "あいうえお"
    "かきくけこ"
    "さしすせそ"
    "たちつてと"
    "なにぬねの"
    "はひふへほ"
    "まみむめも"
    "やゆよ"
    "らりるれろ"
    "わ"
)

OPTION_CHARS = {
    "yoon": list("ゃゅょ"),
    "sokuon": list("っ"),
    "prolonged": list("ー"),
    "smallA": list("ぁぃぅぇぉ"),
    "dakuten": list("がぎぐげござじずぜぞだぢづでどばびぶべぼ"),
    "handakuten": list("ぱぴぷぺぽ"),
}

YOON_MAP = {"ゃ": "や", "ゅ": "ゆ", "ょ": "よ"}
SMALL_A_MAP = {"ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お"}

# 濁点・半濁点グループ
_DAKUTEN_GROUPS: list[set[str]] = [
    {"か", "が"},
    {"き", "ぎ"},
    {"く", "ぐ"},
    {"け", "げ"},
    {"こ", "ご"},
    {"さ", "ざ"},
    {"し", "じ"},
    {"す", "ず"},
    {"せ", "ぜ"},
    {"そ", "ぞ"},
    {"た", "だ"},
    {"ち", "ぢ"},
    {"つ", "づ"},
    {"て", "で"},
    {"と", "ど"},
    {"は", "ば", "ぱ"},
    {"ひ", "び", "ぴ"},
    {"ふ", "ぶ", "ぷ"},
    {"へ", "べ", "ぺ"},
    {"ほ", "ぼ", "ぽ"},
    {"う", "ゔ"},
]
DAKUTEN_MAP: dict[str, set[str]] = {}
for group in _DAKUTEN_GROUPS:
    for ch in group:
        DAKUTEN_MAP[ch] = group

HIRAGANA_SET = set(
    "あいうえお"
    "かきくけこ"
    "さしすせそ"
    "たちつてと"
    "なにぬねの"
    "はひふへほ"
    "まみむめも"
    "やゆよ"
    "らりるれろ"
    "わをん"
    "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ"
    "ぁぃぅぇぉゃゅょっ"
    "ゐゑゔ"
    "ー"
)


def get_candidate_chars(settings: Settings) -> list[str]:
    """設定に基づいてカード文字候補を返す。"""
    chars = BASE_CHARS.copy()
    opts = settings.cardOptions
    if opts.yoon:
        chars.extend(OPTION_CHARS["yoon"])
    if opts.sokuon:
        chars.extend(OPTION_CHARS["sokuon"])
    if opts.prolonged:
        chars.extend(OPTION_CHARS["prolonged"])
    if opts.smallA:
        chars.extend(OPTION_CHARS["smallA"])
    if opts.dakuten:
        chars.extend(OPTION_CHARS["dakuten"])
    if opts.handakuten:
        chars.extend(OPTION_CHARS["handakuten"])
    return chars


def max_card_size(candidates: list[str]) -> int:
    """候補文字数から生成可能な最大の奇数サイズを返す。"""
    m = len(candidates)
    n = int(m ** 0.5)
    if n % 2 == 0:
        n -= 1
    while n >= 3 and n * n > m:
        n -= 2
    return n if n >= 3 else 0


def _system_random() -> random.SystemRandom:
    """暗号学的に安全な乱数生成器を返す。"""
    return random.SystemRandom()


def pick_free_char(rng: random.Random | None = None) -> str:
    """清音候補からフリーマス文字を1文字選ぶ。"""
    if rng is None:
        return secrets.choice(BASE_CHARS)
    return rng.choice(BASE_CHARS)


def generate_card(
    size: int,
    candidates: list[str],
    free_char: str,
    rng: random.Random | None = None,
) -> BingoCard:
    """N×Nのビンゴカードを生成する。"""
    if len(candidates) < size * size:
        raise ValueError("候補文字数が不足しています")
    pool = [c for c in candidates if c != free_char]
    needed = size * size - 1
    if len(pool) < needed:
        raise ValueError("フリーマス文字を除いた候補が不足しています")
    chosen = _system_random().sample(pool, needed) if rng is None else rng.sample(pool, needed)
    center = size // 2
    cells: list[Cell] = []
    idx = 0
    for row in range(size):
        for col in range(size):
            if row == center and col == center:
                cells.append(
                    Cell(
                        index=row * size + col,
                        row=row,
                        column=col,
                        char=free_char,
                        isFree=True,
                        isOpen=True,
                    )
                )
            else:
                cells.append(
                    Cell(
                        index=row * size + col,
                        row=row,
                        column=col,
                        char=chosen[idx],
                        isFree=False,
                        isOpen=False,
                    )
                )
                idx += 1
    return BingoCard(size=size, cells=cells, freeChar=free_char)


def line_definitions(size: int) -> list[tuple[str, list[int]]]:
    """ビンゴ対象列の識別子とセルインデックス一覧を返す。"""
    lines: list[tuple[str, list[int]]] = []
    # 横
    for row in range(size):
        lines.append((f"r{row}", [row * size + col for col in range(size)]))
    # 縦
    for col in range(size):
        lines.append((f"c{col}", [row * size + col for row in range(size)]))
    # 斜め
    lines.append(("d1", [i * size + i for i in range(size)]))
    lines.append(("d2", [i * size + (size - 1 - i) for i in range(size)]))
    return lines


def compute_bingo_lines(card: BingoCard) -> list[str]:
    """カードの成立済みビンゴ列IDを返す。"""
    open_indexes = {cell.index for cell in card.cells if cell.isOpen}
    return [
        line_id
        for line_id, indexes in line_definitions(card.size)
        if set(indexes).issubset(open_indexes)
    ]


def count_open_cells(card: BingoCard) -> int:
    """カードの開放済みマス数を返す。"""
    return sum(1 for cell in card.cells if cell.isOpen)


def normalize_tail(word: str) -> tuple[str, bool]:
    """単語の語尾を正規化して次の開始文字を返す。無効なら ("", False)。"""
    if not word:
        return ("", False)
    chars = list(word)
    i = len(chars) - 1
    # 末尾の伸ばし棒をスキップ
    while i >= 0 and chars[i] == "ー":
        i -= 1
    if i < 0:
        return ("", False)

    ch = chars[i]
    if ch in YOON_MAP:
        if i == 0:
            return ("", False)
        return (YOON_MAP[ch], True)
    if ch == "っ":
        if i == 0:
            return ("", False)
        return ("つ", True)
    if ch in SMALL_A_MAP:
        if i == 0:
            return ("", False)
        return (SMALL_A_MAP[ch], True)
    if ch == "ん":
        return ("ん", False)
    return (ch, True)


def is_connected(start_char: str, first_char: str) -> bool:
    """しりとり接続が成立するかを判定する。"""
    if start_char == first_char:
        return True
    group = DAKUTEN_MAP.get(start_char)
    return bool(group and first_char in group)


def is_valid_word_input(word: str) -> bool:
    """単語が空でなく、ひらがなと伸ばし棒のみで構成されているか。"""
    if not word:
        return False
    return all(ch in HIRAGANA_SET for ch in word)


def is_valid_word_length(word: str, settings: Settings) -> bool:
    """設定された単語の文字数制限を満たすか判定する。"""
    length = len(word)
    if settings.minWordLength is not None and length < settings.minWordLength:
        return False
    return settings.maxWordLength is None or length <= settings.maxWordLength


def get_word_invalid_reason(state: GameState, word: str) -> str | None:
    """ゲームルール上の無効理由を固定文で返す。"""
    if not is_valid_word_length(word, state.settings):
        return "設定された文字数の範囲外です。"
    if word in state.usedWords:
        return "この単語はすでに使われています。"
    if not state.wordHistory:
        if not is_connected(state.freeChar, word[0]):
            return "前の単語の最後の文字から始まっていません。"
    else:
        last_word = state.wordHistory[-1].word
        tail, valid = normalize_tail(last_word)
        if not valid or not is_connected(tail, word[0]):
            return "前の単語の最後の文字から始まっていません。"
    _, valid = normalize_tail(word)
    if not valid:
        return "「ん」で終わる単語は使えません。"
    return None


def _current_subject_id(state: GameState) -> str | None:
    if state.settings.mode == "individual":
        return state.currentPlayerId
    return state.currentTeamId


def _set_current_subject(state: GameState, subject_id: str | None) -> None:
    if state.settings.mode == "individual":
        state.currentPlayerId = subject_id
        state.currentTeamId = None
    else:
        state.currentTeamId = subject_id
        state.currentPlayerId = None


def _subject_card(state: GameState, subject_id: str) -> BingoCard | None:
    if state.settings.mode == "individual":
        player = next((p for p in state.players if p.id == subject_id), None)
        return player.card if player else None
    team = next((t for t in state.teams if t.id == subject_id), None)
    return team.card if team else None


def _set_subject_bingo(state: GameState, subject_id: str, line_ids: list[str]) -> None:
    if state.settings.mode == "individual":
        for player in state.players:
            if player.id == subject_id:
                player.bingoLineIds = line_ids
                break
    else:
        for team in state.teams:
            if team.id == subject_id:
                team.bingoLineIds = line_ids
                break


def _set_subject_opened(state: GameState, subject_id: str, count: int) -> None:
    if state.settings.mode == "individual":
        for player in state.players:
            if player.id == subject_id:
                player.openedCellCount = count
                break
    else:
        for team in state.teams:
            if team.id == subject_id:
                team.openedCellCount = count
                break


def _subject_status(
    state: GameState, subject_id: str
) -> str | None:
    if state.settings.mode == "individual":
        player = next((p for p in state.players if p.id == subject_id), None)
        return player.status if player else None
    team = next((t for t in state.teams if t.id == subject_id), None)
    return team.status if team else None


def _set_subject_status(state: GameState, subject_id: str, status: str) -> None:
    if state.settings.mode == "individual":
        for player in state.players:
            if player.id == subject_id:
                player.status = status  # type: ignore[assignment]
                break
    else:
        for team in state.teams:
            if team.id == subject_id:
                team.status = status  # type: ignore[assignment]
                break


def _active_subject_ids(state: GameState) -> list[str]:
    active_ids: set[str]
    if state.settings.mode == "individual":
        active_ids = {p.id for p in state.players if p.status == "active"}
    else:
        active_ids = {t.id for t in state.teams if t.status == "active"}
    # ゲーム開始時に決めた固定順を維持し、失格した対象だけを除外する。
    return [subject_id for subject_id in state.playOrder if subject_id in active_ids]


def _subject_bingo_count(state: GameState, subject_id: str) -> int:
    card = _subject_card(state, subject_id)
    if card is None:
        return 0
    return len(compute_bingo_lines(card))


def _subject_opened_count(state: GameState, subject_id: str) -> int:
    card = _subject_card(state, subject_id)
    if card is None:
        return 0
    return count_open_cells(card)


def _apply_word_openings(state: GameState, word: str) -> list[str]:
    """全カードの一致マスを開放し、開放文字一覧（重複除く）を返す。"""
    opened_chars = list(dict.fromkeys(word))
    subject_ids = [p.id for p in state.players] + [t.id for t in state.teams]
    for subject_id in subject_ids:
        card = _subject_card(state, subject_id)
        if card is None:
            continue
        changed = False
        for ch in opened_chars:
            for cell in card.cells:
                if cell.char == ch and not cell.isOpen:
                    cell.isOpen = True
                    changed = True
                    break
        if changed:
            _set_subject_bingo(state, subject_id, compute_bingo_lines(card))
            _set_subject_opened(state, subject_id, count_open_cells(card))
    return opened_chars


def _start_turn_timer(state: GameState, now_ms: int) -> None:
    """現在の手番の制限時間を設定する。"""
    base_ms = state.settings.timeLimitSeconds * 1000
    is_first_turn = state.round == 1 and state.orderIndex == 0
    limit_ms = base_ms + (state.settings.extraTimeSeconds * 1000 if is_first_turn else 0)
    state.currentTurnTimeLimitMs = limit_ms
    state.remainingTimeMs = limit_ms
    state.turnStartedAt = now_ms


def _advance_turn(state: GameState, now_ms: int) -> None:
    """現在手番を消化し、次の手番または次のターンへ進める。"""
    state.orderIndex += 1
    if state.orderIndex >= len(state.roundRoster):
        state.orderIndex = 0
        state.round += 1
        state.roundRoster = _active_subject_ids(state)

    if not state.roundRoster:
        _set_current_subject(state, None)
        return

    next_subject = state.roundRoster[state.orderIndex]
    _set_current_subject(state, next_subject)
    state.currentTurnInputPlayerId = None
    _start_turn_timer(state, now_ms)


def _check_end_conditions(state: GameState) -> GameResult | None:
    """終了条件を判定し、終了時は GameResult を返す。"""
    settings = state.settings
    active_ids = _active_subject_ids(state)

    # 全員失格は即時終了
    if not active_ids:
        return _build_result(state, "all_disqualified", state.round)

    # ターン終了時の判定（roundRoster を消化して次のターンに進んだ後）
    if state.orderIndex == 0 and state.round > 1:
        if settings.endCondition == "turns":
            if state.round > settings.targetTurns:
                return _build_result(state, "turns", settings.targetTurns)
        elif settings.endCondition == "bingos":
            achievers = [
                sid for sid in active_ids if _subject_bingo_count(state, sid) >= settings.targetBingos
            ]
            if achievers:
                result = _build_result(state, "bingos", state.round - 1)
                if state.settings.mode == "individual":
                    result.achieverPlayerIds = achievers
                else:
                    result.achieverTeamIds = achievers
                return result
    return None


def _build_rankings(state: GameState) -> list[Ranking]:
    """Standard Competition Ranking（1224方式）で順位を計算する。"""
    rankings: list[Ranking] = []
    if state.settings.mode == "individual":
        active = [p for p in state.players if p.status == "active"]
        active.sort(
            key=lambda p: (
                -(len(p.bingoLineIds or [])),
                -(p.openedCellCount or 0),
            )
        )
        prev_score: tuple[int, int] | None = None
        prev_rank = 1
        for i, player in enumerate(active):
            score = (len(player.bingoLineIds or []), player.openedCellCount or 0)
            if score == prev_score:
                rank = prev_rank
            else:
                rank = i + 1
                prev_rank = rank
            prev_score = score
            rankings.append(
                Ranking(
                    rank=rank,
                    subjectType="player",
                    subjectId=player.id,
                    bingoCount=score[0],
                    openedCellCount=score[1],
                    status="active",
                )
            )
        for player in state.players:
            if player.status == "disqualified":
                rankings.append(
                    Ranking(
                        rank=None,
                        subjectType="player",
                        subjectId=player.id,
                        bingoCount=len(player.bingoLineIds or []),
                        openedCellCount=player.openedCellCount or 0,
                        status="disqualified",
                    )
                )
    else:
        active = [t for t in state.teams if t.status == "active"]
        active.sort(
            key=lambda t: (
                -(len(t.bingoLineIds)),
                -(t.openedCellCount),
            )
        )
        prev_score: tuple[int, int] | None = None
        prev_rank = 1
        for i, team in enumerate(active):
            score = (len(team.bingoLineIds), team.openedCellCount)
            if score == prev_score:
                rank = prev_rank
            else:
                rank = i + 1
                prev_rank = rank
            prev_score = score
            rankings.append(
                Ranking(
                    rank=rank,
                    subjectType="team",
                    subjectId=team.id,
                    bingoCount=score[0],
                    openedCellCount=score[1],
                    status="active",
                )
            )
        for team in state.teams:
            if team.status == "disqualified":
                rankings.append(
                    Ranking(
                        rank=None,
                        subjectType="team",
                        subjectId=team.id,
                        bingoCount=len(team.bingoLineIds),
                        openedCellCount=team.openedCellCount,
                        status="disqualified",
                    )
                )
    return rankings


def _build_result_snapshot(state: GameState) -> ResultSnapshot:
    player_results: list[PlayerResult] = []
    for player in state.players:
        player_results.append(
            PlayerResult(
                playerId=player.id,
                name=player.name,
                teamId=player.teamId,
                status=player.status,
                card=player.card,
                bingoLineIds=player.bingoLineIds,
                openedCellCount=player.openedCellCount,
                connectionStatus=player.connectionStatus,
                isCpu=player.isCpu,
            )
        )
    team_results: list[TeamResult] = []
    for team in state.teams:
        team_results.append(
            TeamResult(
                teamId=team.id,
                memberPlayerIds=team.memberPlayerIds,
                status=team.status,
                card=team.card,  # type: ignore[arg-type]
                bingoLineIds=team.bingoLineIds,
                openedCellCount=team.openedCellCount,
            )
        )
    return ResultSnapshot(
        players=player_results,
        teams=team_results,
        wordHistory=state.wordHistory,
        freeChar=state.freeChar,
        settings=state.settings,
    )


def _build_result(
    state: GameState,
    reason: str,
    end_round: int,
) -> GameResult:
    rankings = _build_rankings(state)
    snapshot = _build_result_snapshot(state)
    return GameResult(
        reason=reason,  # type: ignore[arg-type]
        endRound=end_round,
        achieverPlayerIds=[],
        achieverTeamIds=[],
        rankings=rankings,
        snapshot=snapshot,
    )


MAX_UNDO_HISTORY = 5


def push_undo_snapshot(state: GameState) -> UndoSnapshot:
    """現在の状態をundoスナップショットとして積む（最大MAX_UNDO_HISTORY件保持）。"""
    snapshot_state = state.model_copy(deep=True)
    snapshot_state.undoHistory = []
    snapshot = UndoSnapshot(
        gameStateBeforeAction=snapshot_state,
        restoredTurnTimeLimitMs=state.currentTurnTimeLimitMs,
    )
    state.undoHistory.append(snapshot)
    if len(state.undoHistory) > MAX_UNDO_HISTORY:
        state.undoHistory = state.undoHistory[-MAX_UNDO_HISTORY:]
    return snapshot


def start_game(state: GameState, now_ms: int) -> GameState:
    """ロビーから対戦状態へ移行する。"""
    settings = state.settings
    candidates = get_candidate_chars(settings)
    if settings.cardSize > max_card_size(candidates):
        raise ValueError("カードサイズが文字候補数から算出した上限を超えています")

    # 参加者/チームの状態をリセット
    for player in state.players:
        player.status = "active"
        player.card = None
        player.bingoLineIds = []
        player.openedCellCount = None
    for team in state.teams:
        team.status = "active"
        team.card = None
        team.bingoLineIds = []
        team.openedCellCount = 0
        team.memberPlayerIds = [p.id for p in state.players if p.teamId == team.id]

    free_char = pick_free_char()
    state.freeChar = free_char

    if settings.mode == "individual":
        active_players = [p for p in state.players if p.status == "active"]
        _system_random().shuffle(active_players)
        state.playOrder = [p.id for p in active_players]
        for player in active_players:
            card = generate_card(settings.cardSize, candidates, free_char)
            player.card = card
            player.bingoLineIds = compute_bingo_lines(card)
            player.openedCellCount = count_open_cells(card)
    else:
        active_teams = [t for t in state.teams if t.status == "active"]
        _system_random().shuffle(active_teams)
        state.playOrder = [t.id for t in active_teams]
        for team in active_teams:
            team.memberPlayerIds = [p.id for p in state.players if p.teamId == team.id]
            card = generate_card(settings.cardSize, candidates, free_char)
            team.card = card
            team.bingoLineIds = compute_bingo_lines(card)
            team.openedCellCount = count_open_cells(card)

    state.phase = "playing"
    state.round = 1
    state.orderIndex = 0
    state.roundRoster = state.playOrder.copy()
    state.requiredStartChar = free_char
    state.usedWords = []
    state.wordHistory = []
    state.undoHistory = []
    state.result = None

    first_subject = state.roundRoster[0]
    _set_current_subject(state, first_subject)
    state.currentTurnInputPlayerId = None
    _start_turn_timer(state, now_ms)
    return state


def _apply_invalid_action(state: GameState, now_ms: int) -> GameState:
    """無効入力に対してスキップまたは失格を適用する。"""
    subject_id = _current_subject_id(state)
    if subject_id is None:
        return state
    if state.settings.invalidAction == "disqualify":
        _set_subject_status(state, subject_id, "disqualified")
        active = _active_subject_ids(state)
        if not active:
            state.result = _build_result(state, "all_disqualified", state.round)
            state.phase = "result"
            _set_current_subject(state, None)
            return state
    _advance_turn(state, now_ms)
    if state.phase != "result":
        result = _check_end_conditions(state)
        if result:
            state.result = result
            state.phase = "result"
            _set_current_subject(state, None)
    return state


def process_word(state: GameState, player_id: str, word: str, now_ms: int) -> GameState:
    """単語確定処理を行う。無効入力の場合はスキップ/失格を適用する。"""
    if state.phase != "playing":
        raise ValueError("対戦中以外は単語を確定できません")
    if not is_valid_word_input(word):
        raise ValueError("単語はひらがなと伸ばし棒のみで入力してください")

    subject_id = _current_subject_id(state)
    if subject_id is None:
        raise ValueError("現在の手番がありません")

    # チーム戦では現在チームのメンバーであれば入力可能
    if state.settings.mode == "team":
        team = next((t for t in state.teams if t.id == subject_id), None)
        if team is None or player_id not in team.memberPlayerIds:
            raise ValueError("現在の手番のチームメンバーではありません")
    else:
        if player_id != subject_id:
            raise ValueError("現在の手番ではありません")

    push_undo_snapshot(state)

    # 無効入力判定
    reason = get_word_invalid_reason(state, word)
    if reason is not None:
        return _apply_invalid_action(state, now_ms)

    tail, _ = normalize_tail(word)

    # 有効単語
    opened_chars = _apply_word_openings(state, word)
    sequence = len(state.wordHistory) + 1
    state.wordHistory.append(
        WordEntry(
            word=word,
            playerId=player_id,
            round=state.round,
            sequence=sequence,
            openedChars=opened_chars,
        )
    )
    state.usedWords.append(word)
    state.requiredStartChar = tail
    state.currentTurnInputPlayerId = player_id

    _advance_turn(state, now_ms)
    result = _check_end_conditions(state)
    if result:
        state.result = result
        state.phase = "result"
        _set_current_subject(state, None)
    return state


def process_skip(state: GameState, now_ms: int) -> GameState:
    """現在手番をスキップする。"""
    if state.phase != "playing":
        raise ValueError("対戦中以外はスキップできません")
    push_undo_snapshot(state)
    _advance_turn(state, now_ms)
    result = _check_end_conditions(state)
    if result:
        state.result = result
        state.phase = "result"
        _set_current_subject(state, None)
    return state


def process_disqualify(state: GameState, now_ms: int) -> GameState:
    """現在手番を失格にする。"""
    if state.phase != "playing":
        raise ValueError("対戦中以外は失格処理できません")
    subject_id = _current_subject_id(state)
    if subject_id is None:
        raise ValueError("現在の手番がありません")
    push_undo_snapshot(state)
    _set_subject_status(state, subject_id, "disqualified")
    active = _active_subject_ids(state)
    if not active:
        state.result = _build_result(state, "all_disqualified", state.round)
        state.phase = "result"
        _set_current_subject(state, None)
        return state
    _advance_turn(state, now_ms)
    result = _check_end_conditions(state)
    if result:
        state.result = result
        state.phase = "result"
        _set_current_subject(state, None)
    return state


def undo(state: GameState, now_ms: int) -> GameState:
    """直前の確定操作をundoする。"""
    if state.phase != "playing":
        raise ValueError("対戦中以外はundoできません")
    if not state.undoHistory:
        raise ValueError("undo対象がありません")
    snapshot = state.undoHistory.pop()
    restored = snapshot.gameStateBeforeAction.model_copy(deep=True)
    restored.remainingTimeMs = snapshot.restoredTurnTimeLimitMs
    restored.currentTurnTimeLimitMs = snapshot.restoredTurnTimeLimitMs
    restored.turnStartedAt = now_ms
    return restored


def get_remaining_time_ms(state: GameState, now_ms: int) -> int:
    """現在時刻から残り時間を計算する。"""
    if state.turnStartedAt is None:
        return state.remainingTimeMs
    elapsed = now_ms - state.turnStartedAt
    return max(0, state.currentTurnTimeLimitMs - elapsed)


def randomize_teams(players: list[Player], teams: list[Team]) -> None:
    """未所属の参加者をチーム間の人数差が1以内になるようランダムに配置する。"""
    unassigned = [p for p in players if p.teamId is None]
    _system_random().shuffle(unassigned)
    for player in unassigned:
        teams.sort(key=lambda t: len([p for p in players if p.teamId == t.id]))
        player.teamId = teams[0].id
    # memberPlayerIds は保存時に再計算する
