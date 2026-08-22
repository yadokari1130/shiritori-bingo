"""名詞辞書データ (nouns.json) および抽出ロジックの単体テスト。"""

from __future__ import annotations

import json
from pathlib import Path

from app.engine import HIRAGANA_SET, normalize_tail
from scripts.extract_nouns import INVALID_HEAD_CHARS, kata_to_hira

DATA_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "nouns.json"


def test_kata_to_hira() -> None:
    """カタカナからひらがなへの変換が正しく行われることを確認。"""
    assert kata_to_hira("アイス") == "あいす"
    assert kata_to_hira("ラーメン") == "らーめん"
    assert kata_to_hira("ヴァイオリン") == "ゔぁいおりん"
    assert kata_to_hira("きつね") == "きつね"
    assert kata_to_hira("チョコレート") == "ちょこれーと"


def test_nouns_json_exists_and_loads() -> None:
    """nouns.json が存在し、辞書として正常にロードできることを確認。"""
    assert DATA_FILE.exists(), f"{DATA_FILE} が存在しません"
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) > 0


def test_nouns_json_structure_and_validity() -> None:
    """nouns.json の各エントリがしりとりルールおよびフォーマット仕様を満たしていることを確認。"""
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data: dict[str, list[str]] = json.load(f)

    all_words: set[str] = set()
    total_count = 0

    # 開始文字として無効なキーが存在しないこと
    for head_char in data:
        assert (
            head_char not in INVALID_HEAD_CHARS
        ), f"無効な頭文字キーが含まれています: {head_char}"
        assert (
            head_char in HIRAGANA_SET
        ), f"許可されていない文字が頭文字キーに含まれています: {head_char}"

    for head_char, words in data.items():
        assert isinstance(words, list)
        assert len(words) > 0, f"頭文字 '{head_char}' の単語リストが空です"

        # リスト内がソートされていること
        assert words == sorted(words), f"頭文字 '{head_char}' の単語リストがソートされていません"

        for word in words:
            total_count += 1

            # 1文字以上
            assert len(word) >= 1, "空文字が含まれています"

            # 頭文字の一致
            assert (
                word[0] == head_char
            ), f"単語 '{word}' の頭文字がキー '{head_char}' と一致しません"

            # 文字種チェック
            assert all(
                c in HIRAGANA_SET for c in word
            ), f"単語 '{word}' に不正な文字種が含まれています"

            # 語尾の有効性判定（「ん」終わり、伸ばし棒のみ等でないこと）
            tail_char, is_valid_tail = normalize_tail(word)
            assert (
                is_valid_tail
            ), f"単語 '{word}' の語尾がしりとりとして無効です"
            assert (
                tail_char != "ん"
            ), f"単語 '{word}' が 'ん' で終わっています"

            all_words.add(word)

    # 重複がないこと
    assert len(all_words) == total_count, "辞書全体で単語の重複が存在します"

    # 単語数が3万語以上あること
    assert total_count >= 30_000, f"単語数が少なすぎます: {total_count}"
