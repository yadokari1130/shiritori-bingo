"""しりとりビンゴ CPU思考エンジンおよび補助モード（アシスト機能）モジュール。

MeCab IPADIC由来の名詞辞書（nouns.json）を活用し、
1手先評価（貪欲法＋ヒューリスティクス）による最善手選択およびアシスト候補提示を行う。
"""

from __future__ import annotations

import json
from pathlib import Path
import random
from typing import Sequence

from app.engine import (
    DAKUTEN_MAP,
    compute_bingo_lines,
    count_open_cells,
    is_valid_word_length,
    line_definitions,
    normalize_tail,
)
from app.models import BingoCard, GameState

DATA_FILE = Path(__file__).resolve().parent / "data" / "nouns.json"

# メモリ上に展開される辞書キャッシュ
_NOUNS_DICT: dict[str, list[str]] | None = None
# 語尾評価用：各頭文字グループの単語数テーブル
_GROUP_HEAD_COUNT_MAP: dict[str, int] = {}
_MIN_GROUP_HEAD_COUNT: int = 0
_MAX_GROUP_HEAD_COUNT: int = 1


def load_nouns_dict() -> dict[str, list[str]]:
    """nouns.json をロードしてメモリ上にキャッシュする。"""
    global _NOUNS_DICT, _GROUP_HEAD_COUNT_MAP, _MIN_GROUP_HEAD_COUNT, _MAX_GROUP_HEAD_COUNT
    if _NOUNS_DICT is not None:
        return _NOUNS_DICT

    if not DATA_FILE.exists():
        _NOUNS_DICT = {}
        return _NOUNS_DICT

    with DATA_FILE.open("r", encoding="utf-8") as f:
        data: dict[str, list[str]] = json.load(f)

    _NOUNS_DICT = data

    # 各頭文字グループ（清音・濁音・半濁音統合）の単語数を集計
    head_counts: dict[str, int] = {k: len(v) for k, v in data.items()}
    group_counts: dict[str, int] = {}

    all_keys = set(data.keys())
    for k in all_keys:
        group = DAKUTEN_MAP.get(k, {k})
        total = sum(head_counts.get(ch, 0) for ch in group)
        group_counts[k] = total

    _GROUP_HEAD_COUNT_MAP = group_counts
    if group_counts:
        counts = list(group_counts.values())
        _MIN_GROUP_HEAD_COUNT = min(counts)
        _MAX_GROUP_HEAD_COUNT = max(counts)
    else:
        _MIN_GROUP_HEAD_COUNT = 0
        _MAX_GROUP_HEAD_COUNT = 1

    return _NOUNS_DICT


def get_candidate_words(
    start_char: str,
    used_words: Sequence[str],
    min_len: int | None = None,
    max_len: int | None = None,
) -> list[str]:
    """指定された開始文字（濁点・半濁点グループ含む）から始まる有効な候補単語一覧を返す。"""
    nouns = load_nouns_dict()
    if not nouns or not start_char:
        return []

    # 開始文字グループ（清音・濁点・半濁点）
    head_group = DAKUTEN_MAP.get(start_char, {start_char})
    used_set = set(used_words)

    candidates: list[str] = []
    for head_char in head_group:
        words = nouns.get(head_char, [])
        for word in words:
            if word in used_set:
                continue
            word_len = len(word)
            if min_len is not None and word_len < min_len:
                continue
            if max_len is not None and word_len > max_len:
                continue
            candidates.append(word)

    return candidates


def compute_reach_lines(card: BingoCard) -> list[str]:
    """あと1マスで成立するリーチ列のID一覧を返す。"""
    open_indexes = {cell.index for cell in card.cells if cell.isOpen}
    reach_line_ids: list[str] = []
    for line_id, indexes in line_definitions(card.size):
        unopened_count = sum(1 for idx in indexes if idx not in open_indexes)
        if unopened_count == 1:
            reach_line_ids.append(line_id)
    return reach_line_ids


def _simulate_card_opening(card: BingoCard, opened_chars: list[str]) -> BingoCard:
    """単語の開放文字を適用した仮想カードをディープコピーで生成する。"""
    new_cells = [cell.model_copy() for cell in card.cells]
    for ch in opened_chars:
        for cell in new_cells:
            if cell.char == ch and not cell.isOpen:
                cell.isOpen = True
                break
    return BingoCard(size=card.size, cells=new_cells, freeChar=card.freeChar)


def _calculate_tail_attack_score(tail_char: str, base_weight: float = 50.0) -> float:
    """語尾の返しにくさ（相手の手詰まり誘発）スコアを計算する。"""
    if _MAX_GROUP_HEAD_COUNT == _MIN_GROUP_HEAD_COUNT:
        return 0.0

    count = _GROUP_HEAD_COUNT_MAP.get(tail_char, 0)
    normalized = (count - _MIN_GROUP_HEAD_COUNT) / (_MAX_GROUP_HEAD_COUNT - _MIN_GROUP_HEAD_COUNT)
    # 単語数が少ない文字ほど 1.0 に近くなり高得点
    score = base_weight * (1.0 - normalized)
    return round(score, 2)


def _card_metrics_from_indices(size: int, open_indices: set[int]) -> tuple[int, int, int]:
    """(bingo_count, reach_count, open_count) を高速に計算する。"""
    bingo_count = 0
    reach_count = 0
    for _, indexes in line_definitions(size):
        unopened = sum(1 for idx in indexes if idx not in open_indices)
        if unopened == 0:
            bingo_count += 1
        elif unopened == 1:
            reach_count += 1
    return bingo_count, reach_count, len(open_indices)


def score_word(
    word: str,
    state: GameState,
    subject_id: str,
) -> float:
    """単語 W を入力した際の盤面変化と語尾戦略に基づくスコアを算出する。"""
    tail, valid = normalize_tail(word)
    if not valid:
        return -99999.0

    opened_chars = list(dict.fromkeys(word))

    is_team = state.settings.mode == "team"
    target_bingos = state.settings.targetBingos
    is_bingo_end = state.settings.endCondition == "bingos"

    # 自分のカード
    self_card: BingoCard | None = None
    if not is_team:
        p = next((pl for pl in state.players if pl.id == subject_id), None)
        self_card = p.card if p else None
    else:
        t = next((tm for tm in state.teams if tm.id == subject_id), None)
        self_card = t.card if t else None

    if self_card is None:
        return 0.0

    # 自分の現状とシミュレーション
    self_open_indexes = {c.index for c in self_card.cells if c.isOpen}
    self_orig_bingo, self_orig_reach, self_orig_open = _card_metrics_from_indices(self_card.size, self_open_indexes)

    # 開放文字の適用
    self_sim_indexes = set(self_open_indexes)
    for ch in opened_chars:
        for cell in self_card.cells:
            if cell.char == ch and cell.index not in self_sim_indexes:
                self_sim_indexes.add(cell.index)
                break
    self_sim_bingo, self_sim_reach, self_sim_open = _card_metrics_from_indices(self_card.size, self_sim_indexes)

    delta_self_bingo = self_sim_bingo - self_orig_bingo
    delta_self_reach = self_sim_reach - self_orig_reach
    delta_self_open = self_sim_open - self_orig_open

    # 1. 自分のスコア
    score_self = 0.0
    if is_bingo_end and self_sim_bingo >= target_bingos and self_orig_bingo < target_bingos:
        # 勝利確定手
        score_self += 10000.0
    else:
        score_self += delta_self_bingo * 1000.0

    score_self += delta_self_reach * 60.0
    score_self += delta_self_open * 10.0

    # 2. 対戦相手のスコア
    score_opp = 0.0
    opp_cards: list[BingoCard] = []

    if not is_team:
        for pl in state.players:
            if pl.id != subject_id and pl.status == "active" and pl.card:
                opp_cards.append(pl.card)
    else:
        for tm in state.teams:
            if tm.id != subject_id and tm.status == "active" and tm.card:
                opp_cards.append(tm.card)

    for opp_card in opp_cards:
        opp_open_indexes = {c.index for c in opp_card.cells if c.isOpen}
        opp_orig_bingo, opp_orig_reach, opp_orig_open = _card_metrics_from_indices(opp_card.size, opp_open_indexes)

        opp_sim_indexes = set(opp_open_indexes)
        for ch in opened_chars:
            for cell in opp_card.cells:
                if cell.char == ch and cell.index not in opp_sim_indexes:
                    opp_sim_indexes.add(cell.index)
                    break
        opp_sim_bingo, opp_sim_reach, opp_sim_open = _card_metrics_from_indices(opp_card.size, opp_sim_indexes)

        delta_opp_bingo = opp_sim_bingo - opp_orig_bingo
        delta_opp_reach = opp_sim_reach - opp_orig_reach
        delta_opp_open = opp_sim_open - opp_orig_open

        if is_bingo_end and opp_sim_bingo >= target_bingos and opp_orig_bingo < target_bingos:
            # 相手を勝たせてしまう手
            score_opp -= 10000.0
        else:
            score_opp -= delta_opp_bingo * 800.0

        score_opp -= delta_opp_reach * 40.0
        score_opp -= delta_opp_open * 5.0

    # 3. 語尾の強さ・しりとり戦略スコア
    # 3.1 返しにくさ
    score_tail_attack = _calculate_tail_attack_score(tail)

    # 3.2 次手番相手のカード妨害（次の手番の相手のカードに文字 tail が含まれていなければボーナス加点）
    score_tail_defense = 0.0
    if state.roundRoster:
        curr_idx = state.orderIndex
        next_idx = (curr_idx + 1) % len(state.roundRoster)
        next_subject_id = state.roundRoster[next_idx]
        if next_subject_id != subject_id:
            next_card: BingoCard | None = None
            if not is_team:
                next_p = next((pl for pl in state.players if pl.id == next_subject_id), None)
                next_card = next_p.card if next_p else None
            else:
                next_t = next((tm for tm in state.teams if tm.id == next_subject_id), None)
                next_card = next_t.card if next_t else None

            if next_card is not None:
                card_chars = {cell.char for cell in next_card.cells if not cell.isOpen}
                # 語尾の文字（グループ含む）が次手番相手のカードの未開放マスに含まれていないか
                tail_group = DAKUTEN_MAP.get(tail, {tail})
                if not (tail_group & card_chars):
                    score_tail_defense = 30.0

    total_score = score_self + score_opp + score_tail_attack + score_tail_defense
    return round(total_score, 2)


def select_best_word(state: GameState, subject_id: str) -> str | None:
    """CPUの手番において、スコア最大の単語を選択する。候補がなければ None（スキップ）。"""
    start_char = state.requiredStartChar or state.freeChar
    candidates = get_candidate_words(
        start_char=start_char,
        used_words=state.usedWords,
        min_len=state.settings.minWordLength,
        max_len=state.settings.maxWordLength,
    )

    if not candidates:
        return None

    # 各単語のスコアを計算
    scored_candidates: list[tuple[str, float]] = []
    for word in candidates:
        s = score_word(word, state, subject_id)
        scored_candidates.append((word, s))

    if not scored_candidates:
        return None

    # 最高スコアを特定
    max_score = max(s for _, s in scored_candidates)
    best_words = [w for w, s in scored_candidates if s == max_score]

    # 最高スコアの中でランダムに1つ選択
    return random.choice(best_words)


def get_assist_suggestions(state: GameState, subject_id: str, count: int = 3) -> list[str]:
    """補助モード（アシスト機能）用におすすめ単語をサンプリングして返す。

    スコア上位群（上位10〜15件）からランダムに count 件をサンプリングする。
    """
    start_char = state.requiredStartChar or state.freeChar
    candidates = get_candidate_words(
        start_char=start_char,
        used_words=state.usedWords,
        min_len=state.settings.minWordLength,
        max_len=state.settings.maxWordLength,
    )

    if not candidates:
        return []

    # スコアリング
    scored: list[tuple[str, float]] = []
    for word in candidates:
        s = score_word(word, state, subject_id)
        scored.append((word, s))

    # スコア降順にソート
    scored.sort(key=lambda x: x[1], reverse=True)

    # 上位プール（最大15件）
    pool_size = min(15, len(scored))
    top_pool = [w for w, _ in scored[:pool_size]]

    # ランダムサンプリング（最大 count 件）
    sample_size = min(count, len(top_pool))
    if sample_size <= 0:
        return []

    return random.sample(top_pool, sample_size)
