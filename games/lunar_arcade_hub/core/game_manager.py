"""Application shell: screen stack, game hosting, transitions, persistence."""

import sys
import pygame

from config import WIDTH, HEIGHT, FPS, APP_TITLE, DB_PATH, IS_WEB
from core import render
from core.render import Canvas
from core.database import Database
from core.audio import AudioManager
from core.input_manager import InputManager
from core.neuro import NeuroEngine
from core.window import WindowManager
from ui.dialogs import QuitDialog
from animations.starfield import Starfield
from animations.transitions import FadeTransition
from games import create_game
from ui import theme
from ui.dashboard import Dashboard
from ui.statistics import StatisticsScreen
from ui.profile import ProfileScreen
from ui.monitor import MonitorScreen


def _export_session_safely(game_id, difficulty, result):
    """A missing or broken web bridge must never interrupt a game."""
    try:
        from core.aura_export import send_session
        send_session(game_id, difficulty, result)
    except Exception as exc:
        print(f"[AURA] game-session export unavailable: {exc}", file=sys.stderr)


def _enable_high_dpi():
    """Ask Windows not to bitmap-stretch the window on scaled displays."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class LunarArcadeApp:
    def __init__(self, db_path=None):
        _enable_high_dpi()
        pygame.init()
        pygame.display.set_caption(f"{APP_TITLE} | Cognitive Training")
        render.install()
        self.fullscreen = False
        self._windowed_size = (WIDTH, HEIGHT)
        self._display = self._create_display(self._windowed_size)
        self.screen = Canvas(self._display)
        self.clock = pygame.time.Clock()
        self.window = WindowManager(self)
        self.db = Database(db_path or DB_PATH)
        self.neuro = NeuroEngine(self.db)
        self.neuro.rebuild_from_history()
        self.audio = AudioManager()
        self.input = InputManager(mapper=self.screen.to_logical)
        self.starfield = Starfield(WIDTH, HEIGHT)
        self.fade = FadeTransition()

        self.screens = {
            "dashboard": Dashboard(self),
            "statistics": StatisticsScreen(self),
            "monitor": MonitorScreen(self),
            "profile": ProfileScreen(self),
        }
        self.screen_name = "dashboard"
        self.active = self.screens["dashboard"]
        self.active.enter()

        self.game = None
        self.running = True
        self._shutdown_done = False
        self.quit_dialog = None

    # ------------------------------------------------------------ display
    def _create_display(self, size, fullscreen=False):
        flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
        if IS_WEB:
            # Waiting for browser vsync can block Pygbag's main thread.
            return pygame.display.set_mode(size, flags)
        try:
            return pygame.display.set_mode(size, flags, vsync=1)
        except (pygame.error, TypeError):
            return pygame.display.set_mode(size, flags)

    def set_display(self, size=None, fullscreen=None):
        """Create a new display surface and re-fit the logical canvas."""
        if fullscreen is None:
            fullscreen = self.fullscreen
        if size is None:
            size = (0, 0) if fullscreen else self._windowed_size
        if not fullscreen and size[0] > 0:
            self._windowed_size = tuple(size)
        try:
            display = self._create_display(tuple(size), bool(fullscreen))
        except pygame.error:
            return self._display
        self.fullscreen = bool(fullscreen)
        self._display = display
        self.screen.attach(display)
        return display

    def _sync_display(self):
        """Follow OS window resizes / maximize / restore / fullscreen."""
        surface = pygame.display.get_surface()
        if surface is None:
            return
        try:
            win = pygame.display.get_window_size()
        except Exception:
            win = surface.get_size()
        if win[0] <= 0 or win[1] <= 0:
            return
        if surface.get_size() != tuple(win):
            flags = pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE
            try:
                surface = pygame.display.set_mode(tuple(win), flags)
            except pygame.error:
                return
            self._display = surface
        if surface is not self.screen.raw or \
                surface.get_size() != (self.screen.win_w, self.screen.win_h):
            self.screen.attach(surface)

    # -------------------------------------------------------- navigation
    def go_to(self, name):
        if name not in self.screens or self.fade.busy:
            return
        if self.game is None and name == self.screen_name:
            return
        self.fade.start(lambda: self._switch_screen(name))

    def _switch_screen(self, name):
        self.game = None
        self.screen_name = name
        self.active = self.screens[name]
        self.active.enter()

    def open_game(self, game_id):
        if self.fade.busy:
            return
        self.fade.start(lambda: self._start_game(game_id))

    def _start_game(self, game_id):
        try:
            self.game = create_game(self, game_id)
        except KeyError:
            self.game = None
            return
        self.screen_name = game_id
        self.active = None

    def request_quit(self):
        """Guard against accidental closure with a confirmation dialog."""
        if self.quit_dialog is None:
            self.quit_dialog = QuitDialog(self)

    def close_dialog(self):
        self.quit_dialog = None

    def confirm_quit(self):
        self.quit_dialog = None
        self.quit()

    def quit(self):
        self.running = False

    # ------------------------------------------------------------ events
    def process_events(self, events):
        self._sync_display()
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.window.toggle_fullscreen()
                break
        pointers = self.input.process(events)
        for event in events:
            self.window.handle_event(event)
            if event.type == pygame.QUIT:
                self.request_quit()
        if not self.running:
            return
        if self.quit_dialog is not None:
            for event in events:
                self.quit_dialog.handle_event(event, pointers)
            return
        if self.game is not None:
            for event in events:
                self.game.handle_event(event, pointers)
            if self.game is not None and self.game.exit_requested:
                self.game.exit_requested = False
                self.go_to("dashboard")
        else:
            for event in events:
                self.active.handle_event(event, pointers)

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.starfield.update(dt)
        self.fade.update(dt)
        if self.quit_dialog is not None:
            self.quit_dialog.update(dt)
        if self.game is not None:
            self.game.update(dt)
            self._save_if_finished()
        elif self.active is not None:
            self.active.update(dt)

    def _save_if_finished(self, game=None):
        game = game if game is not None else self.game
        if game is None or game.state != "summary" or game.saved:
            return
        result = game.result or {}
        previous_best = self.db.best_score(game.game_id)
        already_played = game.game_id in self.db.per_game()
        game.first_play = not already_played
        game.new_best = already_played and result.get("score", 0) > previous_best
        difficulty = str((result.get("extra") or {}).get(
            "difficulty", "normal")).lower()
        try:
            ev, feedback, _ = self.neuro.commit(game.game_id, difficulty, result)
            game.assessment = ev
            game.neuro_feedback = feedback
            result["assessment"] = ev
            result["feedback"] = feedback
        except Exception:
            # Never let a persistence error break gameplay.
            pass
        _export_session_safely(game.game_id, difficulty, result)
        game.saved = True

    # -------------------------------------------------------------- draw
    def draw(self):
        self.screen.sync()
        theme.draw_background(self.screen, self.starfield)
        if self.game is not None:
            self.game.draw(self.screen)
        elif self.active is not None:
            self.active.draw(self.screen)
        if self.quit_dialog is not None:
            self.quit_dialog.draw(self.screen)
        self.fade.draw(self.screen)
        pygame.display.flip()

    # --------------------------------------------------------------- run
    def step(self, dt=1.0 / 60.0, events=None):
        """Advance one frame (used by the automated smoke tests)."""
        events = events or []
        self.process_events(events)
        self.update(dt)
        self.draw()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.process_events(pygame.event.get())
            self.update(dt)
            self.draw()
        self.shutdown()

    def shutdown(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True
        try:
            self.db.close()
        except Exception:
            pass
        pygame.quit()
