"""Window state helpers: maximize, restore, minimize and fullscreen.

The app renders through :class:`core.render.Canvas`, which maps the logical
1200x800 grid onto the native window resolution. Resizing, maximizing or
restoring therefore never distorts or clips the layout, and typography is
re-rasterised crisply for the new size.
"""

import pygame


class WindowManager:
    def __init__(self, app=None):
        self.app = app
        self.state = "normal"
        self._window = None
        try:
            from pygame._sdl2.video import Window
            self._window = Window.from_display_module()
        except Exception:
            self._window = None

    # ----------------------------------------------------------- helpers
    @property
    def maximized(self):
        return self.state == "maximized"

    @property
    def minimized(self):
        return self.state == "minimized"

    def _call(self, name):
        if self._window is not None:
            try:
                getattr(self._window, name)()
                return True
            except Exception:
                pass
        try:
            if name == "minimize":
                pygame.display.iconify()
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------ actions
    def maximize(self):
        self._call("maximize")
        self.state = "maximized"

    def restore(self):
        self._call("restore")
        self.state = "normal"

    def minimize(self):
        self._call("minimize")
        self.state = "minimized"

    def toggle_maximize(self):
        if self.state == "maximized":
            self.restore()
        else:
            self.maximize()
        return self.state

    def toggle_fullscreen(self):
        app = self.app
        if app is None:
            return False
        if getattr(app, "fullscreen", False):
            app.set_display(app._windowed_size, fullscreen=False)
            self.state = "normal"
        else:
            size = self.size()
            if size[0] > 0 and size[1] > 0:
                app._windowed_size = tuple(size)
            app.set_display((0, 0), fullscreen=True)
            self.state = "normal"
        return getattr(app, "fullscreen", False)

    # ------------------------------------------------------------- events
    def handle_event(self, event):
        if event.type == getattr(pygame, "WINDOWMAXIMIZED", -1):
            self.state = "maximized"
        elif event.type == getattr(pygame, "WINDOWRESTORED", -2):
            if self.state != "minimized":
                self.state = "normal"
        elif event.type == getattr(pygame, "WINDOWMINIMIZED", -3):
            self.state = "minimized"
        elif event.type == getattr(pygame, "WINDOWFOCUSLOST", -4):
            pass

    def size(self):
        try:
            return pygame.display.get_window_size()
        except Exception:
            return (0, 0)
