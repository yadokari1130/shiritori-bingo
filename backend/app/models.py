from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CardOptions(BaseModel):
    """カードに使用する文字カテゴリの有効/無効設定。"""

    yoon: bool = False
    sokuon: bool = False
    prolonged: bool = False
    smallA: bool = False
    dakuten: bool = False
    handakuten: bool = False


class Settings(BaseModel):
    """ゲームルール設定。"""

    cardSize: int = 5
    mode: Literal["individual", "team"] = "individual"
    teamCount: int = 2
    cardOptions: CardOptions = Field(default_factory=CardOptions)
    endCondition: Literal["turns", "bingos"] = "turns"
    targetTurns: int = 3
    targetBingos: int = 3
    timeLimitSeconds: int = 30
    extraTimeSeconds: int = 10
    forceSkipOnTimeout: bool = False
    invalidAction: Literal["skip", "disqualify"] = "skip"
    inputWordCheck: bool = True
    minWordLength: int | None = None
    maxWordLength: int | None = None

    @field_validator("cardSize")
    @classmethod
    def _validate_card_size(cls, value: int) -> int:
        if value < 3 or value % 2 == 0:
            raise ValueError("カードサイズは3以上の奇数である必要があります")
        return value

    @field_validator("minWordLength", "maxWordLength")
    @classmethod
    def _validate_word_length(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("単語の文字数制限は1以上で指定してください")
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
    result: GameResult | None = None
    undoHistory: list[UndoSnapshot] = Field(default_factory=list)


# --- API リクエストモデル ---


class CreateRoomRequest(BaseModel):
    """ルーム作成リクエスト。"""

    settings: Settings
    password: str | None = None


class SettingsUpdateRequest(BaseModel):
    """ルール設定変更リクエスト。"""

    settings: Settings


class StartGameRequest(BaseModel):
    """ゲーム開始リクエスト。"""

    settings: Settings | None = None


class JoinRoomRequest(BaseModel):
    """ルーム参加リクエスト。"""

    password: str | None = None
    name: str | None = None


class NameChangeRequest(BaseModel):
    """名前変更リクエスト。"""

    name: str


class ChangeTeamRequest(BaseModel):
    """チーム変更リクエスト。"""

    teamId: str | None = None


class ChangeHostRequest(BaseModel):
    """親変更リクエスト。"""

    playerId: str


class KickPlayerRequest(BaseModel):
    """参加者強制退出リクエスト。"""

    playerId: str


class WordAction(BaseModel):
    """単語確定アクション。"""

    type: Literal["word"]
    word: str


class SkipAction(BaseModel):
    """スキップアクション。"""

    type: Literal["skip"]
    subjectId: str


class DisqualifyAction(BaseModel):
    """失格アクション。"""

    type: Literal["disqualify"]
    subjectId: str


class UndoAction(BaseModel):
    """undoアクション。"""

    type: Literal["undo"]


ActionRequest = Annotated[
    WordAction | SkipAction | DisqualifyAction | UndoAction,
    Field(discriminator="type"),
]
