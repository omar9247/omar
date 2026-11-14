"""Game registry — add a new game by importing it and appending its class."""

from games.lunar_alien_reaction import LunarAlienReaction
from games.coloring_shapes import ColoringShapes
from games.memory_test import MemoryTest
from games.reaction_test import ReactionTest
from games.speed_click import SpeedClick
from games.number_hunt import NumberHunt

GAME_CLASSES = [
    LunarAlienReaction,
    ColoringShapes,
    MemoryTest,
    ReactionTest,
    SpeedClick,
    NumberHunt,
]

GAMES_BY_ID = {cls.game_id: cls for cls in GAME_CLASSES}


def get_game_class(game_id):
    return GAMES_BY_ID.get(game_id)


def create_game(app, game_id):
    cls = GAMES_BY_ID.get(game_id)
    if cls is None:
        raise KeyError(f"Unknown game id: {game_id}")
    return cls(app)
