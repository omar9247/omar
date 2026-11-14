"""Monitor sub-view: astronaut psychological-wellbeing check-in.

A five-point Likert questionnaire split into five dimensions, with drafts,
timestamped submissions, dimension scores, supportive feedback and trends.
It is a self-report indicator, not a clinical assessment.
"""

import datetime

import pygame

from config import (
    WIDTH, PANEL, PANEL_LIGHT, PANEL_DARK, BORDER, BORDER_SOFT, WHITE,
    MUTED, CYAN, GOLD, GREEN, RED, PURPLE, DIM, ORANGE,
)
from core import wellbeing
from ui import theme
from ui.widgets import Button

DIM_COLORS = {
    "workload": ORANGE,
    "emotional": PURPLE,
    "motivation": GOLD,
    "social": CYAN,
    "resilience": GREEN,
}


def _stamp(iso_string):
    try:
        then = datetime.datetime.fromisoformat(iso_string)
    except (TypeError, ValueError):
        return "—"
    return then.strftime("%d %b %Y · %H:%M").upper()


class WellbeingView:
    def __init__(self, app, monitor):
        self.app = app
        self.monitor = monitor
        self.mode = "form"          # form | results | history
        self.category = 0
        self.answers = {}
        self.submissions = []
        self.selected = 0
        self.message = ""
        self.message_color = MUTED
        self.draft_at = None
        self._result = None
        self._feedback = None
        self._build_buttons()

    # ----------------------------------------------------------- buttons
    def _build_buttons(self):
        self.back_button = Button((966, 94, 194, 36), "BACK TO PHYSIOLOGY",
                                  "ghost", CYAN, 11)
        self.prev_button = Button((342, 700, 88, 36), "PREV", "ghost",
                                  CYAN, 12)
        self.next_button = Button((438, 700, 88, 36), "NEXT", "ghost",
                                  CYAN, 12)
        self.draft_button = Button((836, 700, 128, 36), "SAVE DRAFT", "ghost",
                                   GOLD, 11)
        self.submit_button = Button((972, 700, 172, 36), "SUBMIT CHECK-IN",
                                    "primary", PURPLE, 12)
        self.history_button = Button((56, 700, 110, 36), "HISTORY", "ghost",
                                     CYAN, 11)
        self.new_button = Button((806, 700, 154, 36), "NEW CHECK-IN", "primary",
                                 PURPLE, 12)
        self.results_history_button = Button((650, 700, 144, 36), "HISTORY",
                                             "ghost", CYAN, 12)
        self.results_back_button = Button((966, 94, 194, 36),
                                          "BACK TO PHYSIOLOGY", "ghost", CYAN, 11)
        self.history_new_button = Button((806, 700, 154, 36), "NEW CHECK-IN",
                                         "primary", PURPLE, 12)
        self.history_back_button = Button((966, 94, 194, 36),
                                          "BACK TO PHYSIOLOGY", "ghost", CYAN, 11)
        self._all_buttons = [
            self.back_button, self.prev_button, self.next_button,
            self.draft_button, self.submit_button, self.history_button,
            self.new_button, self.results_history_button,
            self.results_back_button, self.history_new_button,
            self.history_back_button,
        ]

    def _visible_buttons(self):
        if self.mode == "form":
            return [self.back_button, self.prev_button, self.next_button,
                    self.draft_button, self.submit_button, self.history_button]
        if self.mode == "results":
            return [self.results_back_button, self.results_history_button,
                    self.new_button]
        return [self.history_back_button, self.history_new_button]

    # -------------------------------------------------------------- data
    def enter(self):
        self.submissions = self.app.db.wellbeing_submissions()
        draft = self.app.db.wellbeing_draft()
        if draft and draft.get("answers_data"):
            self.answers = wellbeing.normalise_answers(draft["answers_data"])
            self.draft_at = draft.get("created_at")
            self.message = ("Draft restored — " +
                            f"{len(self.answers)}/{wellbeing.TOTAL_QUESTIONS} "
                            "answered.")
            self.message_color = GOLD
        else:
            self.answers = {}
            self.draft_at = None
            self.message = ""
        self.mode = "form"
        self.category = 0
        self.selected = 0

    def update(self, dt):
        mouse = self.app.input.pos
        down = self.app.input.down
        for button in self._visible_buttons():
            button.update(dt, mouse, down)

    # ------------------------------------------------------------ layout
    @staticmethod
    def _main_rect():
        return pygame.Rect(326, 152, 834, 600)

    def _category_rows(self):
        rows = []
        progress = wellbeing.dimension_progress(self.answers)
        for i, dim in enumerate(wellbeing.DIMENSIONS):
            rect = pygame.Rect(56, 212 + i * 78, 238, 66)
            rows.append((i, dim, rect, progress[dim["key"]]))
        return rows

    def _option_rects(self, card_rect, qid):
        rects = []
        start_x = card_rect.x + 414
        for i, (value, _, _) in enumerate(wellbeing.SCALE):
            rects.append((qid, value,
                          pygame.Rect(start_x + i * 78, card_rect.y + 54,
                                      72, 30)))
        return rects

    def _question_rows(self):
        dim = wellbeing.DIMENSIONS[self.category]
        main = self._main_rect()
        rows = []
        y = 250
        for qid in dim["questions"]:
            card = pygame.Rect(main.x + 16, y, main.w - 32, 94)
            rows.append((wellbeing.BY_ID[qid], card,
                         self._option_rects(card, qid)))
            y += 102
        return rows

    # ------------------------------------------------------------ events
    def handle_event(self, event, pointers):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.monitor.show_physiology()
                return
        for p in pointers:
            if p.kind != "down":
                continue
            if self.mode == "form":
                if self._handle_form_click(p.pos):
                    return
            elif self.mode == "results":
                if self._handle_results_click(p.pos):
                    return
            elif self.mode == "history":
                if self._handle_history_click(p.pos):
                    return

    def _handle_form_click(self, pos):
        if self.back_button.hit(pos):
            self.monitor.show_physiology()
            return True
        if self.history_button.hit(pos):
            self.show_history()
            return True
        for index, _, rect, _ in self._category_rows():
            if rect.collidepoint(pos):
                self.category = index
                self.message = ""
                self.app.audio.play("click", 0.3)
                return True
        for q, card, options in self._question_rows():
            for qid, value, rect in options:
                if rect.collidepoint(pos):
                    self.answers[qid] = value
                    self.message = ""
                    self.app.audio.play("tick", 0.25)
                    return True
        if self.prev_button.hit(pos):
            self.category = max(0, self.category - 1)
            self.app.audio.play("click", 0.3)
            return True
        if self.next_button.hit(pos):
            self.category = min(len(wellbeing.DIMENSIONS) - 1,
                                self.category + 1)
            self.app.audio.play("click", 0.3)
            return True
        if self.draft_button.hit(pos):
            self.save_draft()
            return True
        if self.submit_button.hit(pos):
            self.submit()
            return True
        return False

    def _handle_results_click(self, pos):
        if self.results_back_button.hit(pos):
            self.monitor.show_physiology()
            return True
        if self.results_history_button.hit(pos):
            self.show_history()
            return True
        if self.new_button.hit(pos):
            self.new_check_in()
            return True
        return False

    def _handle_history_click(self, pos):
        if self.history_back_button.hit(pos):
            self.monitor.show_physiology()
            return True
        if self.history_new_button.hit(pos):
            self.new_check_in()
            return True
        panel = pygame.Rect(40, 188, 340, 492)
        for i, row in enumerate(self.submissions[:9]):
            rect = pygame.Rect(panel.x + 12, 242 + i * 44, panel.w - 24, 38)
            if rect.collidepoint(pos):
                self.selected = i
                self.app.audio.play("click", 0.3)
                return True
        return False

    # ----------------------------------------------------------- actions
    def save_draft(self):
        answers = wellbeing.flatten_answers(self.answers)
        self.draft_at = self.app.db.save_wellbeing_draft(answers)
        count = len(answers)
        self.message = (f"Draft saved {_stamp(self.draft_at)} — "
                        f"{count}/{wellbeing.TOTAL_QUESTIONS} answered.")
        self.message_color = GOLD
        self.app.audio.play("click", 0.4)

    def submit(self):
        if not wellbeing.is_complete(self.answers):
            missing = wellbeing.unanswered_questions(self.answers)
            first = wellbeing.BY_ID[missing[0]]
            for i, dim in enumerate(wellbeing.DIMENSIONS):
                if first["id"] in dim["questions"]:
                    self.category = i
                    break
            self.message = (f"{len(missing)} question(s) unanswered — answer "
                            "all 17 or save a draft.")
            self.message_color = RED
            self.app.audio.play("error", 0.4)
            return
        previous_scores = (self.submissions[0].get("scores_data")
                           if self.submissions else None)
        scores = wellbeing.score_submission(self.answers, previous_scores)
        feedback = wellbeing.build_feedback(scores, previous_scores)
        answers = wellbeing.flatten_answers(self.answers)
        self.app.db.submit_wellbeing(answers, scores, feedback)
        self.submissions = self.app.db.wellbeing_submissions()
        self._result = scores
        self._feedback = feedback
        self.selected = 0
        self.mode = "results"
        self.message = ""
        self.app.audio.play("success")

    def new_check_in(self):
        self.answers = {}
        self.category = 0
        self.mode = "form"
        self.message = ""
        self.draft_at = None
        try:
            self.app.db.delete_wellbeing_draft()
        except AttributeError:
            pass

    def show_history(self):
        self.submissions = self.app.db.wellbeing_submissions()
        self.mode = "history"
        self.selected = 0
        self.message = ""

    # -------------------------------------------------------------- draw
    def draw(self, surface):
        if self.mode == "form":
            self._draw_form(surface)
        elif self.mode == "results":
            self._draw_results(surface)
        else:
            self._draw_history(surface)

    def _draw_header(self, surface, subtitle):
        theme.text(surface, "PSYCHOLOGICAL WELLBEING", 26, WHITE, (52, 104),
                   anchor="midleft")
        theme.text(surface, subtitle, 11, MUTED, (54, 130),
                   anchor="midleft", bold=False)

    def _draw_form(self, surface):
        self._draw_header(surface, "Self-reported check-in · five-point "
                                   "agreement scale · not a clinical assessment")
        self.back_button.draw(surface)
        # Sidebar.
        side = pygame.Rect(40, 152, 270, 600)
        theme.panel(surface, side, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "DIMENSIONS", 11, CYAN, (side.x + 16, side.y + 24),
                   anchor="midleft")
        for index, dim, rect, done in self._category_rows():
            active = index == self.category
            color = DIM_COLORS[dim["key"]]
            if active:
                theme.alpha_rect(surface, rect, color, 30, radius=10)
                pygame.draw.rect(surface, color, rect, width=1, border_radius=10)
            else:
                pygame.draw.rect(surface, BORDER_SOFT, rect, width=1,
                                 border_radius=10)
            theme.text(surface, dim["title"].upper(), 9,
                       WHITE if active else MUTED,
                       (rect.x + 10, rect.y + 16), anchor="midleft")
            theme.text(surface, f"{done}/{len(dim['questions'])}",
                       9, color if done else DIM,
                       (rect.right - 10, rect.y + 16), anchor="midright")
            theme.progress_bar(surface,
                               (rect.x + 10, rect.bottom - 16, rect.w - 20, 4),
                               done / len(dim["questions"]), color,
                               bg=PANEL_DARK, border=None)
        theme.text(surface, "Completed check-ins", 9, DIM,
                   (side.x + 16, 620), anchor="midleft")
        theme.text(surface, str(len(self.submissions)), 20, WHITE,
                   (side.x + 16, 644), anchor="midleft")
        if self.submissions:
            theme.text(surface, "LAST " + _stamp(
                self.submissions[0].get("created_at", "")), 8, MUTED,
                (side.x + 16, 666), anchor="midleft", bold=False)
        self.history_button.draw(surface)
        if self.message:
            for i, line in enumerate(theme.wrap_lines(
                    self.message, 9, side.w - 32, bold=False)[:3]):
                theme.text(surface, line, 9, self.message_color,
                           (side.x + 16, 560 + i * 12), anchor="midleft",
                           bold=False)
        # Main questionnaire.
        main = self._main_rect()
        theme.panel(surface, main, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        dim = wellbeing.DIMENSIONS[self.category]
        color = DIM_COLORS[dim["key"]]
        theme.text(surface, dim["title"].upper(), 13, color,
                   (main.x + 16, main.y + 24), anchor="midleft")
        theme.text(surface, dim["description"], 10, MUTED,
                   (main.x + 16, main.y + 44), anchor="midleft", bold=False)
        # Scale legend, aligned with the option columns.
        for i, (_, long_label, _) in enumerate(wellbeing.SCALE):
            cx = main.x + 414 + i * 78 + 36
            lines = theme.wrap_lines(long_label.upper(), 8, 74, bold=False)
            for j, line in enumerate(lines[:2]):
                theme.text(surface, line, 8, MUTED, (cx, main.y + 58 + j * 10),
                           bold=False)
        pygame.draw.line(surface, BORDER_SOFT, (main.x + 16, main.y + 88),
                         (main.right - 16, main.y + 88), 1)
        answers = wellbeing.normalise_answers(self.answers)
        for q, card, options in self._question_rows():
            answered = q["id"] in answers
            pygame.draw.rect(surface, PANEL_LIGHT if answered else PANEL_DARK,
                             card, border_radius=12)
            pygame.draw.rect(surface, BORDER_SOFT if answered else
                             (120, 94, 40), card, width=1, border_radius=12)
            lines = theme.wrap_lines(f"{q['id']}. {q['text']}", 11, 400,
                                     bold=False)
            for j, line in enumerate(lines[:3]):
                theme.text(surface, line, 11, WHITE if answered else MUTED,
                           (card.x + 16, card.y + 14 + j * 15),
                           anchor="midleft", bold=False)
            for qid, value, rect in options:
                chosen = answers.get(qid) == value
                if chosen:
                    pygame.draw.rect(surface, color, rect, border_radius=8)
                else:
                    pygame.draw.rect(surface, PANEL, rect, border_radius=8)
                pygame.draw.rect(surface, color if chosen else BORDER_SOFT,
                                 rect, width=1, border_radius=8)
                label = next(s[2] for s in wellbeing.SCALE if s[0] == value)
                lines = label.split("\n")
                for j, line in enumerate(lines):
                    theme.text(surface, line, 7,
                               (10, 14, 30) if chosen else MUTED,
                               (rect.centerx, rect.centery - 4 + j * 9),
                               bold=chosen)
        # Progress + actions.
        count = len(answers)
        theme.text(surface, f"{count}/{wellbeing.TOTAL_QUESTIONS} ANSWERED",
                   9, GREEN if count == wellbeing.TOTAL_QUESTIONS else GOLD,
                   (main.x + 16, main.bottom - 82), anchor="midleft")
        theme.progress_bar(surface, (main.x + 150, main.bottom - 87, 480, 8),
                           count / wellbeing.TOTAL_QUESTIONS, PURPLE,
                           bg=PANEL_DARK, border=None)
        self.prev_button.enabled = self.category > 0
        self.next_button.enabled = self.category < len(wellbeing.DIMENSIONS) - 1
        self.submit_button.enabled = count == wellbeing.TOTAL_QUESTIONS
        for button in (self.prev_button, self.next_button, self.draft_button,
                       self.submit_button):
            button.draw(surface)

    # ---------------------------------------------------------- results
    def _draw_results(self, surface):
        self._draw_header(surface, "Check-in saved · dimension indicators "
                                   "only · no diagnosis is generated")
        self.results_back_button.draw(surface)
        if self._result is None:
            latest = self.submissions[0] if self.submissions else None
            if latest:
                self._result = latest.get("scores_data") or []
                self._feedback = latest.get("feedback_data") or {}
        scores = self._result or []
        feedback = self._feedback or {}
        stamp = (_stamp(self.submissions[0]["created_at"])
                 if self.submissions else "")
        panel = pygame.Rect(40, 152, 1120, 150)
        theme.panel(surface, panel, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "CHECK-IN SAVED", 13, GREEN,
                   (panel.x + 18, panel.y + 24), anchor="midleft")
        theme.text(surface, stamp, 10, MUTED,
                   (panel.right - 18, panel.y + 24), anchor="midright")
        lines = theme.wrap_lines(feedback.get("summary", ""), 12,
                                 panel.w - 36, bold=False)
        for i, line in enumerate(lines[:3]):
            theme.text(surface, line, 12, WHITE,
                       (panel.x + 18, panel.y + 52 + i * 17),
                       anchor="midleft", bold=False)
        theme.text(surface, feedback.get("note", ""), 9, DIM,
                   (panel.x + 18, panel.bottom - 18), anchor="midleft",
                   bold=False)
        # Dimension cards.
        x = 40
        for dim in scores:
            card = pygame.Rect(x, 320, 208, 178)
            color = DIM_COLORS.get(dim.get("key"), CYAN)
            theme.panel(surface, card, color=PANEL, border=BORDER_SOFT,
                        radius=14, width=1, shadow=False)
            theme.text(surface, dim.get("title", "").upper(), 9, MUTED,
                       (card.x + 12, card.y + 18), anchor="midleft")
            theme.text(surface, f"{dim.get('percent', 0)}%", 30, color,
                       (card.x + 12, card.y + 52), anchor="midleft")
            theme.text(surface, dim.get("label", ""), 10, WHITE,
                       (card.x + 12, card.y + 78), anchor="midleft")
            theme.progress_bar(surface,
                               (card.x + 12, card.y + 96, card.w - 24, 6),
                               dim.get("percent", 0) / 100, color,
                               bg=PANEL_DARK, border=None)
            delta = dim.get("delta")
            delta_text = ("FIRST CHECK-IN" if delta is None else
                          f"{delta:+d}% vs previous")
            delta_color = (MUTED if delta is None else
                           GREEN if delta > 0 else RED if delta < 0 else MUTED)
            theme.text(surface, delta_text, 8, delta_color,
                       (card.x + 12, card.y + 120), anchor="midleft",
                       bold=False)
            theme.text(surface, f"Difficulty {dim.get('difficulty_mean', 0):.1f}"
                               " / 5", 8, DIM,
                       (card.x + 12, card.y + 140), anchor="midleft",
                       bold=False)
            x += 224
        # Recommendations.
        rec_panel = pygame.Rect(40, 516, 1120, 168)
        theme.panel(surface, rec_panel, color=PANEL, border=BORDER_SOFT,
                    radius=18, width=1, shadow=False)
        theme.text(surface, "SUPPORTIVE RECOMMENDATIONS", 11, CYAN,
                   (rec_panel.x + 18, rec_panel.y + 22), anchor="midleft")
        y = rec_panel.y + 46
        for rec in (feedback.get("recommendations") or [])[:3]:
            pygame.draw.circle(surface, CYAN, (rec_panel.x + 24, y + 5), 2)
            for line in theme.wrap_lines(rec, 10, rec_panel.w - 70,
                                         bold=False)[:2]:
                theme.text(surface, line, 10, WHITE,
                           (rec_panel.x + 36, y), anchor="midleft",
                           bold=False)
                y += 14
            y += 6
        pattern = feedback.get("pattern")
        if pattern:
            theme.text(surface, pattern, 9, GOLD,
                       (rec_panel.right - 18, rec_panel.bottom - 18),
                       anchor="midright", bold=False)
        self.new_button.draw(surface)
        self.results_history_button.draw(surface)

    # ---------------------------------------------------------- history
    def _draw_history(self, surface):
        self._draw_header(surface, "Historical self-reports · dimension trends "
                                   "· persistent patterns need repeat data")
        self.history_back_button.draw(surface)
        left = pygame.Rect(40, 188, 340, 492)
        theme.panel(surface, left, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "SUBMISSIONS — LATEST 9", 11, CYAN,
                   (left.x + 16, left.y + 24), anchor="midleft")
        if not self.submissions:
            theme.text(surface, "No submitted check-ins yet.", 11, DIM,
                       (left.x + 16, left.y + 60), anchor="midleft", bold=False)
        for i, row in enumerate(self.submissions[:9]):
            rect = pygame.Rect(left.x + 12, 242 + i * 44, left.w - 24, 38)
            active = i == self.selected
            if active:
                theme.alpha_rect(surface, rect, PURPLE, 32, radius=9)
                pygame.draw.rect(surface, PURPLE, rect, width=1, border_radius=9)
            theme.text(surface, _stamp(row.get("created_at", "")), 10,
                       WHITE if active else MUTED,
                       (rect.x + 10, rect.y + 13), anchor="midleft")
            answers = row.get("answers_data") or {}
            theme.text(surface, f"{len(answers)}/17", 9, GREEN,
                       (rect.right - 10, rect.y + 13), anchor="midright")
            scores = row.get("scores_data") or []
            low = sum(1 for s in scores if s.get("percent", 100) < 50)
            theme.text(surface, f"{low} dimension(s) below 50%", 8, DIM,
                       (rect.x + 10, rect.y + 27), anchor="midleft",
                       bold=False)
        right = pygame.Rect(396, 188, 764, 492)
        theme.panel(surface, right, color=PANEL, border=BORDER_SOFT, radius=18,
                    width=1, shadow=False)
        theme.text(surface, "DIMENSION TRENDS — LAST 8 (0–100%, higher is better)", 11,
                   CYAN, (right.x + 18, right.y + 24), anchor="midleft")
        ordered = list(reversed(self.submissions[:8]))
        series = wellbeing.trend_series(ordered)
        chart = pygame.Rect(right.x + 54, right.y + 64, right.w - 84, 240)
        for value in (0, 25, 50, 75, 100):
            y = chart.bottom - chart.h * value / 100
            pygame.draw.line(surface, BORDER_SOFT, (chart.x, y),
                             (chart.right, y), 1)
            theme.text(surface, str(value), 8, DIM,
                       (chart.x - 10, y), anchor="midright", bold=False)
        if not ordered:
            theme.text(surface, "Submit a check-in to start the trend.",
                       11, DIM, (right.centerx, right.y + 170), bold=False)
        elif len(ordered) == 1:
            theme.text(surface, "One check-in recorded — submit another to see "
                               "a trend.", 10, DIM,
                       (right.centerx, right.y + 190), bold=False)
        if ordered:
            count = len(ordered)
            xs = [chart.x + (chart.w * i / max(1, count - 1))
                  if count > 1 else chart.centerx for i in range(count)]
            for dim in wellbeing.DIMENSIONS:
                points = series[dim["key"]]
                color = DIM_COLORS[dim["key"]]
                pts = [(xs[i], chart.bottom - chart.h * points[i] / 100)
                       for i in range(min(len(points), count))]
                if len(pts) > 1:
                    pygame.draw.lines(surface, color, False, pts, 2)
                for px, py in pts:
                    pygame.draw.circle(surface, color, (int(px), int(py)), 3)
        # Legend.
        lx = right.x + 20
        ly = right.y + 320
        for i, dim in enumerate(wellbeing.DIMENSIONS):
            color = DIM_COLORS[dim["key"]]
            px = lx + (i % 3) * 240
            py = ly + (i // 3) * 18
            pygame.draw.circle(surface, color, (px, py), 3)
            theme.text(surface, dim["title"].upper(), 8, MUTED,
                       (px + 10, py), anchor="midleft", bold=False)
        # Selected submission detail.
        if self.submissions:
            row = self.submissions[self.selected]
            scores = row.get("scores_data") or []
            theme.text(surface, "SELECTED: " + _stamp(row.get("created_at", "")),
                       9, WHITE, (right.x + 20, right.y + 360), anchor="midleft")
            x = right.x + 20
            for dim in scores:
                color = DIM_COLORS.get(dim.get("key"), CYAN)
                theme.text(surface, dim.get("short", ""), 7, MUTED,
                           (x, right.y + 384), anchor="midleft", bold=False)
                theme.text(surface, f"{dim.get('percent', 0)}%", 13, color,
                           (x, right.y + 400), anchor="midleft")
                x += 144
            feedback = row.get("feedback_data") or {}
            summary = feedback.get("summary", "")
            for i, line in enumerate(theme.wrap_lines(
                    summary, 9, right.w - 40, bold=False)[:2]):
                theme.text(surface, line, 9, MUTED,
                           (right.x + 20, right.y + 428 + i * 13),
                           anchor="midleft", bold=False)
        self.history_new_button.draw(surface)
