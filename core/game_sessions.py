"""Demo game performance is stored separately from canonical health signals."""
import json
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, model_validator

GAME_IDS = ("lunar_alien_reaction", "coloring_shapes", "memory_test", "reaction_test", "speed_click", "number_hunt")
GAME_LABEL = "Demo game performance, not a validated health measurement. Not used for health alerts or model scoring."


class GameResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: int
    accuracy: FiniteFloat = Field(ge=0, le=100)
    mistakes: int = Field(ge=0)
    hits: int = Field(ge=0)
    avg_reaction_ms: FiniteFloat | None = Field(default=None, ge=0)
    duration: FiniteFloat = Field(ge=0)
    stats: list[tuple[str, str]] = Field(default_factory=list, max_length=100)
    extra: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def finite_and_bounded_json(self):
        text = json.dumps(self.model_dump(), allow_nan=False)
        if len(text.encode()) > 65536:
            raise ValueError("game result exceeds 64 KiB")
        return self


class GameSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    crew_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    game_id: Literal["lunar_alien_reaction", "coloring_shapes", "memory_test", "reaction_test", "speed_click", "number_hunt"]
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    ts: AwareDatetime | None = None
    result: GameResult
