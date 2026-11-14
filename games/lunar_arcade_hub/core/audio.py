"""Sound effect manager. Missing audio devices or files degrade silently."""

import os

import pygame

from config import SOUND_DIR

SOUND_FILES = {
    "click": "click.ogg",
    "pop": "pop.ogg",
    "hit": "hit.ogg",
    "combo": "combo.ogg",
    "miss": "miss.ogg",
    "error": "error.ogg",
    "success": "success.ogg",
    "countdown": "countdown.ogg",
    "go": "go.ogg",
    "gameover": "gameover.ogg",
    "tick": "tick.ogg",
}


class AudioManager:
    def __init__(self, sound_dir=SOUND_DIR):
        self.enabled = False
        self.muted = False
        self.sounds = {}
        self._missing = []
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2,
                                  buffer=512)
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return
        for key, filename in SOUND_FILES.items():
            path = os.path.join(sound_dir, filename)
            if os.path.exists(path):
                try:
                    self.sounds[key] = pygame.mixer.Sound(path)
                    self.sounds[key].set_volume(0.55)
                except (pygame.error, OSError):
                    self._missing.append(filename)
            else:
                self._missing.append(filename)

    def play(self, name, volume=None):
        if not self.enabled or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        if volume is not None:
            sound.set_volume(max(0.0, min(1.0, volume)))
            sound.play()
            sound.set_volume(0.55)
        else:
            sound.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted
