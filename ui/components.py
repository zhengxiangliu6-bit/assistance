"""Reusable UI components for the Assistance workspace."""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QHBoxLayout, QVBoxLayout,
    QPushButton, QSizePolicy, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QKeyEvent, QPixmap

from .theme import C, S, F, D
from .animations import StatusDot


# ── Sidebar Nav Item ──────────────────────────────────────

class SidebarNavItem(QPushButton):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setText(f"    {label}")
        self.setFixedHeight(D.BTN_LG)
        self.setCheckable(True)
        self.setFont(QFont(F.SANS, F.SM))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_active(False)

    def set_active(self, active):
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C.ACTIVE};
                    color: {C.TEXT_0};
                    border: none; border-radius: {D.RADIUS_MD}px;
                    border-left: 2px solid {C.ACCENT};
                    text-align: left; padding-left: {S.SM}px;
                    font-weight: {F.MEDIUM};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {C.TEXT_3};
                    border: none; border-radius: {D.RADIUS_MD}px;
                    border-left: 2px solid transparent;
                    text-align: left; padding-left: {S.SM}px;
                }}
                QPushButton:hover {{
                    background-color: {C.HOVER};
                    color: {C.TEXT_1};
                }}
            """)


# ── Message Bubble ────────────────────────────────────────

class MessageBubble(QFrame):
    def __init__(self, text, is_user, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setFont(QFont(F.SANS, F.BASE))
        self.label.setText(text)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setMinimumWidth(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(S.LG, S.XXS, S.LG, S.XXS)

        if is_user:
            layout.addStretch()
            self.label.setStyleSheet(f"""
                background-color: {C.BUBBLE_USER};
                color: {C.TEXT_0};
                border-radius: {D.RADIUS_LG}px;
                border-bottom-right-radius: {D.RADIUS_SM}px;
                padding: {S.SM}px {S.MD}px;
                border: 1px solid {C.BORDER_SUB};
            """)
            self.label.setMaximumWidth(500)
            layout.addWidget(self.label)
        else:
            self.label.setStyleSheet(f"""
                background-color: {C.BUBBLE_AI};
                color: {C.TEXT_1};
                border-radius: {D.RADIUS_LG}px;
                border-bottom-left-radius: {D.RADIUS_SM}px;
                padding: {S.SM}px {S.MD}px;
                border: 1px solid {C.BORDER_SUB};
            """)
            self.label.setMaximumWidth(560)
            layout.addWidget(self.label)
            layout.addStretch()

    def append_text(self, text):
        self.label.setText(self.label.text() + text)

    def set_text(self, text):
        self.label.setText(text)


# ── Agent Status Indicator ────────────────────────────────

class AgentStatus(QWidget):
    STATES = {
        "idle":      ("Ready", C.TEXT_3, C.SUCCESS),
        "thinking":  ("Thinking...", C.WARNING, C.WARNING),
        "tool":      ("Running tool", C.PURPLE, C.PURPLE),
        "streaming": ("Generating...", C.ACCENT, C.ACCENT),
        "error":     ("Error", C.DANGER, C.DANGER),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S.XS)

        self.dot = StatusDot(C.SUCCESS, 6)
        layout.addWidget(self.dot)

        self.label = QLabel("Ready")
        self.label.setFont(QFont(F.MONO, F.XS))
        self.label.setStyleSheet(f"color: {C.TEXT_3};")
        layout.addWidget(self.label)

        self.detail = QLabel("")
        self.detail.setFont(QFont(F.SANS, F.XS))
        self.detail.setStyleSheet(f"color: {C.TEXT_3};")
        layout.addWidget(self.detail)
        layout.addStretch()

    def set_state(self, state, detail=""):
        info = self.STATES.get(state, self.STATES["idle"])
        text, text_color, dot_color = info
        self.label.setText(text)
        self.label.setStyleSheet(f"color: {text_color};")
        self.dot.set_color(dot_color)
        self.detail.setText(detail)


# ── Composer (multi-line input) ───────────────────────────

class ChatComposer(QFrame):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C.BG_INPUT};
                border: 1px solid {C.BORDER};
                border-radius: {D.RADIUS_XL}px;
                margin: {S.XS}px {S.LG}px {S.MD}px {S.LG}px;
            }}
            QFrame:focus-within {{
                border-color: {C.BORDER_FOCUS};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S.MD, S.SM, S.SM, S.SM)
        layout.setSpacing(S.XXS)

        self.text_edit = ComposerTextEdit()
        self.text_edit.setPlaceholderText("Message Assistance...")
        self.text_edit.setFont(QFont(F.SANS, F.BASE))
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                color: {C.TEXT_0};
                border: none;
                selection-background-color: rgba(110,168,255,0.25);
            }}
        """)
        self.text_edit.setMinimumHeight(28)
        self.text_edit.setMaximumHeight(120)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.submit_signal.connect(self._submit)
        layout.addWidget(self.text_edit)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, S.XXS, 0)
        bottom.addStretch()

        self.send_btn = QPushButton()
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C.ACCENT};
                border: none;
                border-radius: 16px;
                color: {C.BG_0};
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {C.ACCENT_DIM}; }}
            QPushButton:disabled {{ background-color: {C.BORDER}; color: {C.TEXT_3}; }}
        """)
        self.send_btn.setText("\u2191")  # up arrow
        self.send_btn.clicked.connect(self._submit)
        bottom.addWidget(self.send_btn)
        layout.addLayout(bottom)

    def _submit(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            self.submitted.emit(text)
            self.text_edit.clear()

    def set_enabled(self, enabled):
        self.text_edit.setReadOnly(not enabled)
        self.send_btn.setEnabled(enabled)
        if enabled:
            self.text_edit.setFocus()

    def text(self):
        return self.text_edit.toPlainText().strip()


class ComposerTextEdit(QTextEdit):
    submit_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            elif not self._is_composing():
                self.submit_signal.emit()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _is_composing(self):
        return self.inputMethodQuery(Qt.InputMethodQuery.ImEnabled) and \
               bool(self.inputMethodQuery(Qt.InputMethodQuery.ImSurroundingText) == "")


# ── Section Header ────────────────────────────────────────

class SectionHeader(QWidget):
    def __init__(self, title, count=0, color=C.TEXT_2, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(S.XXS, S.XS, 0, 0)
        layout.setSpacing(S.XS)

        lbl = QLabel(title)
        lbl.setFont(QFont(F.SANS, F.XS, F.SEMIBOLD))
        lbl.setStyleSheet(f"color: {color};")
        layout.addWidget(lbl)

        if count > 0:
            badge = QLabel(str(count))
            badge.setFont(QFont(F.MONO, F.XS - 1))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(20, 16)
            badge.setStyleSheet(f"""
                background-color: {C.BG_4};
                color: {C.TEXT_3};
                border-radius: 8px;
            """)
            layout.addWidget(badge)

        layout.addStretch()


# ── Empty State ───────────────────────────────────────────

class EmptyState(QWidget):
    def __init__(self, text="Nothing here yet", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, S.XXL, 0, S.XXL)
        lbl = QLabel(text)
        lbl.setFont(QFont(F.SANS, F.SM))
        lbl.setStyleSheet(f"color: {C.TEXT_3};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)


# ── Welcome View ──────────────────────────────────────────

class ChatWelcomeView(QWidget):
    quick_action = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(S.MD)

        # AI icon
        icon = QLabel()
        px = self._make_icon()
        icon.setPixmap(px)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        layout.addSpacing(S.XS)

        title = QLabel("What can I help you with?")
        title.setFont(QFont(F.SANS, F.XL, F.SEMIBOLD))
        title.setStyleSheet(f"color: {C.TEXT_0};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Your personal AI workspace.")
        sub.setFont(QFont(F.SANS, F.SM))
        sub.setStyleSheet(f"color: {C.TEXT_3};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
        layout.addSpacing(S.MD)

        # Quick actions
        actions_row = QHBoxLayout()
        actions_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        actions_row.setSpacing(S.SM)

        quick_items = [
            ("Plan my day", "帮我安排一下今天的日程"),
            ("Review tasks", "我今天有什么待办事项？"),
            ("Search memory", "你还记得我的作息习惯吗？"),
            ("Capture idea", "我有一个新的想法想分析一下"),
        ]

        for label, prompt in quick_items:
            btn = QPushButton(label)
            btn.setFont(QFont(F.SANS, F.SM))
            btn.setFixedHeight(D.BTN_MD)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C.BG_3};
                    color: {C.TEXT_2};
                    border: 1px solid {C.BORDER};
                    border-radius: {D.RADIUS_MD}px;
                    padding: 0 {S.MD}px;
                }}
                QPushButton:hover {{
                    background-color: {C.BG_4};
                    color: {C.TEXT_0};
                    border-color: {C.ACCENT};
                }}
            """)
            btn.clicked.connect(lambda _, t=prompt: self.quick_action.emit(t))
            actions_row.addWidget(btn)

        layout.addLayout(actions_row)

    def _make_icon(self):
        px = QPixmap(48, 48)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(C.ACCENT))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 4, 40, 40, 12, 12)
        p.setPen(QColor(C.BG_0))
        p.setFont(QFont(F.SANS, 20, F.BOLD))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        p.end()
        return px
