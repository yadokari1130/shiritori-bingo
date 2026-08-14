"""MeCab IPADIC (Janome内包辞書) から名詞を抽出してしりとり用辞書JSONを生成するスクリプト。

使用方法:
    uv run python3 scripts/extract_nouns.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# backend ディレクトリを sys.path に追加
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from janome.sysdic import entries

from app.engine import HIRAGANA_SET, normalize_tail

# 除外する名詞の品詞細分類1 (rawモード用)
EXCLUDE_POS_SUBTYPES_RAW = {"接尾", "非自立", "数", "特殊", "引用文字列"}

# 除外する名詞の品詞細分類1 (plan-a / plan-b 用: 固有名詞・代名詞・形容動詞語幹も除外)
EXCLUDE_POS_SUBTYPES_FILTERED = {
    "接尾",
    "非自立",
    "数",
    "特殊",
    "引用文字列",
    "固有名詞",
    "形容動詞語幹",
    "代名詞",
}

# しりとりの開始文字として無効な文字（促音・拗音・小文字・長音・「ん」）
INVALID_HEAD_CHARS = set("ぁぃぅぇぉゃゅょっーん")


def kata_to_hira(text: str) -> str:
    """カタカナ文字列をひらがなに変換する。長音符などはそのまま保持する。"""
    res: list[str] = []
    for c in text:
        code = ord(c)
        # カタカナ 'ァ' (0x30A1) ～ 'ヶ' (0x30F6)
        if 0x30A1 <= code <= 0x30F6:
            res.append(chr(code - 0x60))
        else:
            res.append(c)
    return "".join(res)


def is_valid_surface(surface: str) -> bool:
    """表層形がひらがな・カタカナ・長音符・漢字のみで構成されているかを判定する。"""
    for c in surface:
        # ひらがな (0x3040 - 0x309F)、カタカナ (0x30A0 - 0x30FF)、長音符 'ー'
        if "\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" or c == "ー":
            continue
        # CJK統合漢字 (0x4E00 - 0x9FFF)
        if "\u4e00" <= c <= "\u9fff":
            continue
        return False
    return True


def extract_nouns(mode: str = "raw") -> dict[str, list[str]]:
    """IPADICから名詞を抽出し、頭文字ごとの辞書（dict[str, list[str]]）を返す。

    Args:
        mode: 抽出モード
            - "raw": 既存の全名詞抽出（約13.4万語）
            - "plan-a": 標準（固有名詞全除外 + 記号英数字除外 + 2〜6文字: 約3.5万語）
            - "plan-b": かんたん・身近（一般名詞・仮名語中心 + 2〜5文字: 約1万〜1.5万語）
    """
    raw_entries = entries()
    unique_words: set[str] = set()

    for entry in raw_entries.values():
        (
            surface,
            _left_id,
            _right_id,
            cost,
            pos,
            _conj_type,
            _conj_form,
            _base_form,
            reading,
            _pronunciation,
        ) = entry

        pos_parts = pos.split(",")

        # 品詞チェック: 大分類が名詞であること
        if pos_parts[0] != "名詞":
            continue

        # 品詞細分類1の除外チェック
        if mode == "raw":
            if len(pos_parts) > 1 and pos_parts[1] in EXCLUDE_POS_SUBTYPES_RAW:
                continue
        else:
            if len(pos_parts) > 1 and pos_parts[1] in EXCLUDE_POS_SUBTYPES_FILTERED:
                continue

            # 記号やアルファベット混じりの表層形を除外
            if not is_valid_surface(surface):
                continue

        # 読みが存在しない、または未定義のエントリはスキップ
        if not reading or reading == "*":
            continue

        # 読みをひらがなに正規化
        hira = kata_to_hira(reading)

        # 1文字以上で、ひらがな・伸ばし棒のみで構成されているかチェック
        if not hira or not all(c in HIRAGANA_SET for c in hira):
            continue

        # しりとりの有効な語尾判定（「ん」終わり、伸ばし棒のみ等を除外）
        tail_char, is_valid_tail = normalize_tail(hira)
        if not is_valid_tail or tail_char == "ん":
            continue

        # 開始文字が無効な文字（「ん」、小文字、長音）でないかチェック
        if hira[0] in INVALID_HEAD_CHARS:
            continue

        # プランごとの追加フィルタ
        if mode == "plan-a":
            # 読みの長さ: 2〜6文字
            if not (2 <= len(hira) <= 6):
                continue
            # 漢字1文字の高コスト（マイナー）語を除外
            if len(surface) == 1 and cost > 8000:
                continue

        elif mode == "plan-b":
            # 読みの長さ: 2〜5文字
            if not (2 <= len(hira) <= 5):
                continue
            # 表層形がひらがな・カタカナのみかどうか
            is_kana_only = all(
                "\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" or c == "ー"
                for c in surface
            )
            # サ変接続の漢語を抑制（一般名詞・副詞可能名詞、または仮名表記語を優先）
            sub_pos = pos_parts[1] if len(pos_parts) > 1 else ""
            if not (sub_pos in {"一般", "副詞可能"} or is_kana_only):
                continue
            # 漢字1文字の高コスト語を除外
            if len(surface) == 1 and cost > 6000:
                continue
            # 漢字表記で極端に高コストな専門語を除外
            if not is_kana_only and cost > 5500:
                continue

        unique_words.add(hira)

    # 頭文字ごとにグループ化してソート
    grouped_nouns: dict[str, list[str]] = {}
    for word in sorted(unique_words):
        head = word[0]
        grouped_nouns.setdefault(head, []).append(word)

    return grouped_nouns


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IPADICから名詞を抽出してしりとり用辞書JSONを生成します。"
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["raw", "plan-a", "plan-b"],
        default="raw",
        help="抽出モード: raw (今のまま/全件), plan-a (標準/固有名詞除外・2-6文字), plan-b (かんたん/身近な名詞・2-5文字) (デフォルト: raw)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=BACKEND_DIR / "app" / "data" / "nouns.json",
        help="出力先JSONファイルパス (デフォルト: app/data/nouns.json)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSONのインデント幅 (0でコンパクト出力, デフォルト: 2)",
    )
    args = parser.parse_args()

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"IPADIC辞書エントリから名詞を抽出中... (モード: {args.mode})")
    nouns_by_head = extract_nouns(mode=args.mode)

    total_words = sum(len(words) for words in nouns_by_head.values())
    total_heads = len(nouns_by_head)
    print(f"抽出完了: 全 {total_words:,} 単語（頭文字: {total_heads} 種類）")

    indent = args.indent if args.indent > 0 else None
    separators = (",", ": ") if indent is not None else (",", ":")

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            nouns_by_head,
            f,
            ensure_ascii=False,
            indent=indent,
            separators=separators,
        )

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"JSONファイルを保存しました: {output_path} ({file_size_mb:.2f} MB)")


if __name__ == "__main__":
    main()

