"""Qt stylesheet generators. All reference design tokens from theme.py."""

from .theme import C, S, F, D


def global_style():
    return f"""
        * {{ outline: none; }}
        QMainWindow, QWidget {{
            background-color: {C.BG_0};
            color: {C.TEXT_0};
            font-family: "{F.SANS}", "{F.FALLBACK}", sans-serif;
            font-size: {F.BASE}px;
        }}
        QToolTip {{
            background-color: {C.BG_3};
            color: {C.TEXT_0};
            border: 1px solid {C.BORDER};
            padding: 4px 8px;
        }}
    """


# ── Buttons ───────────────────────────────────────────────

def btn_primary(extra=""):
    return f"""
        QPushButton {{
            background-color: {C.ACCENT};
            color: {C.BG_0};
            border: none;
            border-radius: {D.RADIUS_MD}px;
            padding: 0 {S.MD}px;
            font-weight: {F.SEMIBOLD};
            min-height: {D.BTN_MD}px;
            {extra}
        }}
        QPushButton:hover {{ background-color: {C.ACCENT_DIM}; }}
        QPushButton:pressed {{ background-color: {C.ACCENT_DIM}; padding-top: 1px; }}
        QPushButton:disabled {{ background-color: {C.BORDER}; color: {C.TEXT_3}; }}
    """


def btn_secondary(extra=""):
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {C.TEXT_1};
            border: 1px solid {C.BORDER};
            border-radius: {D.RADIUS_MD}px;
            padding: 0 {S.SM}px;
            min-height: {D.BTN_SM}px;
            {extra}
        }}
        QPushButton:hover {{ border-color: {C.ACCENT}; color: {C.ACCENT}; }}
        QPushButton:pressed {{ background-color: {C.ACTIVE}; }}
        QPushButton:disabled {{ color: {C.TEXT_3}; border-color: {C.BORDER_SUB}; }}
    """


def btn_ghost(extra=""):
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {C.TEXT_3};
            border: none;
            border-radius: {D.RADIUS_SM}px;
            padding: 0 {S.XS}px;
            min-height: {D.BTN_SM}px;
            {extra}
        }}
        QPushButton:hover {{ color: {C.TEXT_1}; background-color: {C.HOVER}; }}
        QPushButton:pressed {{ background-color: {C.ACTIVE}; }}
    """


def btn_danger(extra=""):
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {C.TEXT_3};
            border: none;
            border-radius: {D.RADIUS_SM}px;
            min-height: {D.BTN_SM}px;
            {extra}
        }}
        QPushButton:hover {{ color: {C.DANGER}; background-color: rgba(255,107,133,0.10); }}
    """


def btn_icon(sz=28):
    return f"""
        QPushButton {{
            background: transparent; color: {C.TEXT_3}; border: none;
            border-radius: {sz//2}px;
            min-width: {sz}px; max-width: {sz}px;
            min-height: {sz}px; max-height: {sz}px;
        }}
        QPushButton:hover {{ color: {C.TEXT_1}; background: {C.HOVER}; }}
        QPushButton:disabled {{ color: {C.BORDER}; }}
    """


# ── Inputs ────────────────────────────────────────────────

def input_field():
    return f"""
        QLineEdit {{
            background-color: {C.BG_INPUT};
            color: {C.TEXT_0};
            border: 1px solid {C.BORDER};
            border-radius: {D.RADIUS_MD}px;
            padding: {S.XS}px {S.SM}px;
            min-height: {D.INPUT_H}px;
            selection-background-color: rgba(110,168,255,0.25);
        }}
        QLineEdit:focus {{ border-color: {C.BORDER_FOCUS}; }}
        QLineEdit:disabled {{ color: {C.TEXT_3}; }}
    """


def textedit_field():
    return f"""
        QTextEdit {{
            background-color: {C.BG_INPUT};
            color: {C.TEXT_0};
            border: 1px solid {C.BORDER};
            border-radius: {D.RADIUS_MD}px;
            padding: {S.XS}px {S.SM}px;
            selection-background-color: rgba(110,168,255,0.25);
        }}
        QTextEdit:focus {{ border-color: {C.BORDER_FOCUS}; }}
    """


def combo_field():
    return f"""
        QComboBox {{
            background-color: {C.BG_INPUT};
            color: {C.TEXT_0};
            border: 1px solid {C.BORDER};
            border-radius: {D.RADIUS_MD}px;
            padding: {S.XXS}px {S.SM}px;
            min-height: {D.BTN_SM}px;
        }}
        QComboBox:hover {{ border-color: {C.ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox::down-arrow {{ image: none; }}
        QComboBox QAbstractItemView {{
            background-color: {C.BG_3};
            color: {C.TEXT_0};
            border: 1px solid {C.BORDER};
            selection-background-color: {C.BG_4};
            outline: none;
        }}
    """


# ── Surfaces ──────────────────────────────────────────────

def card_surface():
    return f"""
        QFrame {{
            background-color: {C.BG_3};
            border-radius: {D.RADIUS_LG}px;
            border: 1px solid {C.BORDER_SUB};
        }}
    """


def checkbox_style():
    return f"""
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border: 1.5px solid {C.TEXT_3};
            border-radius: {D.RADIUS_SM - 2}px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {C.ACCENT};
            border-color: {C.ACCENT};
        }}
        QCheckBox::indicator:hover {{ border-color: {C.ACCENT}; }}
    """


def toggle_style():
    return f"""
        QCheckBox::indicator {{
            width: 34px; height: 18px;
            border-radius: 9px;
            background-color: {C.BG_4};
            border: none;
        }}
        QCheckBox::indicator:checked {{ background-color: {C.ACCENT}; }}
        QCheckBox::indicator:hover {{ background-color: {C.BORDER}; }}
        QCheckBox::indicator:checked:hover {{ background-color: {C.ACCENT_DIM}; }}
    """


def scrollarea():
    return f"""
        QScrollArea {{ border: none; background: transparent; }}
        QScrollBar:vertical {{
            width: 5px; background: transparent; margin: 2px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {C.BORDER}; border-radius: 2px; min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {C.TEXT_3}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    """


def dialog_style():
    return f"""
        QDialog {{
            background-color: {C.BG_3};
            color: {C.TEXT_0};
        }}
    """
