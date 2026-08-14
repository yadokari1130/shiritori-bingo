from tortoise import fields
from tortoise.models import Model


class Room(Model):
    id = fields.CharField(max_length=255, pk=True)
    password_hash = fields.TextField(null=True)
    creator_token_hash = fields.TextField(null=True)
    settings_json = fields.TextField()
    phase = fields.CharField(max_length=20)
    free_char = fields.TextField(null=True)
    current_player_id = fields.CharField(max_length=255, null=True)
    current_team_id = fields.CharField(max_length=255, null=True)
    required_start_char = fields.TextField(null=True)
    round = fields.IntField(default=0)
    order_index = fields.IntField(default=0)
    remaining_time_ms = fields.BigIntField(default=0)
    current_turn_time_limit_ms = fields.BigIntField(default=0)
    turn_started_at = fields.BigIntField(null=True)
    result_json = fields.TextField(null=True)
    state_json = fields.TextField()
    created_at = fields.BigIntField()
    updated_at = fields.BigIntField()
    host_player_id = fields.CharField(max_length=255, null=True)
    round_roster_json = fields.TextField(default="[]")

    class Meta:
        table = "rooms"


class Player(Model):
    id = fields.CharField(max_length=255, pk=True)
    room = fields.ForeignKeyField("models.Room", related_name="players", on_delete=fields.CASCADE)
    name = fields.TextField()
    status = fields.CharField(max_length=30, null=True)
    card_json = fields.TextField(null=True)
    bingo_line_ids_json = fields.TextField(null=True)
    opened_cell_count = fields.IntField(null=True)
    sort_order = fields.IntField(default=0)
    team_id = fields.CharField(max_length=255, null=True)
    connection_status = fields.CharField(max_length=30, default="connected")
    disconnected_at = fields.BigIntField(null=True)
    is_cpu = fields.BooleanField(default=False)

    class Meta:
        table = "players"


class Team(Model):
    id = fields.CharField(max_length=255, pk=True)
    room = fields.ForeignKeyField("models.Room", related_name="teams", on_delete=fields.CASCADE)
    sort_order = fields.IntField(default=0)
    status = fields.CharField(max_length=30, default="active")
    card_json = fields.TextField(null=True)
    bingo_line_ids_json = fields.TextField(null=True)
    opened_cell_count = fields.IntField(default=0)

    class Meta:
        table = "teams"


class PlayerSession(Model):
    id = fields.CharField(max_length=255, pk=True)
    room = fields.ForeignKeyField("models.Room", related_name="sessions", on_delete=fields.CASCADE)
    player = fields.ForeignKeyField("models.Player", related_name="sessions", on_delete=fields.CASCADE)
    token_hash = fields.CharField(max_length=255, unique=True)
    active_connections = fields.IntField(default=0)
    last_seen_at = fields.BigIntField()
    disconnected_at = fields.BigIntField(null=True)

    class Meta:
        table = "player_sessions"


class WordHistory(Model):
    id = fields.IntField(pk=True)
    room = fields.ForeignKeyField("models.Room", related_name="word_history", on_delete=fields.CASCADE)
    player_id = fields.CharField(max_length=255)
    word = fields.TextField()
    round = fields.IntField()
    sequence = fields.IntField()
    opened_chars_json = fields.TextField()
    created_at = fields.BigIntField()

    class Meta:
        table = "word_history"


class UndoSnapshot(Model):
    id = fields.IntField(pk=True)
    room = fields.ForeignKeyField("models.Room", related_name="undo_snapshots", on_delete=fields.CASCADE)
    snapshot_json = fields.TextField()
    restored_turn_time_limit_ms = fields.BigIntField()
    created_at = fields.BigIntField()

    class Meta:
        table = "undo_snapshots"
