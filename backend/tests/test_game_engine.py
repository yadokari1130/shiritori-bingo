import pytest

from app import engine
from app.dao import now_ms
from app.models import CardOptions, GameState, Player, Settings


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("しりとり", "り"),
        ("きしゃ", "や"),
        ("ぎたー", "た"),
        ("らーー", "ら"),
        ("きょーー", "よ"),
        ("きゃっ", "つ"),
        ("まぁ", "あ"),
    ],
)
def test_normalize_tail(word, expected):
    assert engine.normalize_tail(word) == (expected, True)


@pytest.mark.parametrize(
    "word",
    ["しん", "しんー", "ーー", "っ"],
)
def test_normalize_tail_invalid(word):
    char, valid = engine.normalize_tail(word)
    assert valid is False
    assert char == "" or char == "ん"


def test_is_connected():
    assert engine.is_connected("り", "り") is True
    assert engine.is_connected("く", "ぐ") is True
    assert engine.is_connected("ぐ", "く") is True
    assert engine.is_connected("は", "ぱ") is True
    assert engine.is_connected("は", "さ") is False


def test_generate_card():
    settings = Settings(cardSize=5, cardOptions=CardOptions(dakuten=True))
    candidates = engine.get_candidate_chars(settings)
    free = engine.pick_free_char()
    card = engine.generate_card(5, candidates, free)
    assert card.size == 5
    assert len(card.cells) == 25
    center = card.cells[12]
    assert center.isFree is True
    assert center.isOpen is True
    assert center.char == free
    chars = [c.char for c in card.cells]
    assert len(set(chars)) == len(chars)
    assert free not in {c.char for c in card.cells if not c.isFree}


def test_compute_bingo_lines():
    size = 3
    candidates = engine.get_candidate_chars(Settings(cardSize=size))
    card = engine.generate_card(size, candidates, "あ")
    for cell in card.cells:
        cell.isOpen = True
    lines = engine.compute_bingo_lines(card)
    assert len(lines) == 8  # 3横 + 3縦 + 2斜め


def test_apply_word_openings():
    settings = Settings(cardSize=3)
    state = GameState(phase="setup", settings=settings)
    p1 = Player(id="p1", name="p1", status="active")
    p2 = Player(id="p2", name="p2", status="active")
    state.players = [p1, p2]
    state.freeChar = "あ"
    candidates = engine.get_candidate_chars(settings)
    for player in state.players:
        player.card = engine.generate_card(3, candidates, state.freeChar)
        player.bingoLineIds = engine.compute_bingo_lines(player.card)
        player.openedCellCount = engine.count_open_cells(player.card)

    opened = engine._apply_word_openings(state, "あいう")
    assert set(opened) == {"あ", "い", "う"}
    assert all(p.openedCellCount >= 1 for p in state.players)


def test_start_game_individual():
    settings = Settings(cardSize=3)
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    assert state.phase == "playing"
    assert state.round == 1
    assert state.currentPlayerId in {"p1", "p2"}
    assert state.requiredStartChar == state.freeChar
    assert all(p.card is not None for p in state.players)
    assert state.currentTurnTimeLimitMs == (
        settings.timeLimitSeconds + settings.extraTimeSeconds
    ) * 1000


def test_process_word_valid_and_advance():
    settings = Settings(cardSize=3)
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId
    engine.process_word(state, first, state.freeChar + "い", now_ms())
    assert len(state.wordHistory) == 1
    assert state.usedWords == [state.freeChar + "い"]
    assert state.currentPlayerId != first


def test_next_round_preserves_play_order():
    settings = Settings(cardSize=3)
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
        Player(id="p3", name="p3", status="active"),
    ]

    engine.start_game(state, now_ms())
    play_order = state.playOrder.copy()

    for start_char, next_char in zip(
        [state.freeChar, "い", "う"], ["い", "う", "え"]
    ):
        assert state.currentPlayerId == play_order[state.orderIndex]
        engine.process_word(state, state.currentPlayerId, start_char + next_char, now_ms())

    assert state.round == 2
    assert state.roundRoster == play_order
    assert state.orderIndex == 0
    assert state.currentPlayerId == play_order[0]


def test_process_word_invalid_skip():
    settings = Settings(cardSize=3, invalidAction="skip")
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId
    engine.process_word(state, first, "ず" + "い", now_ms())
    assert len(state.wordHistory) == 0
    assert state.currentPlayerId != first


def test_process_word_invalid_disqualify():
    settings = Settings(cardSize=3, invalidAction="disqualify")
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId
    engine.process_word(state, first, "ず" + "い", now_ms())
    player = next(p for p in state.players if p.id == first)
    assert player.status == "disqualified"


@pytest.mark.parametrize(
    ("invalid_action", "expected_status"),
    [("skip", "active"), ("disqualify", "disqualified")],
)
def test_process_word_outside_length_limit_uses_invalid_action(invalid_action, expected_status):
    settings = Settings(
        cardSize=3,
        minWordLength=3,
        maxWordLength=4,
        invalidAction=invalid_action,
    )
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId

    engine.process_word(state, first, state.freeChar + "い", now_ms())

    player = next(p for p in state.players if p.id == first)
    assert player.status == expected_status
    assert len(state.wordHistory) == 0


def test_word_length_limit_includes_boundaries():
    settings = Settings(cardSize=3, minWordLength=2, maxWordLength=3)
    assert engine.is_valid_word_length("あい", settings) is True
    assert engine.is_valid_word_length("あいう", settings) is True
    assert engine.is_valid_word_length("あ", settings) is False
    assert engine.is_valid_word_length("あいうえ", settings) is False


def test_disqualify_all_ends_game():
    settings = Settings(cardSize=3, invalidAction="disqualify")
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId
    engine.process_word(state, first, "ず" + "い", now_ms())
    second = state.currentPlayerId
    engine.process_word(state, second, "ず" + "い", now_ms())
    assert state.phase == "result"
    assert state.result is not None
    assert state.result.reason == "all_disqualified"


def test_turns_end_condition():
    settings = Settings(cardSize=3, endCondition="turns", targetTurns=1)
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId
    engine.process_word(state, first, state.freeChar + "い", now_ms())
    engine.process_word(state, state.currentPlayerId, "い" + "う", now_ms())
    assert state.phase == "result"
    assert state.result.reason == "turns"
    assert state.result.endRound == 1


def test_ranking_standard_competition():
    settings = Settings(cardSize=3)
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
        Player(id="p3", name="p3", status="active"),
    ]
    engine.start_game(state, now_ms())
    for i, player in enumerate(state.players):
        player.bingoLineIds = []
        player.openedCellCount = [10, 10, 5][i]
    rankings = engine._build_rankings(state)
    assert rankings[0].rank == 1
    assert rankings[1].rank == 1
    assert rankings[2].rank == 3


def test_undo():
    settings = Settings(cardSize=3)
    state = GameState(phase="setup", settings=settings)
    state.players = [
        Player(id="p1", name="p1", status="active"),
        Player(id="p2", name="p2", status="active"),
    ]
    engine.start_game(state, now_ms())
    first = state.currentPlayerId
    before_round = state.round
    engine.process_word(state, first, state.freeChar + "い", now_ms())
    assert len(state.wordHistory) == 1
    state = engine.undo(state, now_ms())
    assert len(state.wordHistory) == 0
    assert state.round == before_round
    assert state.currentPlayerId == first
