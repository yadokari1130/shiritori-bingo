"""CPU思考エンジン (app/cpu.py) の単体テスト。"""

from __future__ import annotations

from app import cpu, engine
from app.models import BingoCard, Cell, GameState, Player, Settings


def test_load_nouns_dict():
    """nouns.json がロードされ、主要な頭文字キーが存在することを確認。"""
    nouns = cpu.load_nouns_dict()
    assert isinstance(nouns, dict)
    assert len(nouns) > 0
    assert "あ" in nouns
    assert "か" in nouns
    assert "し" in nouns


def test_get_candidate_words():
    """開始文字から始まる有効単語が正しく抽出されることを確認。"""
    # 「は」で始まる単語（「は」「ば」「ぱ」を含む）
    candidates = cpu.get_candidate_words("は", used_words=[])
    assert len(candidates) > 0
    # 「は」「ば」「ぱ」から始まることを確認
    assert all(w[0] in {"は", "ば", "ぱ"} for w in candidates)

    # 既出単語が除外されること
    first_word = candidates[0]
    filtered = cpu.get_candidate_words("は", used_words=[first_word])
    assert first_word not in filtered

    # 文字数制限（3文字〜4文字）
    length_filtered = cpu.get_candidate_words("あ", used_words=[], min_len=3, max_len=4)
    assert all(3 <= len(w) <= 4 for w in length_filtered)


def test_compute_reach_lines():
    """リーチ列（残り1マス）の判定が正しいことを確認。"""
    # 3x3 カードでテスト
    # [ (0,0): O, (0,1): O, (0,2): X ] -> r0 がリーチ
    cells = [
        Cell(index=0, row=0, column=0, char="あ", isFree=False, isOpen=True),
        Cell(index=1, row=0, column=1, char="い", isFree=False, isOpen=True),
        Cell(index=2, row=0, column=2, char="う", isFree=False, isOpen=False),
        Cell(index=3, row=1, column=0, char="え", isFree=False, isOpen=False),
        Cell(index=4, row=1, column=1, char="お", isFree=True, isOpen=True),
        Cell(index=5, row=1, column=2, char="か", isFree=False, isOpen=False),
        Cell(index=6, row=2, column=0, char="き", isFree=False, isOpen=False),
        Cell(index=7, row=2, column=1, char="く", isFree=False, isOpen=False),
        Cell(index=8, row=2, column=2, char="け", isFree=False, isOpen=False),
    ]
    card = BingoCard(size=3, cells=cells, freeChar="お")
    reach_lines = cpu.compute_reach_lines(card)
    assert "r0" in reach_lines


def test_score_word_self_bingo_and_reach():
    """ビンゴ成立手やリーチ作成手が高いスコアを得ることを確認。"""
    settings = Settings(cardSize=3)
    cells = [
        Cell(index=0, row=0, column=0, char="あ", isFree=False, isOpen=True),
        Cell(index=1, row=0, column=1, char="い", isFree=False, isOpen=True),
        Cell(index=2, row=0, column=2, char="う", isFree=False, isOpen=False),
        Cell(index=3, row=1, column=0, char="え", isFree=False, isOpen=False),
        Cell(index=4, row=1, column=1, char="お", isFree=True, isOpen=True),
        Cell(index=5, row=1, column=2, char="か", isFree=False, isOpen=False),
        Cell(index=6, row=2, column=0, char="き", isFree=False, isOpen=False),
        Cell(index=7, row=2, column=1, char="く", isFree=False, isOpen=False),
        Cell(index=8, row=2, column=2, char="け", isFree=False, isOpen=False),
    ]
    card = BingoCard(size=3, cells=cells, freeChar="お")
    p1 = Player(id="p1", name="CPU 1", isCpu=True, card=card, status="active")
    p2 = Player(id="p2", name="Player 2", isCpu=False, status="active")

    state = GameState(
        phase="playing",
        settings=settings,
        players=[p1, p2],
        playOrder=["p1", "p2"],
        roundRoster=["p1", "p2"],
        orderIndex=0,
        currentPlayerId="p1",
        requiredStartChar="う",
    )

    # 「うし」を入力すると、自分の (0,2) の「う」が開き、r0 ビンゴ成立 (+1000点以上)
    score_bingo = cpu.score_word("うし", state, "p1")
    # ビンゴ成立手は 1000 点以上の高スコアになる
    assert score_bingo > 1000.0

    # リーチ手（ビンゴにならないが1マス開いてリーチが増える手）
    # 例: 「え」を開ける手（(1,0) が開く）
    score_reach = cpu.score_word("えのぐ", state, "p1")
    # ビンゴ成立手の方がリーチ手よりも圧倒的に高い
    assert score_bingo > score_reach


def test_select_best_word_and_assist_suggestions():
    """select_best_word および get_assist_suggestions が正常に単語を返すことを確認。"""
    settings = Settings(cardSize=3)
    p1 = Player(
        id="p1",
        name="CPU 1",
        isCpu=True,
        status="active",
        card=engine.generate_card(3, engine.get_candidate_chars(settings), "あ"),
    )
    p2 = Player(
        id="p2",
        name="Player 2",
        isCpu=False,
        status="active",
        card=engine.generate_card(3, engine.get_candidate_chars(settings), "あ"),
    )

    state = GameState(
        phase="playing",
        settings=settings,
        freeChar="あ",
        players=[p1, p2],
        playOrder=["p1", "p2"],
        roundRoster=["p1", "p2"],
        orderIndex=0,
        currentPlayerId="p1",
        requiredStartChar="あ",
    )

    best_word = cpu.select_best_word(state, "p1")
    assert best_word is not None
    assert isinstance(best_word, str)
    assert best_word[0] in {"あ"}

    suggestions = cpu.get_assist_suggestions(state, "p1", count=3)
    assert len(suggestions) <= 3
    assert len(suggestions) > 0
    assert all(w[0] in {"あ"} for w in suggestions)
