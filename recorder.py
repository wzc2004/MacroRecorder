"""
Keyboard + Mouse recording engine using pynput global hooks.
Captures key press/release (for tap vs hold detection) and
mouse clicks with position (stored as screen-relative percentages
so the recording adapts to different resolutions).

Stop hotkey: ScrollLock + F6 (neither key is recorded).
Mouse events are only recorded when mouse recording is enabled.
"""

import time
import threading
import ctypes
from dataclasses import dataclass, field

try:
    from pynput import keyboard, mouse
except ImportError:
    keyboard = None
    mouse = None


@dataclass
class InputEvent:
    """A single recorded input event (key or mouse)."""
    event_type: str       # "key_press", "key_release", "mouse_click", "mouse_press", "mouse_release"
    timestamp: float      # Seconds relative to recording start

    # Keyboard fields (None for mouse events)
    key_name: str | None = None

    # Mouse fields (None for keyboard events)
    mouse_button: str | None = None   # "left", "right", "middle"
    mouse_rel_x: float | None = None  # 0.0 - 1.0 (percentage of screen width)
    mouse_rel_y: float | None = None  # 0.0 - 1.0 (percentage of screen height)


@dataclass
class Recording:
    """Complete recording session data."""
    events: list[InputEvent] = field(default_factory=list)
    duration: float = 0.0
    event_count: int = 0
    key_event_count: int = 0
    mouse_event_count: int = 0


class Recorder:
    """
    Global input recorder using pynput.
    Runs keyboard + mouse listeners on background threads.
    Communicates stop via callback (called from pynput thread).
    """

    def __init__(self, on_stop_callback=None):
        self._events: list[InputEvent] = []
        self._start_time: float = 0.0
        self._is_recording: bool = False
        self._lock = threading.Lock()
        self._kbd_listener: 'keyboard.Listener | None' = None
        self._ms_listener: 'mouse.Listener | None' = None
        self._scroll_lock_held: bool = False
        self._stop_requested: bool = False
        self._record_mouse: bool = False
        self._screen_w: int = 1920
        self._screen_h: int = 1080
        self._mouse_btn_held: str | None = None  # track which button is pressed
        self.on_stop_callback = on_stop_callback

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._events)

    def start(self, record_mouse: bool = True) -> None:
        """
        Start capturing keyboard and optionally mouse events globally.

        Args:
            record_mouse: If True, also capture mouse clicks (with position).
        """
        if keyboard is None:
            raise RuntimeError(
                "pynput is not installed. Run: pip install pynput"
            )

        with self._lock:
            self._events.clear()
        self._start_time = time.perf_counter()
        self._is_recording = True
        self._stop_requested = False
        self._scroll_lock_held = False
        self._record_mouse = record_mouse

        # Capture current screen dimensions for relative-position calculation
        try:
            self._screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            self._screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            self._screen_w = 1920
            self._screen_h = 1080

        # Keyboard listener (always on)
        self._kbd_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._kbd_listener.start()

        # Mouse listener (optional)
        if record_mouse and mouse is not None:
            self._ms_listener = mouse.Listener(
                on_click=self._on_mouse_click,
                on_move=self._on_mouse_move,
            )
            self._ms_listener.start()

    def stop(self) -> Recording:
        """Stop recording and return the captured data."""
        self._is_recording = False

        if self._kbd_listener is not None:
            self._kbd_listener.stop()
            try:
                self._kbd_listener.join(timeout=1.0)
            except Exception:
                pass
            self._kbd_listener = None

        if self._ms_listener is not None:
            self._ms_listener.stop()
            try:
                self._ms_listener.join(timeout=1.0)
            except Exception:
                pass
            self._ms_listener = None

        with self._lock:
            events = list(self._events)
            duration = events[-1].timestamp if events else 0.0
            key_count = sum(1 for e in events
                            if e.event_type in ("key_press", "key_release"))
            mouse_count = len(events) - key_count

        return Recording(
            events=events,
            duration=duration,
            event_count=len(events),
            key_event_count=key_count,
            mouse_event_count=mouse_count,
        )

    # ------------------------------------------------------------------
    # Keyboard callbacks
    # ------------------------------------------------------------------

    def _on_key_press(self, key) -> None:
        with self._lock:
            if not self._is_recording:
                return

            key_name = self._normalize_key(key)

            if key_name == 'scroll_lock':
                self._scroll_lock_held = True
                return

            if key_name == 'f6' and self._scroll_lock_held:
                self._stop_requested = True
                if self.on_stop_callback is not None:
                    self.on_stop_callback()
                return

            ts = time.perf_counter() - self._start_time
            self._events.append(InputEvent(
                event_type="key_press",
                timestamp=ts,
                key_name=key_name,
            ))

    def _on_key_release(self, key) -> None:
        with self._lock:
            if not self._is_recording:
                return

            key_name = self._normalize_key(key)

            if key_name == 'scroll_lock':
                self._scroll_lock_held = False
                return

            if key_name == 'f6' and self._stop_requested:
                return

            ts = time.perf_counter() - self._start_time
            self._events.append(InputEvent(
                event_type="key_release",
                timestamp=ts,
                key_name=key_name,
            ))

    def _normalize_key(self, key) -> str:
        # Prioritize `name` first for consistency — the same physical key
        # should always produce the same name regardless of pynput's reporting.
        if hasattr(key, 'name') and key.name is not None:
            return key.name.lower()
        if hasattr(key, 'char') and key.char is not None:
            return key.char
        if hasattr(key, 'vk') and key.vk is not None:
            return f'vk_{key.vk}'
        return str(key).lower()

    # ------------------------------------------------------------------
    # Mouse callbacks
    # ------------------------------------------------------------------

    def _on_mouse_click(self, x: int, y: int, button, pressed: bool) -> None:
        with self._lock:
            if not self._is_recording or not self._record_mouse:
                return

            btn_name = self._normalize_button(button)

            rel_x = round(x / self._screen_w, 6) if self._screen_w > 0 else 0.0
            rel_y = round(y / self._screen_h, 6) if self._screen_h > 0 else 0.0

            ts = time.perf_counter() - self._start_time
            self._events.append(InputEvent(
                event_type="mouse_press" if pressed else "mouse_release",
                timestamp=ts,
                mouse_button=btn_name,
                mouse_rel_x=rel_x,
                mouse_rel_y=rel_y,
            ))

            # Track button state for drag detection
            if pressed:
                self._mouse_btn_held = btn_name
            else:
                self._mouse_btn_held = None

    def _on_mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            if not self._is_recording or not self._record_mouse:
                return
            if self._mouse_btn_held is None:
                return  # only record moves during drag

            rel_x = round(x / self._screen_w, 6) if self._screen_w > 0 else 0.0
            rel_y = round(y / self._screen_h, 6) if self._screen_h > 0 else 0.0

            ts = time.perf_counter() - self._start_time
            self._events.append(InputEvent(
                event_type="mouse_move",
                timestamp=ts,
                mouse_button=self._mouse_btn_held,
                mouse_rel_x=rel_x,
                mouse_rel_y=rel_y,
            ))

    def _normalize_button(self, button) -> str:
        """Convert pynput mouse Button to string."""
        from pynput.mouse import Button
        if button == Button.left:
            return "left"
        elif button == Button.right:
            return "right"
        elif button == Button.middle:
            return "middle"
        return str(button).lower()
