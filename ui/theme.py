"""Assistance Design System — Visual Tokens

Minimal, premium dark theme inspired by Linear / Raycast / Vercel.
All visual constants centralized here. No magic numbers elsewhere.
"""


class C:
    """Color palette. Layered depth backgrounds with restrained accent."""
    # Backgrounds — ordered by depth (darker = deeper)
    BG_0         = "#090B10"   # Window / deepest
    BG_1         = "#0D1018"   # Sidebar
    BG_2         = "#10141E"   # Content area
    BG_3         = "#151B27"   # Cards, elevated panels
    BG_4         = "#1D2634"   # Hover, active states
    BG_INPUT     = "#111822"   # Input fields

    # Text — four-level hierarchy
    TEXT_0       = "#F1F4FA"   # Primary headings & body
    TEXT_1       = "#C7D0DE"   # Secondary body
    TEXT_2       = "#A0ABBC"   # Tertiary, labels
    TEXT_3       = "#6F7D91"   # Muted, placeholders, disabled

    # Borders — minimal, used sparingly
    BORDER       = "#252D3B"   # Standard
    BORDER_SUB   = "#1C2433"   # Subtle dividers
    BORDER_FOCUS = "#6EA8FF"   # Focus rings

    # Accent
    ACCENT       = "#6EA8FF"   # Primary blue
    ACCENT_DIM   = "#5B91E0"   # Hover variant
    PURPLE       = "#9B8CFF"   # Secondary accent
    SUCCESS      = "#4DD4AC"   # Online, done
    WARNING      = "#FFBF69"   # Caution, in-progress
    DANGER       = "#FF6B85"   # Error, delete, overdue

    # Chat bubbles — subtle differentiation through background only
    BUBBLE_USER  = "#161D2B"
    BUBBLE_AI    = "#111822"

    # Transparent
    HOVER        = "rgba(110, 168, 255, 0.06)"
    ACTIVE       = "rgba(110, 168, 255, 0.10)"
    GLOW         = "rgba(110, 168, 255, 0.08)"


class S:
    """Spacing scale (px)."""
    XXS  = 4
    XS   = 8
    SM   = 12
    MD   = 16
    LG   = 24
    XL   = 32
    XXL  = 48


class F:
    """Typography."""
    SANS   = "Segoe UI"
    MONO   = "Cascadia Code"
    FALLBACK = "Microsoft YaHei"

    # Sizes
    XS   = 10
    SM   = 11
    BASE = 13
    MD   = 14
    LG   = 16
    XL   = 20
    XXL  = 26

    # Weights
    REGULAR  = 400
    MEDIUM   = 500
    SEMIBOLD = 600
    BOLD     = 700


class D:
    """Dimensions."""
    BTN_SM      = 30
    BTN_MD      = 36
    BTN_LG      = 42
    INPUT_H     = 40
    RADIUS_SM   = 6
    RADIUS_MD   = 8
    RADIUS_LG   = 12
    RADIUS_XL   = 16
    SIDEBAR_W   = 224
    TOPBAR_H    = 56
    MIN_W       = 960
    MIN_H       = 640
    CONTENT_MAX = 780  # Max content width for readability
