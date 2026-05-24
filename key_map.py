"""
Mapping from pynput normalized key names to:
  1. PowerShell SendKeys format (for tap keys)
  2. Windows Virtual Key codes     (for hold/long-press keys)

Returns None for keys that cannot be sent standalone.
"""

# Characters that have special meaning in SendKeys and must be escaped
_SENDKEYS_ESCAPE_CHARS = {
    '+': '{+}',
    '^': '{^}',
    '%': '{%}',
    '~': '{~}',
    '(': '{(}',
    ')': '{)}',
    '{': '{{}',
    '}': '{}}',
}

# Named keys -> SendKeys representation
_SENDKEYS_NAMED = {
    'enter':      '{ENTER}',
    'tab':        '{TAB}',
    'space':      ' ',
    'backspace':  '{BS}',
    'delete':     '{DELETE}',
    'esc':        '{ESC}',
    'escape':     '{ESC}',
    'up':         '{UP}',
    'down':       '{DOWN}',
    'left':       '{LEFT}',
    'right':      '{RIGHT}',
    'home':       '{HOME}',
    'end':        '{END}',
    'page_up':    '{PGUP}',
    'page_down':  '{PGDN}',
    'insert':     '{INSERT}',
    'print_screen': '{PRTSC}',
    'f1':  '{F1}',  'f2':  '{F2}',  'f3':  '{F3}',  'f4':  '{F4}',
    'f5':  '{F5}',  'f6':  '{F6}',  'f7':  '{F7}',  'f8':  '{F8}',
    'f9':  '{F9}',  'f10': '{F10}', 'f11': '{F11}', 'f12': '{F12}',
    'f13': '{F13}', 'f14': '{F14}', 'f15': '{F15}', 'f16': '{F16}',
    'num_lock':    '{NUMLOCK}',
    'scroll_lock': '{SCROLLLOCK}',
    'caps_lock':   '{CAPSLOCK}',
    'pause':       '{BREAK}',
    'decimal':     '{DECIMAL}',
    'add':         '{ADD}',
    'subtract':    '{SUBTRACT}',
    'multiply':    '{MULTIPLY}',
    'divide':      '{DIVIDE}',
    'num_0': '{NUMPAD0}', 'num_1': '{NUMPAD1}', 'num_2': '{NUMPAD2}',
    'num_3': '{NUMPAD3}', 'num_4': '{NUMPAD4}', 'num_5': '{NUMPAD5}',
    'num_6': '{NUMPAD6}', 'num_7': '{NUMPAD7}', 'num_8': '{NUMPAD8}',
    'num_9': '{NUMPAD9}',
}

# Named keys -> Windows Virtual Key code (hex)
_VK_NAMED = {
    'enter':       0x0D,
    'tab':         0x09,
    'space':       0x20,
    'backspace':   0x08,
    'delete':      0x2E,
    'esc':         0x1B,
    'escape':      0x1B,
    'up':          0x26,
    'down':        0x28,
    'left':        0x25,
    'right':       0x27,
    'home':        0x24,
    'end':         0x23,
    'page_up':     0x21,
    'page_down':   0x22,
    'insert':      0x2D,
    'print_screen': 0x2C,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    'f13': 0x7C, 'f14': 0x7D, 'f15': 0x7E, 'f16': 0x7F,
    'num_lock':    0x90,
    'scroll_lock': 0x91,
    'caps_lock':   0x14,
    'pause':       0x13,
    'decimal':     0x6E,
    'add':         0x6B,
    'subtract':    0x6D,
    'multiply':    0x6A,
    'divide':      0x6F,
    'num_0': 0x60, 'num_1': 0x61, 'num_2': 0x62,
    'num_3': 0x63, 'num_4': 0x64, 'num_5': 0x65,
    'num_6': 0x66, 'num_7': 0x67, 'num_8': 0x68,
    'num_9': 0x69,
    'apps':            0x5D,
    'sleep':           0x5F,
    'browser_back':    0xA6,
    'browser_forward': 0xA7,
    'browser_refresh': 0xA8,
    'browser_stop':    0xA9,
    'browser_search':  0xAA,
    'browser_favorites': 0xAB,
    'browser_home':    0xAC,
    'volume_mute':     0xAD,
    'volume_down':     0xAE,
    'volume_up':       0xAF,
    'media_next':      0xB0,
    'media_prev':      0xB1,
    'media_stop':      0xB2,
    'media_play':      0xB3,
    'launch_mail':     0xB4,
    'launch_media':    0xB5,
    'launch_app1':     0xB6,
    'launch_app2':     0xB7,
}

# Punctuation characters: ASCII ≠ VK code, need explicit mapping
_VK_PUNCTUATION = {
    '-': 0xBD,  # VK_OEM_MINUS
    '=': 0xBB,  # VK_OEM_PLUS
    '[': 0xDB,  # VK_OEM_4
    ']': 0xDD,  # VK_OEM_6
    '\\': 0xDC, # VK_OEM_5
    ';': 0xBA,  # VK_OEM_1
    '\'': 0xDE, # VK_OEM_7
    ',': 0xBC,  # VK_OEM_COMMA
    '.': 0xBE,  # VK_OEM_PERIOD
    '/': 0xBF,  # VK_OEM_2
    '`': 0xC0,  # VK_OEM_3
}

# Keys that should be skipped in generated scripts (modifiers)
_SKIP_KEYS = {
    'shift', 'shift_l', 'shift_r',
    'ctrl', 'ctrl_l', 'ctrl_r',
    'alt', 'alt_l', 'alt_r', 'alt_gr',
    'cmd', 'cmd_l', 'cmd_r',
    'media_volume_up', 'media_volume_down', 'media_volume_mute',
    'media_play_pause', 'media_next', 'media_previous',
    'scroll_lock',
}


def to_sendkeys(key_name: str) -> str | None:
    """
    Convert a normalized key name to its PowerShell SendKeys representation.
    Returns None for keys that should be skipped (modifiers, media keys, etc.).
    """
    if key_name in _SKIP_KEYS:
        return None

    if key_name in _SENDKEYS_NAMED:
        return _SENDKEYS_NAMED[key_name]

    if len(key_name) == 1:
        return _SENDKEYS_ESCAPE_CHARS.get(key_name, key_name)

    return None


def to_vk_code(key_name: str) -> int | None:
    """
    Convert a normalized key name to its Windows Virtual Key code.
    Returns None if no VK mapping exists.
    """
    if key_name in _SKIP_KEYS:
        return None

    # Named keys lookup
    if key_name in _VK_NAMED:
        return _VK_NAMED[key_name]

    # Single character keys
    if len(key_name) == 1:
        # Check punctuation first (VK ≠ ASCII)
        if key_name in _VK_PUNCTUATION:
            return _VK_PUNCTUATION[key_name]
        # Letters and digits: ASCII = VK
        ch = key_name.upper()
        vk = ord(ch)
        # Only letters (0x41-0x5A) and digits (0x30-0x39) have matching ASCII/VK
        if (0x30 <= vk <= 0x39) or (0x41 <= vk <= 0x5A):
            return vk
        # Unknown single char — skip
        return None

    return None


def is_skip_key(key_name: str) -> bool:
    """Check if this key should be skipped in recording output."""
    return key_name in _SKIP_KEYS
