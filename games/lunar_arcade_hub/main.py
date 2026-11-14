"""Lunar Arcade Hub — entry point.

Run with:  python main.py
"""

import asyncio
import sys

import pygame

from core.game_manager import LunarArcadeApp


def main():
    try:
        app = LunarArcadeApp()
    except pygame.error as exc:
        print("Could not initialise the display:", exc)
        print("This application needs a graphical desktop session "
              "(or SDL_VIDEODRIVER=dummy for headless testing).")
        return 1
    app.run()
    return 0


async def run_web():
    """Pygbag entry point: one frame per browser task, never a sync loop."""
    app = LunarArcadeApp()
    last = pygame.time.get_ticks()
    try:
        while app.running:
            # pygame.time.Clock.tick() can block the browser's main thread in
            # Pygbag; derive a clamped delta from the monotonic timer instead.
            now = pygame.time.get_ticks()
            dt = min(max(0.0, (now - last) / 1000.0), 0.05)
            last = now
            # Pygbag does not run a blocking event loop: pump SDL events each
            # frame so mouse, touch, keyboard and resize input still work.
            app.step(dt, pygame.event.get())
            await asyncio.sleep(0)
    finally:
        app.shutdown()


if __name__ == "__main__":
    if sys.platform == "emscripten":
        asyncio.run(run_web())
    else:
        sys.exit(main())
