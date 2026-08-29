import unicodedata
from typing import Annotated, Literal

import nh3
from pydantic import BaseModel, Field, field_validator, model_validator


def sanitize_text(text: str, max_length: int = 50) -> str:
    """nh3 と unicodedata を使用してプレーンテキストを無害化・正規化する。"""
    if not text:
        return ""
    # 1. HTMLタグ・スクリプトの完全除去
    cleaned = nh3.clean(text, tags=set())
    # 2. Unicode NFKC 正規化
    normalized = unicodedata.normalize("NFKC", cleaned)
    # 3. 制御文字（ASCII制御文字およびDEL）の除去
    sanitized = "".join(ch for ch in normalized if ord(ch) >= 32 and ord(ch) != 127)
    # 4. 前後の空白（全角空白・ゼロ幅スペース含む）をトリム
    trimmed = sanitized.strip(" \t\n\r\u3000\u200b\u200c\u200d\ufeff")
    return trimmed[:max_length]


class CardOptions(BaseModel):
    """カードに使用する文字カテゴリの有効/無効設定。"""

    yoon: bool = False
    sokuon: bool = False
    prolonged: bool = False
    smallA: bool = False
    dakuten: bool = True
    handakuten: bool = True


class Settings(BaseModel):
    """ゲームルール設定。"""

    cardSize: int = Field(default=5, ge=3, le=9)
    mode: Literal["individual", "team"] = "individual"
    teamCount: int = Field(default=2, ge=2, le=10)
    cardOptions: CardOptions = Field(default_factory=CardOptions)
    endCondition: Literal["turns", "bingos"] = "turns"
    targetTurns: int = Field(default=3, ge=1, le=100)
    targetBingos: int = Field(default=3, ge=1, le=20)
    timeLimitSeconds: int = Field(default=30, ge=5, le=300)
    extraTimeSeconds: int = Field(default=10, ge=0, le=120)
    forceSkipOnTimeout: bool = False
    invalidAction: Literal["skip", "disqualify"] = "skip"
    inputWordCheck: bool = True
    minWordLength: int | None = Field(default=None, ge=1, le=50)
    maxWordLength: int | None = Field(default=None, ge=1, le=50)

    @field_validator("cardSize")
    @classmethod
    def _validate_card_size(cls, value: int) -> int:
        if value < 3 or value > 9 or value % 2 == 0:
            raise ValueError("カードサイズは3以上9以下の奇数である必要があります")
        return value

    @field_validator("teamCount")
    @classmethod
    def _validate_team_count(cls, value: int) -> int:
        if value < 2 or value > 10:
            raise ValueError("チーム数は2以上10以下で指定してください")
        return value

    @field_validator("minWordLength", "maxWordLength")
    @classmethod
    def _validate_word_length(cls, value: int | None) -> int | None:
        if value is not None and (value < 1 or value > 50):
            raise ValueError("単語の文字数制限は1以上50以下で指定してください")
        return value

    @model_validator(mode="after")
    def _validate_word_length_range(self) -> Settings:
        if (
            self.minWordLength is not None
            and self.maxWordLength is not None
            and self.minWordLength > self.maxWordLength
        ):
            raise ValueError("最小文字数は最大文字数以下で指定してください")
        return self

    @model_validator(mode="after")
    def _validate_target_bingos(self) -> Settings:
        if self.endCondition == "bingos" and self.targetBingos > self.cardSize * 2 + 2:
            max_bingos = self.cardSize * 2 + 2
            raise ValueError(f"ビンゴ数はカードサイズに対して最大{max_bingos}までです")
        return self


class Cell(BaseModel):
    """ビンゴカードの1マス。"""

    index: int
    row: int
    column: int
    char: str
    isFree: bool
    isOpen: bool


class BingoCard(BaseModel):
    """N×Nのビンゴカード。"""

    size: int
    cells: list[Cell]
    freeChar: str


class Player(BaseModel):
    """参加者。チーム戦ではカードや失格状態はチームに持たせる。"""

    id: str
    name: str
    teamId: str | None = None
    status: Literal["active", "disqualified"] | None = None
    connectionStatus: Literal["connected", "disconnected"] = "connected"
    disconnectedAt: int | None = None
    card: BingoCard | None = None
    bingoLineIds: list[str] | None = None
    openedCellCount: int | None = None
    sortOrder: int = 0
    isCpu: bool = False


class Team(BaseModel):
    """チーム。チーム戦でのゲーム進行単位。"""

    id: str
    memberPlayerIds: list[str] = Field(default_factory=list)
    status: Literal["active", "disqualified"] = "active"
    card: BingoCard | None = None
    bingoLineIds: list[str] = Field(default_factory=list)
    openedCellCount: int = 0
    sortOrder: int = 0


class WordEntry(BaseModel):
    """入力された単語の履歴エントリ。"""

    word: str
    playerId: str
    round: int
    sequence: int
    openedChars: list[str] = Field(default_factory=list)


class Ranking(BaseModel):
    """順位情報。失格者はrankがNone。"""

    rank: int | None
    subjectType: Literal["player", "team"]
    subjectId: str
    bingoCount: int
    openedCellCount: int
    status: Literal["active", "disqualified"]


class PlayerResult(BaseModel):
    """結果画面用の参加者情報。"""

    playerId: str
    name: str
    teamId: str | None = None
    status: Literal["active", "disqualified"] | None = None
    card: BingoCard | None = None
    bingoLineIds: list[str] | None = None
    openedCellCount: int | None = None
    connectionStatus: Literal["connected", "disconnected"] = "connected"
    isCpu: bool = False


class TeamResult(BaseModel):
    """結果画面用のチーム情報。"""

    teamId: str
    memberPlayerIds: list[str]
    status: Literal["active", "disqualified"]
    card: BingoCard
    bingoLineIds: list[str]
    openedCellCount: int


class ResultSnapshot(BaseModel):
    """結果画面で確定表示するためのスナップショット。"""

    players: list[PlayerResult]
    teams: list[TeamResult]
    wordHistory: list[WordEntry]
    freeChar: str
    settings: Settings


class GameResult(BaseModel):
    """ゲーム終了時の結果情報。"""

    reason: Literal["turns", "bingos", "all_disqualified"]
    endRound: int
    achieverPlayerIds: list[str]
    achieverTeamIds: list[str]
    rankings: list[Ranking]
    snapshot: ResultSnapshot


class UndoSnapshot(BaseModel):
    """undo用のスナップショット。"""

    gameStateBeforeAction: GameState
    restoredTurnTimeLimitMs: int


class GameState(BaseModel):
    """ルームの公開ゲーム状態。"""

    phase: Literal["setup", "playing", "result"]
    settings: Settings
    hasPassword: bool = False
    hostPlayerId: str | None = None
    freeChar: str = ""
    players: list[Player] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    playOrder: list[str] = Field(default_factory=list)
    round: int = 0
    roundRoster: list[str] = Field(default_factory=list)
    orderIndex: int = 0
    currentPlayerId: str | None = None
    currentTeamId: str | None = None
    requiredStartChar: str = ""
    usedWords: list[str] = Field(default_factory=list)
    wordHistory: list[WordEntry] = Field(default_factory=list)
    remainingTimeMs: int = 0
    currentTurnTimeLimitMs: int = 0
    currentTurnInputPlayerId: str | None = None
    turnStartedAt: int | None = None
    assistSuggestions: list[str] = Field(default_factory=list)
    result: GameResult | None = None
    undoHistory: list[UndoSnapshot] = Field(default_factory=list)


# --- API リクエストモデル ---


class CreateRoomRequest(BaseModel):
    """ルーム作成リクエスト。"""

    settings: Settings
    password: str | None = Field(default=None, max_length=100)


class SettingsUpdateRequest(BaseModel):
    """ルール設定変更リクエスト。"""

    settings: Settings


class StartGameRequest(BaseModel):
    """ゲーム開始リクエスト。"""

    settings: Settings | None = None


class JoinRoomRequest(BaseModel):
    """ルーム参加リクエスト。"""

    password: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def _sanitize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        sanitized = sanitize_text(value, max_length=50)
        return sanitized or None


class NameChangeRequest(BaseModel):
    """名前変更リクエスト。"""

    name: str = Field(..., min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def _sanitize_name(cls, value: str) -> str:
        sanitized = sanitize_text(value, max_length=50)
        if not sanitized:
            raise ValueError("有効な名前を入力してください")
        return sanitized


class ChangeTeamRequest(BaseModel):
    """チーム変更リクエスト。"""

    teamId: str | None = Field(default=None, max_length=100)


class ChangeHostRequest(BaseModel):
    """親変更リクエスト。"""

    playerId: str = Field(..., min_length=1, max_length=100)


class KickPlayerRequest(BaseModel):
    """参加者強制退出リクエスト。"""

    playerId: str = Field(..., min_length=1, max_length=100)


class WordAction(BaseModel):
    """単語確定アクション。"""

    type: Literal["word"]
    word: str = Field(..., min_length=1, max_length=50)

    @field_validator("word")
    @classmethod
    def _sanitize_word(cls, value: str) -> str:
        sanitized = sanitize_text(value, max_length=50)
        if not sanitized:
            raise ValueError("単語を入力してください")
        return sanitized


class SkipAction(BaseModel):
    """スキップアクション。"""

    type: Literal["skip"]
    subjectId: str = Field(..., min_length=1, max_length=100)


class DisqualifyAction(BaseModel):
    """失格アクション。"""

    type: Literal["disqualify"]
    subjectId: str = Field(..., min_length=1, max_length=100)


class UndoAction(BaseModel):
    """undoアクション。"""

    type: Literal["undo"]


ActionRequest = Annotated[
    WordAction | SkipAction | DisqualifyAction | UndoAction,
    Field(discriminator="type"),
]


class AssistResponse(BaseModel):
    """補助モード（アシスト機能）の候補単語レスポンス。"""

    suggestions: list[str]

