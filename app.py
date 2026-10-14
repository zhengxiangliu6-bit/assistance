"""Assistance — AI Agent Desktop Workspace"""

import sys
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QLabel, QFrame,
    QStackedWidget, QCheckBox, QComboBox, QDialog, QTextEdit,
    QSystemTrayIcon, QMenu, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QAction
from pynput import keyboard as kb

from engine import AgentEngine
from schedule import (
    load_tasks, add_task, complete_task, uncomplete_task,
    delete_task, update_task, move_task,
)
from memory import search_memories, delete_memory, save_memory, update_memory
from creative import load_ideas, delete_idea
from settings import PERMISSION_DEFS, get_permission, set_permission

from ui.theme import C, S, F, D
from ui.styles import (
    global_style, btn_primary, btn_secondary, btn_ghost, btn_danger, btn_icon,
    input_field, textedit_field, combo_field,
    card_surface, checkbox_style, toggle_style, scrollarea, dialog_style,
)
from ui.components import (
    SidebarNavItem, MessageBubble, AgentStatus, ChatComposer,
    SectionHeader, EmptyState, ChatWelcomeView,
)
from ui.animations import fade_in, TypingDots, StatusDot
from i18n import t, cat_name, get_language, set_language


# ── Worker ────────────────────────────────────────────────

class WorkerThread(QThread):
    token_received = pyqtSignal(str)
    tool_called = pyqtSignal(str)
    reply_done = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    compressed = pyqtSignal(str)

    def __init__(self, engine, text):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self):
        try:
            for t, d in self.engine.chat_stream(self.text):
                {"token": self.token_received, "tool": self.tool_called,
                 "done": self.reply_done, "error": self.error_occurred,
                 "compressed": self.compressed}.get(t, self.error_occurred).emit(d)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ── Dialogs ───────────────────────────────────────────────

def _field_label(text):
    l = QLabel(text)
    l.setFont(QFont(F.SANS, F.XS))
    l.setStyleSheet(f"color: {C.TEXT_3}; letter-spacing: 1px;")
    return l


class EditTaskDialog(QDialog):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dialog.edit_task"))
        self.setMinimumWidth(440)
        self.setStyleSheet(dialog_style())
        layout = QVBoxLayout(self)
        layout.setSpacing(S.SM)
        layout.setContentsMargins(S.LG, S.LG, S.LG, S.LG)

        layout.addWidget(_field_label(t("dialog.title")))
        self.title_input = QLineEdit(task["title"])
        self.title_input.setStyleSheet(input_field())
        layout.addWidget(self.title_input)

        row = QHBoxLayout()
        row.setSpacing(S.SM)
        for lbl_text, attr, widget_fn in [
            (t("dialog.priority"), "priority_combo",
             lambda: self._combo(["low", "normal", "high"], task.get("priority", "normal"))),
            (t("dialog.date"), "due_input",
             lambda: self._line(task.get("due_date", ""))),
            (t("dialog.time"), "time_input",
             lambda: self._line(task.get("due_time", ""), "17:30")),
        ]:
            col = QVBoxLayout()
            col.addWidget(_field_label(lbl_text))
            w = widget_fn()
            setattr(self, attr, w)
            col.addWidget(w)
            row.addLayout(col)
        layout.addLayout(row)

        layout.addSpacing(S.SM)
        btns = QHBoxLayout()
        btns.addStretch()
        c = QPushButton(t("dialog.cancel"))
        c.setStyleSheet(btn_secondary())
        c.clicked.connect(self.reject)
        btns.addWidget(c)
        o = QPushButton(t("dialog.save"))
        o.setStyleSheet(btn_primary())
        o.clicked.connect(self.accept)
        btns.addWidget(o)
        layout.addLayout(btns)

    def _line(self, val, ph=""):
        w = QLineEdit(val)
        if ph:
            w.setPlaceholderText(ph)
        w.setStyleSheet(input_field())
        return w

    def _combo(self, items, current):
        w = QComboBox()
        w.addItems(items)
        w.setCurrentText(current)
        w.setStyleSheet(combo_field())
        return w

    def get_values(self):
        return {
            "title": self.title_input.text().strip(),
            "priority": self.priority_combo.currentText(),
            "due_date": self.due_input.text().strip(),
            "due_time": self.time_input.text().strip(),
        }


class EditMemoryDialog(QDialog):
    def __init__(self, memory, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dialog.edit_memory"))
        self.setMinimumWidth(480)
        self.setStyleSheet(dialog_style())
        layout = QVBoxLayout(self)
        layout.setSpacing(S.SM)
        layout.setContentsMargins(S.LG, S.LG, S.LG, S.LG)

        layout.addWidget(_field_label(t("dialog.content")))
        self.content_edit = QTextEdit()
        self.content_edit.setText(memory.get("content", ""))
        self.content_edit.setMinimumHeight(120)
        self.content_edit.setStyleSheet(textedit_field())
        layout.addWidget(self.content_edit)

        layout.addWidget(_field_label(t("dialog.category")))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["habit", "preference", "info", "general"])
        self.cat_combo.setCurrentText(memory.get("category", "general"))
        self.cat_combo.setStyleSheet(combo_field())
        layout.addWidget(self.cat_combo)

        layout.addSpacing(S.SM)
        btns = QHBoxLayout()
        btns.addStretch()
        c = QPushButton(t("dialog.cancel"))
        c.setStyleSheet(btn_secondary())
        c.clicked.connect(self.reject)
        btns.addWidget(c)
        o = QPushButton(t("dialog.save"))
        o.setStyleSheet(btn_primary())
        o.clicked.connect(self.accept)
        btns.addWidget(o)
        layout.addLayout(btns)

    def get_values(self):
        return {
            "content": self.content_edit.toPlainText().strip(),
            "category": self.cat_combo.currentText(),
        }


# ══════════════════════════════════════════════════════════
#  ChatPage
# ══════════════════════════════════════════════════════════

class ChatPage(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.worker = None
        self.current_bubble = None
        self._history_loaded = False
        self._busy = False
        self._welcome_visible = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for messages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(scrollarea() + f"QScrollArea {{ background: {C.BG_2}; }}")
        self.messages_widget = QWidget()
        self.messages_widget.setStyleSheet(f"background: {C.BG_2};")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(S.XXS)
        self.messages_layout.setContentsMargins(0, S.SM, 0, S.SM)
        self.scroll_area.setWidget(self.messages_widget)

        # Welcome view (shown when no messages)
        self.welcome = ChatWelcomeView()
        self.welcome.quick_action.connect(self._on_quick_action)
        self.messages_layout.addWidget(self.welcome)

        # Typing dots
        self.typing_dots = TypingDots()
        self.typing_dots.hide()
        self.messages_layout.addWidget(self.typing_dots)

        layout.addWidget(self.scroll_area, 1)

        # Status bar
        self.status = AgentStatus()
        self.status.setStyleSheet(f"background: {C.BG_1}; padding-left: {S.MD}px;")
        layout.addWidget(self.status)

        # Composer
        self.composer = ChatComposer()
        self.composer.submitted.connect(self._submit)
        layout.addWidget(self.composer)

    def _on_quick_action(self, text):
        self._submit(text)

    def load_history(self):
        if self._history_loaded:
            return
        self._history_loaded = True
        messages = self.engine.get_display_messages()
        if messages:
            self._hide_welcome()
            for role, content in messages:
                self._add_bubble(content, role == "user")

    def _submit(self, text):
        if self._busy or not text:
            return
        self._hide_welcome()
        self._add_bubble(text, True)
        self._set_busy(True)
        self.status.set_state("thinking")
        self.typing_dots.start()
        self.current_bubble = None

        self.worker = WorkerThread(self.engine, text)
        self.worker.token_received.connect(self._on_token)
        self.worker.tool_called.connect(lambda n: self.status.set_state("tool", n))
        self.worker.reply_done.connect(self._on_done)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.compressed.connect(lambda m: None)
        self.worker.start()

    def _on_token(self, text):
        if self.current_bubble is None:
            self.typing_dots.stop()
            self.status.set_state("streaming")
            self.current_bubble = self._add_bubble("", False)
        self.current_bubble.append_text(text)
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum())

    def _on_done(self, _):
        self.typing_dots.stop()
        self.status.set_state("idle")
        self.current_bubble = None
        self.worker = None
        self._set_busy(False)

    def _on_error(self, msg):
        self.typing_dots.stop()
        self.status.set_state("error", msg[:50])
        if self.current_bubble:
            self.current_bubble.set_text(f"Error: {msg}")
        else:
            self._add_bubble(f"Error: {msg}", False)
        self.current_bubble = None
        self.worker = None
        self._set_busy(False)
        QTimer.singleShot(5000, lambda: self.status.set_state("idle"))

    def _add_bubble(self, text, is_user):
        b = MessageBubble(text, is_user)
        self.messages_layout.addWidget(b)
        fade_in(b, 150)
        QTimer.singleShot(30, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()))
        return b

    def _hide_welcome(self):
        if self._welcome_visible:
            self.welcome.hide()
            self._welcome_visible = False

    def _set_busy(self, busy):
        self._busy = busy
        self.composer.set_enabled(not busy)

    def clear_chat(self):
        if self._busy:
            return
        self.engine.clear()
        while self.messages_layout.count():
            w = self.messages_layout.takeAt(0)
            if w.widget() and w.widget() not in (self.typing_dots, self.welcome):
                w.widget().deleteLater()
        self.messages_layout.addWidget(self.welcome)
        self.messages_layout.addWidget(self.typing_dots)
        self.welcome.show()
        self._welcome_visible = True
        self._history_loaded = True


# ══════════════════════════════════════════════════════════
#  SchedulePage
# ══════════════════════════════════════════════════════════

class SchedulePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C.BG_2};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S.XL, S.LG, S.XL, S.LG)
        layout.setSpacing(S.MD)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)

        # Add row
        add_row = QHBoxLayout()
        add_row.setSpacing(S.SM)
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText(t("schedule.add_placeholder"))
        self.add_input.setStyleSheet(input_field())
        self.add_input.returnPressed.connect(self._on_add)
        add_row.addWidget(self.add_input, 1)
        self.pri_combo = QComboBox()
        self.pri_combo.addItems(["normal", "high", "low"])
        self.pri_combo.setStyleSheet(combo_field())
        self.pri_combo.setFixedWidth(90)
        add_row.addWidget(self.pri_combo)
        ab = QPushButton(t("schedule.add"))
        ab.setStyleSheet(btn_primary())
        ab.setFixedWidth(60)
        ab.setCursor(Qt.CursorShape.PointingHandCursor)
        ab.clicked.connect(self._on_add)
        add_row.addWidget(ab)
        layout.addLayout(add_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(scrollarea())
        self.container = QWidget()
        self.tasks_layout = QVBoxLayout(self.container)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tasks_layout.setSpacing(S.XXS)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

    def refresh(self):
        while self.tasks_layout.count():
            w = self.tasks_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        tasks = load_tasks()
        if not tasks:
            self.tasks_layout.addWidget(EmptyState(t("schedule.empty")))
            return

        from datetime import datetime as dt
        now = dt.now()
        today, cur_time = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")

        def overdue(t):
            if t["done"] or not t.get("due_date"):
                return False
            if t["due_date"] < today:
                return True
            return t["due_date"] == today and t.get("due_time", "99") <= cur_time

        ov = [t for t in tasks if overdue(t)]
        td = sorted([t for t in tasks if not t["done"] and t.get("due_date") == today and not overdue(t)],
                     key=lambda x: x.get("due_time") or "99:99")
        fu = [t for t in tasks if not t["done"] and t.get("due_date") and t["due_date"] > today]
        nd = [t for t in tasks if not t["done"] and not t.get("due_date")]
        dn = [t for t in tasks if t["done"]]

        for title, items, color, sec in [
            (t("schedule.overdue"), ov, C.DANGER, "overdue"),
            (t("schedule.today"), td, C.ACCENT, "normal"),
            (t("schedule.upcoming"), fu, C.TEXT_3, "normal"),
            (t("schedule.unscheduled"), nd, C.TEXT_3, "normal"),
            (t("schedule.completed"), dn, C.TEXT_3, "done"),
        ]:
            if not items:
                continue
            self.tasks_layout.addWidget(SectionHeader(title, len(items), color))
            for i, tk in enumerate(items):
                self.tasks_layout.addWidget(self._card(tk, i, len(items), sec))

        self._sched_next(td, today, cur_time)

    def _card(self, task, idx, total, sec):
        f = QFrame()
        f.setMinimumHeight(44)
        bg = f"rgba(255,107,133,0.06)" if sec == "overdue" else C.BG_3
        bdr = f"rgba(255,107,133,0.20)" if sec == "overdue" else C.BORDER_SUB
        f.setStyleSheet(f"""
            QFrame {{ background: {bg}; border-radius: {D.RADIUS_MD}px; border: 1px solid {bdr}; }}
        """)
        row = QHBoxLayout(f)
        row.setContentsMargins(S.SM, S.XXS, S.XS, S.XXS)
        row.setSpacing(S.XS)
        tid = task["id"]

        # Arrows
        aw = QWidget()
        aw.setFixedWidth(16)
        al = QVBoxLayout(aw)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        u = QPushButton("^")
        u.setStyleSheet(btn_icon(14))
        u.setFixedSize(14, 14)
        u.setEnabled(idx > 0)
        u.clicked.connect(lambda _, i=tid: (move_task(i, -1), self.refresh()))
        al.addWidget(u)
        d = QPushButton("v")
        d.setStyleSheet(btn_icon(14))
        d.setFixedSize(14, 14)
        d.setEnabled(idx < total - 1)
        d.clicked.connect(lambda _, i=tid: (move_task(i, 1), self.refresh()))
        al.addWidget(d)
        row.addWidget(aw)

        cb = QCheckBox()
        cb.setChecked(task["done"])
        cb.setStyleSheet(checkbox_style())
        cb.stateChanged.connect(
            lambda s, i=tid: (complete_task(i) if s else uncomplete_task(i), self.refresh()))
        row.addWidget(cb)

        if task.get("priority") == "high":
            p = QLabel("!")
            p.setFont(QFont(F.SANS, F.SM, F.BOLD))
            p.setStyleSheet(f"color: {C.DANGER}; border:none;")
            p.setFixedWidth(12)
            row.addWidget(p)

        lbl = QLabel(task["title"])
        lbl.setFont(QFont(F.SANS, F.SM))
        color = C.TEXT_3 if task["done"] else (C.DANGER if sec == "overdue" else C.TEXT_0)
        deco = "text-decoration: line-through;" if task["done"] else ""
        lbl.setStyleSheet(f"color: {color}; {deco} border:none;")
        row.addWidget(lbl, 1)

        tp = []
        if task.get("due_time"):
            tp.append(task["due_time"])
        if task.get("due_date"):
            tp.append(task["due_date"])
        if tp:
            tl = QLabel("  ".join(tp))
            tl.setFont(QFont(F.MONO, F.XS))
            tl.setStyleSheet(f"color: {C.TEXT_3}; border:none;")
            row.addWidget(tl)

        eb = QPushButton(t("schedule.edit"))
        eb.setStyleSheet(btn_ghost("font-size:10px;"))
        eb.setFixedSize(36, 24)
        eb.setCursor(Qt.CursorShape.PointingHandCursor)
        eb.clicked.connect(lambda _, tk=task: self._edit(tk))
        row.addWidget(eb)

        xb = QPushButton("x")
        xb.setStyleSheet(btn_danger("font-size:11px;"))
        xb.setFixedSize(24, 24)
        xb.setCursor(Qt.CursorShape.PointingHandCursor)
        xb.clicked.connect(lambda _, i=tid: (delete_task(i), self.refresh()))
        row.addWidget(xb)
        return f

    def _sched_next(self, td, today, cur):
        self._refresh_timer.stop()
        up = [t["due_time"] for t in td if t.get("due_time") and t["due_time"] > cur]
        if not up:
            from datetime import datetime as dt, timedelta
            n = dt.now()
            m = (n + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ms = int((m - n).total_seconds() * 1000)
        else:
            from datetime import datetime as dt
            n = dt.now()
            nt = min(up)
            h, mi = map(int, nt.split(":"))
            tgt = n.replace(hour=h, minute=mi, second=0, microsecond=0)
            ms = max(int((tgt - n).total_seconds() * 1000), 1000)
        self._refresh_timer.start(ms)

    def _on_add(self):
        t = self.add_input.text().strip()
        if t:
            add_task(t, priority=self.pri_combo.currentText())
            self.add_input.clear()
            self.refresh()

    def _edit(self, task):
        dlg = EditTaskDialog(task, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.get_values()
            if v["title"]:
                update_task(task["id"], title=v["title"], priority=v["priority"],
                            due_date=v["due_date"], due_time=v["due_time"])
                self.refresh()


# ══════════════════════════════════════════════════════════
#  MemoryPage
# ══════════════════════════════════════════════════════════

class MemoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C.BG_2};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S.XL, S.LG, S.XL, S.LG)
        layout.setSpacing(S.MD)

        add_row = QHBoxLayout()
        add_row.setSpacing(S.SM)
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText(t("memory.add_placeholder"))
        self.add_input.setStyleSheet(input_field())
        self.add_input.returnPressed.connect(self._on_add)
        add_row.addWidget(self.add_input, 1)
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["general", "habit", "preference", "info"])
        self.cat_combo.setStyleSheet(combo_field())
        self.cat_combo.setFixedWidth(100)
        add_row.addWidget(self.cat_combo)
        ab = QPushButton(t("memory.add"))
        ab.setStyleSheet(btn_primary())
        ab.setFixedWidth(60)
        ab.setCursor(Qt.CursorShape.PointingHandCursor)
        ab.clicked.connect(self._on_add)
        add_row.addWidget(ab)
        layout.addLayout(add_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(scrollarea())
        self.container = QWidget()
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items_layout.setSpacing(S.XXS)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

    def _on_add(self):
        t = self.add_input.text().strip()
        if t:
            save_memory(t, self.cat_combo.currentText())
            self.add_input.clear()
            self.refresh()

    def refresh(self):
        while self.items_layout.count():
            w = self.items_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        memories = search_memories("")
        if not memories:
            self.items_layout.addWidget(EmptyState(t("memory.empty")))
            return

        cat_colors = {"habit": C.SUCCESS, "preference": C.PURPLE, "info": C.ACCENT, "general": C.TEXT_3}

        for m in memories:
            f = QFrame()
            f.setStyleSheet(f"""
                QFrame {{ background: {C.BG_3}; border-radius: {D.RADIUS_MD}px; border: 1px solid {C.BORDER_SUB}; }}
            """)
            row = QHBoxLayout(f)
            row.setContentsMargins(S.MD, S.SM, S.XS, S.SM)
            row.setSpacing(S.SM)

            cat = m.get("category", "general")
            cc = cat_colors.get(cat, C.TEXT_3)
            badge = QLabel(cat_name(cat))
            badge.setFont(QFont(F.SANS, F.XS - 1))
            badge.setFixedHeight(18)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qc = QColor(cc)
            badge.setStyleSheet(f"""
                color: {cc}; background: rgba({qc.red()},{qc.green()},{qc.blue()},25);
                border-radius: 4px; padding: 0 6px; border: none;
            """)
            row.addWidget(badge)

            cl = QLabel(m["content"])
            cl.setWordWrap(True)
            cl.setFont(QFont(F.SANS, F.SM))
            cl.setStyleSheet(f"color: {C.TEXT_1}; border:none;")
            cl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(cl, 1)

            eb = QPushButton(t("schedule.edit"))
            eb.setStyleSheet(btn_ghost("font-size:10px;"))
            eb.setFixedSize(36, 24)
            eb.setCursor(Qt.CursorShape.PointingHandCursor)
            eb.clicked.connect(lambda _, mem=m: self._edit(mem))
            row.addWidget(eb)

            xb = QPushButton("x")
            xb.setStyleSheet(btn_danger("font-size:11px;"))
            xb.setFixedSize(24, 24)
            xb.setCursor(Qt.CursorShape.PointingHandCursor)
            xb.clicked.connect(lambda _, mid=m["id"]: (delete_memory(mid), self.refresh()))
            row.addWidget(xb)
            self.items_layout.addWidget(f)

    def _edit(self, mem):
        dlg = EditMemoryDialog(mem, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.get_values()
            if v["content"]:
                update_memory(mem["id"], content=v["content"], category=v["category"])
                self.refresh()


# ══════════════════════════════════════════════════════════
#  IdeasPage
# ══════════════════════════════════════════════════════════

class IdeasPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C.BG_2};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S.XL, S.LG, S.XL, S.LG)
        layout.setSpacing(S.SM)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(scrollarea())
        self.container = QWidget()
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items_layout.setSpacing(S.SM)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

    def refresh(self):
        while self.items_layout.count():
            w = self.items_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        ideas = load_ideas()
        if not ideas:
            self.items_layout.addWidget(EmptyState(t("ideas.empty")))
            return

        sn = {k: t(f"ideas.status.{k}") for k in ["draft", "in_progress", "done", "abandoned"]}
        sc = {"draft": C.TEXT_3, "in_progress": C.WARNING, "done": C.SUCCESS, "abandoned": C.TEXT_3}

        for idea in ideas:
            f = QFrame()
            f.setStyleSheet(f"QFrame {{ background: {C.BG_3}; border-radius: {D.RADIUS_LG}px; border: 1px solid {C.BORDER_SUB}; }}")
            col = QVBoxLayout(f)
            col.setContentsMargins(S.MD, S.SM, S.MD, S.SM)
            col.setSpacing(S.XS)

            hdr = QHBoxLayout()
            ti = QLabel(idea.get("title", "Untitled"))
            ti.setFont(QFont(F.SANS, F.MD, F.SEMIBOLD))
            ti.setStyleSheet(f"color: {C.TEXT_0}; border:none;")
            hdr.addWidget(ti, 1)

            st = idea.get("status", "draft")
            stc = sc.get(st, C.TEXT_3)
            qc = QColor(stc)
            sb = QLabel(sn.get(st, st))
            sb.setFont(QFont(F.SANS, F.XS))
            sb.setStyleSheet(f"color: {stc}; background: rgba({qc.red()},{qc.green()},{qc.blue()},25); border-radius: 4px; padding: 2px 6px; border:none;")
            hdr.addWidget(sb)

            xb = QPushButton("x")
            xb.setStyleSheet(btn_danger("font-size:11px;"))
            xb.setFixedSize(24, 24)
            xb.setCursor(Qt.CursorShape.PointingHandCursor)
            xb.clicked.connect(lambda _, iid=idea["id"]: (delete_idea(iid), self.refresh()))
            hdr.addWidget(xb)
            col.addLayout(hdr)

            if idea.get("summary"):
                s = QLabel(idea["summary"][:200])
                s.setWordWrap(True)
                s.setFont(QFont(F.SANS, F.SM))
                s.setStyleSheet(f"color: {C.TEXT_2}; border:none;")
                s.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                col.addWidget(s)
            self.items_layout.addWidget(f)


# ══════════════════════════════════════════════════════════
#  SettingsPage
# ══════════════════════════════════════════════════════════

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C.BG_2};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(S.XL, S.LG, S.XL, S.LG)
        layout.setSpacing(S.MD)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(scrollarea())
        self.container = QWidget()
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.items_layout.setSpacing(S.XXS)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)
        self._cbs = {}

    def refresh(self):
        while self.items_layout.count():
            w = self.items_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        self._cbs.clear()

        # Language selector
        gl = QLabel(t("nav.settings").upper())
        gl.setFont(QFont(F.SANS, F.XS, F.SEMIBOLD))
        gl.setStyleSheet(f"color: {C.TEXT_3}; letter-spacing: 1px; padding-top: 8px;")
        self.items_layout.addWidget(gl)

        lang_frame = QFrame()
        lang_frame.setMinimumHeight(48)
        lang_frame.setStyleSheet(
            f"QFrame {{ background: {C.BG_3}; border-radius: {D.RADIUS_MD}px; "
            f"border: 1px solid {C.BORDER_SUB}; }}")
        lr = QHBoxLayout(lang_frame)
        lr.setContentsMargins(S.MD, S.XS, S.MD, S.XS)
        li = QVBoxLayout()
        li.setSpacing(0)
        ln = QLabel(t("settings.language"))
        ln.setFont(QFont(F.SANS, F.SM))
        ln.setStyleSheet(f"color: {C.TEXT_0}; border:none;")
        li.addWidget(ln)
        ld = QLabel(t("settings.language_desc"))
        ld.setFont(QFont(F.SANS, F.XS))
        ld.setStyleSheet(f"color: {C.TEXT_3}; border:none;")
        li.addWidget(ld)
        lr.addLayout(li, 1)
        lang_combo = QComboBox()
        lang_combo.addItems(["zh", "en"])
        lang_combo.setCurrentText(get_language())
        lang_combo.setStyleSheet(combo_field())
        lang_combo.setFixedWidth(70)
        lang_combo.currentTextChanged.connect(self._on_lang_change)
        lr.addWidget(lang_combo)
        self.items_layout.addWidget(lang_frame)

        cur_grp = None
        for key, pd in PERMISSION_DEFS.items():
            grp = pd.get("group", "")
            if grp != cur_grp:
                cur_grp = grp
                gl = QLabel(grp)
                gl.setFont(QFont(F.SANS, F.XS, F.SEMIBOLD))
                gl.setStyleSheet(f"color: {C.TEXT_3}; letter-spacing: 1px; padding-top: 8px;")
                self.items_layout.addWidget(gl)

            f = QFrame()
            f.setMinimumHeight(48)
            f.setStyleSheet(f"QFrame {{ background: {C.BG_3}; border-radius: {D.RADIUS_MD}px; border: 1px solid {C.BORDER_SUB}; }}")
            row = QHBoxLayout(f)
            row.setContentsMargins(S.MD, S.XS, S.MD, S.XS)
            info = QVBoxLayout()
            info.setSpacing(0)
            nm = QLabel(pd["name"])
            nm.setFont(QFont(F.SANS, F.SM))
            nm.setStyleSheet(f"color: {C.TEXT_0}; border:none;")
            info.addWidget(nm)
            ds = QLabel(pd.get("description", ""))
            ds.setFont(QFont(F.SANS, F.XS))
            ds.setStyleSheet(f"color: {C.TEXT_3}; border:none;")
            info.addWidget(ds)
            row.addLayout(info, 1)

            cb = QCheckBox()
            cb.setChecked(get_permission(key))
            cb.setStyleSheet(toggle_style())
            cb.stateChanged.connect(lambda s, k=key: set_permission(k, bool(s)))
            row.addWidget(cb)
            self._cbs[key] = cb
            self.items_layout.addWidget(f)

    def _on_lang_change(self, lang):
        set_language(lang)
        mw = self.window()
        if hasattr(mw, '_refresh_lang'):
            mw._refresh_lang()


# ══════════════════════════════════════════════════════════
#  MainWindow
# ══════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    toggle_signal = pyqtSignal()
    reminder_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.engine = AgentEngine()
        self.nav_btns = []
        self._notified = set()
        self._build()
        self._setup_tray()
        self._setup_hotkey()
        self._setup_timers()
        self.chat_page.load_history()
        self._switch(0)

    def _build(self):
        self.setWindowTitle("Assistance")
        self.setMinimumSize(D.MIN_W, D.MIN_H)
        self.resize(1100, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = QFrame()
        sidebar.setFixedWidth(D.SIDEBAR_W)
        sidebar.setStyleSheet(f"QFrame {{ background: {C.BG_1}; border-right: 1px solid {C.BORDER_SUB}; }}")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(S.SM, S.LG, S.SM, S.SM)
        sl.setSpacing(S.XXS)

        # Brand
        brand_row = QHBoxLayout()
        brand_row.setSpacing(S.XS)
        brand_row.setContentsMargins(S.SM, 0, 0, 0)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._brand_icon())
        brand_row.addWidget(icon_lbl)
        brand_text = QLabel("Assistance")
        brand_text.setFont(QFont(F.SANS, F.LG, F.SEMIBOLD))
        brand_text.setStyleSheet(f"color: {C.TEXT_0};")
        brand_row.addWidget(brand_text)
        brand_row.addStretch()
        sl.addLayout(brand_row)
        sl.addSpacing(S.LG)

        # Nav
        _nav_keys = ["nav.chat", "nav.schedule", "nav.memory", "nav.ideas", "nav.settings"]
        for i, key in enumerate(_nav_keys):
            b = SidebarNavItem(t(key))
            b.clicked.connect(lambda _, idx=i: self._switch(idx))
            sl.addWidget(b)
            self.nav_btns.append(b)

        sl.addStretch()

        # Bottom status
        self.sidebar_status = AgentStatus()
        sl.addWidget(self.sidebar_status)

        root.addWidget(sidebar)

        # ── Main area ──
        main_col = QVBoxLayout()
        main_col.setContentsMargins(0, 0, 0, 0)
        main_col.setSpacing(0)

        # Topbar
        topbar = QFrame()
        topbar.setFixedHeight(D.TOPBAR_H)
        topbar.setStyleSheet(f"background: {C.BG_2}; border-bottom: 1px solid {C.BORDER_SUB};")
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(S.LG, 0, S.LG, 0)
        self.page_title = QLabel(t("nav.chat"))
        self.page_title.setFont(QFont(F.SANS, F.MD, F.SEMIBOLD))
        self.page_title.setStyleSheet(f"color: {C.TEXT_0};")
        tb_layout.addWidget(self.page_title)
        tb_layout.addStretch()

        self.clear_btn = QPushButton(t("chat.clear"))
        self.clear_btn.setStyleSheet(btn_ghost("font-size: 11px;"))
        self.clear_btn.setFixedHeight(D.BTN_SM)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear)
        tb_layout.addWidget(self.clear_btn)
        main_col.addWidget(topbar)

        # Stack
        self.stack = QStackedWidget()
        self.chat_page = ChatPage(self.engine)
        self.schedule_page = SchedulePage()
        self.memory_page = MemoryPage()
        self.ideas_page = IdeasPage()
        self.settings_page = SettingsPage()
        for p in [self.chat_page, self.schedule_page, self.memory_page, self.ideas_page, self.settings_page]:
            self.stack.addWidget(p)
        main_col.addWidget(self.stack, 1)
        root.addLayout(main_col, 1)

    def _brand_icon(self):
        px = QPixmap(28, 28)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(C.ACCENT))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, 24, 24, 7, 7)
        p.setPen(QColor(C.BG_0))
        p.setFont(QFont(F.SANS, 14, F.BOLD))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        p.end()
        return px

    _PAGE_KEYS = ["nav.chat", "nav.schedule", "nav.memory", "nav.ideas", "nav.settings"]

    def _refresh_lang(self):
        for i, key in enumerate(self._PAGE_KEYS):
            self.nav_btns[i].setText(f"    {t(key)}")
        cur = self.stack.currentIndex()
        self.page_title.setText(t(self._PAGE_KEYS[cur]))
        self.clear_btn.setText(t("chat.clear"))

    def _switch(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.set_active(i == idx)
        self.page_title.setText(t(self._PAGE_KEYS[idx]))
        self.clear_btn.setVisible(idx == 0)
        refreshers = [None, self.schedule_page.refresh, self.memory_page.refresh,
                      self.ideas_page.refresh, self.settings_page.refresh]
        if idx > 0 and refreshers[idx]:
            refreshers[idx]()

    def _clear(self):
        self.chat_page.clear_chat()

    # ── Tray ──
    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        px = QPixmap(64, 64)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(C.ACCENT))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 4, 56, 56, 16, 16)
        p.setPen(QColor(C.BG_0))
        p.setFont(QFont(F.SANS, 28, F.BOLD))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        p.end()
        self.tray.setIcon(QIcon(px))
        self.tray.setToolTip("Assistance")
        menu = QMenu()
        sa = QAction(t("tray.show"), self)
        sa.triggered.connect(self._show_window)
        menu.addAction(sa)
        menu.addSeparator()
        qa = QAction(t("tray.quit"), self)
        qa.triggered.connect(QApplication.quit)
        menu.addAction(qa)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self._show_window() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    # ── Hotkey ──
    def _setup_hotkey(self):
        self.toggle_signal.connect(self._toggle_window)
        pressed = set()

        def _has_ctrl():
            return kb.Key.ctrl_l in pressed or kb.Key.ctrl_r in pressed

        def _has_alt():
            return kb.Key.alt_l in pressed or kb.Key.alt_r in pressed

        def on_press(key):
            pressed.add(key)
            if _has_ctrl() and _has_alt():
                is_a = (hasattr(key, 'char') and key.char == 'a') or \
                       (hasattr(key, 'vk') and key.vk == 65)
                if is_a:
                    self.toggle_signal.emit()

        def on_release(key):
            pressed.discard(key)

        listener = kb.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

    def _toggle_window(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Timers ──
    def _setup_timers(self):
        self.reminder_signal.connect(self._handle_reminder)
        from system_tools import set_reminder_callback
        set_reminder_callback(self._on_reminder_fired)
        QTimer.singleShot(800, self._daily_briefing)
        self._rem_timer = QTimer(self)
        self._rem_timer.timeout.connect(self._check_reminders)
        self._rem_timer.start(5 * 60 * 1000)

    def _daily_briefing(self):
        def _run():
            from smart_notify import gen_greeting
            msg = gen_greeting()
            if msg:
                QTimer.singleShot(0, lambda: self.chat_page._add_bubble(msg, False))
        threading.Thread(target=_run, daemon=True).start()

    def _check_reminders(self):
        from schedule import load_tasks as _ld
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = _ld()
        due = [tk for tk in tasks if tk.get("due_date") and tk["due_date"] <= today and not tk["done"] and tk["id"] not in self._notified]
        if due:
            for tk in due:
                self._notified.add(tk["id"])
            titles = "\n".join(f"- {tk['title']}" for tk in due[:5])
            self.tray.showMessage(
                t("tray.tasks"),
                f"{len(due)} pending:\n{titles}",
                QSystemTrayIcon.MessageIcon.Information, 5000)

        now_str = datetime.now().strftime("%H:%M")
        now_m = int(now_str[:2]) * 60 + int(now_str[3:])
        for tk in [tk for tk in tasks if tk.get("due_date") == today and not tk["done"] and tk.get("due_time")]:
            nk = f"t_{tk['id']}"
            if nk in self._notified:
                continue
            try:
                h, m = map(int, tk["due_time"].split(":"))
                diff = h * 60 + m - now_m
                if 0 <= diff <= 10:
                    self._notified.add(nk)
                    tc = dict(tk)
                    def _go(task=tc, dl=diff):
                        from smart_notify import gen_pre_task_reminder
                        msg = gen_pre_task_reminder(task) or f"{task['title']} in {dl}min"
                        QTimer.singleShot(0, lambda: (
                            self.tray.showMessage(
                                t("tray.upcoming"), msg,
                                QSystemTrayIcon.MessageIcon.Information, 8000),
                            self.chat_page._add_bubble(msg, False),
                        ))
                    threading.Thread(target=_go, daemon=True).start()
            except (ValueError, AttributeError):
                continue

    def _on_reminder_fired(self, message, time_str):
        self.reminder_signal.emit(message, time_str)

    def _handle_reminder(self, message, time_str):
        self.tray.showMessage(
            f"{t('tray.reminder')} [{time_str}]", message,
            QSystemTrayIcon.MessageIcon.Information, 8000)
        self.chat_page._add_bubble(f"[Reminder] {message}", False)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("Assistance", t("tray.minimized"),
                              QSystemTrayIcon.MessageIcon.Information, 2000)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(global_style())
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
