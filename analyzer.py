"""
Input sequence analysis: pair press/release events (both keyboard and mouse),
detect holds vs taps/clicks, group consecutive identical key taps, and
estimate timing parameters for code generation.
"""

import statistics
from dataclasses import dataclass, field

from recorder import InputEvent
from key_map import is_skip_key, to_vk_code

HOLD_THRESHOLD_MS = 1000
GROUP_MERGE_THRESHOLD_S = 0.350


@dataclass
class KeyAction:
    """A processed keyboard action (tap or hold)."""
    key_name: str
    action_type: str       # "tap" or "hold"
    timestamp: float
    hold_duration_ms: int = 0


@dataclass
class MouseAction:
    """A processed mouse action (click or hold/drag)."""
    mouse_button: str              # "left", "right", "middle"
    action_type: str               # "click" or "hold"
    timestamp: float               # When the press started
    rel_x: float                   # 0.0 - 1.0
    rel_y: float                   # 0.0 - 1.0
    hold_duration_ms: int = 0


@dataclass
class KeyGroup:
    """A group of consecutive, rapidly-pressed identical key taps."""
    key_name: str
    count: int
    first_timestamp: float
    last_timestamp: float
    avg_interval_ms: float = 0.0
    is_hold: bool = False
    hold_duration_ms: int = 0
    delay_before_ms: int = 0  # actual ms between this group's start and previous group's end


@dataclass
class MouseGroup:
    """A single mouse action (click or hold at a position)."""
    mouse_button: str
    rel_x: float
    rel_y: float
    timestamp: float
    release_timestamp: float = 0.0
    is_hold: bool = False
    hold_duration_ms: int = 0
    delay_before_ms: int = 0
    drag_path: list[tuple[float, float]] = None  # intermediate move points during drag

    def __post_init__(self):
        if self.drag_path is None:
            self.drag_path = []


@dataclass
class AnalyzedSequence:
    """The analyzed result ready for code generation."""
    key_groups: list[KeyGroup] = field(default_factory=list)
    mouse_groups: list[MouseGroup] = field(default_factory=list)
    estimated_key_delay_ms: int = 200
    estimated_cycle_interval_ms: int = 2000
    total_events: int = 0
    skipped_events: int = 0
    tap_count: int = 0
    hold_count: int = 0
    mouse_click_count: int = 0
    mouse_hold_count: int = 0

    @property
    def total_key_presses(self) -> int:
        return sum(g.count for g in self.key_groups)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict for saving."""
        return {
            "key_groups": [
                {
                    "key_name": g.key_name,
                    "count": g.count,
                    "first_timestamp": g.first_timestamp,
                    "last_timestamp": g.last_timestamp,
                    "avg_interval_ms": g.avg_interval_ms,
                    "is_hold": g.is_hold,
                    "hold_duration_ms": g.hold_duration_ms,
                    "delay_before_ms": g.delay_before_ms,
                }
                for g in self.key_groups
            ],
            "mouse_groups": [
                {
                    "mouse_button": mg.mouse_button,
                    "rel_x": mg.rel_x,
                    "rel_y": mg.rel_y,
                    "timestamp": mg.timestamp,
                    "release_timestamp": mg.release_timestamp,
                    "is_hold": mg.is_hold,
                    "hold_duration_ms": mg.hold_duration_ms,
                    "delay_before_ms": mg.delay_before_ms,
                    "drag_path": mg.drag_path,
                }
                for mg in self.mouse_groups
            ],
            "estimated_key_delay_ms": self.estimated_key_delay_ms,
            "estimated_cycle_interval_ms": self.estimated_cycle_interval_ms,
            "total_events": self.total_events,
            "skipped_events": self.skipped_events,
            "tap_count": self.tap_count,
            "hold_count": self.hold_count,
            "mouse_click_count": self.mouse_click_count,
            "mouse_hold_count": self.mouse_hold_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnalyzedSequence":
        """Reconstruct from a dict (from JSON)."""
        return cls(
            key_groups=[
                KeyGroup(
                    key_name=g["key_name"],
                    count=g["count"],
                    first_timestamp=g["first_timestamp"],
                    last_timestamp=g["last_timestamp"],
                    avg_interval_ms=g.get("avg_interval_ms", 0.0),
                    is_hold=g.get("is_hold", False),
                    hold_duration_ms=g.get("hold_duration_ms", 0),
                    delay_before_ms=g.get("delay_before_ms", 0),
                )
                for g in d.get("key_groups", [])
            ],
            mouse_groups=[
                MouseGroup(
                    mouse_button=mg["mouse_button"],
                    rel_x=mg["rel_x"],
                    rel_y=mg["rel_y"],
                    timestamp=mg["timestamp"],
                    release_timestamp=mg.get("release_timestamp", 0.0),
                    is_hold=mg.get("is_hold", False),
                    hold_duration_ms=mg.get("hold_duration_ms", 0),
                    delay_before_ms=mg.get("delay_before_ms", 0),
                )
                for mg in d.get("mouse_groups", [])
            ],
            estimated_key_delay_ms=d.get("estimated_key_delay_ms", 200),
            estimated_cycle_interval_ms=d.get("estimated_cycle_interval_ms", 2000),
            total_events=d.get("total_events", 0),
            skipped_events=d.get("skipped_events", 0),
            tap_count=d.get("tap_count", 0),
            hold_count=d.get("hold_count", 0),
            mouse_click_count=d.get("mouse_click_count", 0),
            mouse_hold_count=d.get("mouse_hold_count", 0),
        )

    @property
    def total_mouse_actions(self) -> int:
        return len(self.mouse_groups)

    @property
    def groups(self) -> list:
        """Return all groups (key + mouse) sorted by timestamp."""
        all_groups = []
        all_groups.extend(self.key_groups)
        for mg in self.mouse_groups:
            all_groups.append(KeyGroup(
                key_name=f"mouse_{mg.mouse_button}",
                count=1,
                first_timestamp=mg.timestamp,
                last_timestamp=mg.timestamp,
                is_hold=mg.is_hold,
                hold_duration_ms=mg.hold_duration_ms,
            ))
        all_groups.sort(key=lambda g: g.first_timestamp)
        return all_groups

    def all_actions_sorted(self) -> list:
        """Return all actions interleaved by timestamp for generation."""
        items = []
        for g in self.key_groups:
            items.append(('key', g))
        for g in self.mouse_groups:
            items.append(('mouse', g))
        items.sort(key=lambda x: (x[1].first_timestamp
                                   if hasattr(x[1], 'first_timestamp')
                                   else x[1].timestamp))
        return items


def analyze(events: list[InputEvent]) -> AnalyzedSequence:
    """
    Analyze input events (keyboard press/release + mouse press/release).

    1. Separate keyboard and mouse events
    2. Pair press/release for both
    3. Classify as tap/click vs hold
    4. Group consecutive identical key taps
    5. Estimate timing parameters
    """
    if not events:
        return AnalyzedSequence()

    # Separate events by type
    kbd_events = [e for e in events
                  if e.event_type in ("key_press", "key_release")]
    ms_events = [e for e in events
                 if e.event_type in ("mouse_press", "mouse_release")]

    # Process keyboard
    key_actions, kb_skipped = _process_keyboard_events(kbd_events)
    key_groups = _build_key_groups(key_actions)

    # Process mouse
    mouse_groups, ms_skipped = _process_mouse_events(ms_events)

    # Timing from keyboard actions (or mouse if no keyboard)
    all_actions_for_timing = list(key_actions)
    # Also include mouse actions in timing
    for mg in mouse_groups:
        all_actions_for_timing.append(KeyAction(
            key_name=f"mouse_{mg.mouse_button}",
            action_type="hold" if mg.is_hold else "tap",
            timestamp=mg.timestamp,
            hold_duration_ms=mg.hold_duration_ms,
        ))
    all_actions_for_timing.sort(key=lambda a: a.timestamp)

    key_delay_ms = _estimate_key_delay(all_actions_for_timing)

    # Sequence duration from all groups
    all_groups_sorted = []
    all_groups_sorted.extend(key_groups)
    for mg in mouse_groups:
        all_groups_sorted.append(KeyGroup(
            key_name=f"mouse_{mg.mouse_button}",
            count=1,
            first_timestamp=mg.timestamp,
            last_timestamp=mg.timestamp,
        ))
    all_groups_sorted.sort(key=lambda g: g.first_timestamp)
    seq_duration_ms = _sequence_duration_ms(all_groups_sorted)
    cycle_interval_ms = 1000  # Default 1 second (user can change in Timeline Editor)

    # Compute per-action delays from actual recorded timestamps
    _compute_delays(key_groups, mouse_groups)

    tap_count = sum(1 for a in key_actions if a.action_type == "tap")
    hold_count = sum(1 for a in key_actions if a.action_type == "hold")
    click_count = sum(1 for mg in mouse_groups if not mg.is_hold)
    mouse_hold_count = sum(1 for mg in mouse_groups if mg.is_hold)

    return AnalyzedSequence(
        key_groups=key_groups,
        mouse_groups=mouse_groups,
        estimated_key_delay_ms=key_delay_ms,
        estimated_cycle_interval_ms=cycle_interval_ms,
        total_events=len(events),
        skipped_events=kb_skipped + ms_skipped,
        tap_count=tap_count,
        hold_count=hold_count,
        mouse_click_count=click_count,
        mouse_hold_count=mouse_hold_count,
    )


# ------------------------------------------------------------------
# Keyboard processing
# ------------------------------------------------------------------

def _process_keyboard_events(events: list[InputEvent]) -> tuple[list[KeyAction], int]:
    """Pair key press/release and classify taps vs holds."""
    pending: dict[str, list[float]] = {}
    actions: list[KeyAction] = []
    skipped = 0

    for e in events:
        if is_skip_key(e.key_name):
            skipped += 1
            continue
        if to_vk_code(e.key_name) is None:
            skipped += 1
            continue

        if e.event_type == "key_press":
            if e.key_name not in pending:
                pending[e.key_name] = []
            # Ignore autorepeat: only record the first press while key is held
            if not pending[e.key_name]:
                pending[e.key_name].append(e.timestamp)
        elif e.event_type == "key_release":
            if e.key_name in pending and pending[e.key_name]:
                press_ts = pending[e.key_name].pop(0)
                duration_ms = int((e.timestamp - press_ts) * 1000.0)
                if duration_ms > HOLD_THRESHOLD_MS:
                    actions.append(KeyAction(key_name=e.key_name,
                                             action_type="hold",
                                             timestamp=press_ts,
                                             hold_duration_ms=duration_ms))
                else:
                    actions.append(KeyAction(key_name=e.key_name,
                                             action_type="tap",
                                             timestamp=press_ts))

    # Unmatched presses (recording stopped while held) → taps
    for key_name, stack in pending.items():
        for press_ts in stack:
            actions.append(KeyAction(key_name=key_name,
                                     action_type="tap", timestamp=press_ts))

    actions.sort(key=lambda a: a.timestamp)
    return actions, skipped


def _build_key_groups(actions: list[KeyAction]) -> list[KeyGroup]:
    """Merge consecutive identical taps into groups; holds stay separate."""
    groups: list[KeyGroup] = []

    for a in actions:
        if a.action_type == "hold":
            groups.append(KeyGroup(key_name=a.key_name, count=1,
                                   first_timestamp=a.timestamp,
                                   last_timestamp=a.timestamp,
                                   is_hold=True,
                                   hold_duration_ms=a.hold_duration_ms))
        else:
            if (groups and not groups[-1].is_hold
                    and groups[-1].key_name == a.key_name
                    and (a.timestamp - groups[-1].last_timestamp) <= GROUP_MERGE_THRESHOLD_S):
                groups[-1].count += 1
                groups[-1].last_timestamp = a.timestamp
            else:
                groups.append(KeyGroup(key_name=a.key_name, count=1,
                                       first_timestamp=a.timestamp,
                                       last_timestamp=a.timestamp))

    for g in groups:
        if not g.is_hold and g.count >= 2:
            total_span_s = g.last_timestamp - g.first_timestamp
            g.avg_interval_ms = round((total_span_s / (g.count - 1)) * 1000.0)

    return groups


# ------------------------------------------------------------------
# Mouse processing
# ------------------------------------------------------------------

def _process_mouse_events(events: list[InputEvent]) -> tuple[list[MouseGroup], int]:
    """
    Pair mouse press/release events into clicks or holds.
    Uses the position from the press event.
    """
    pending: dict[str, list[tuple[float, float, float]]] = {}
    groups: list[MouseGroup] = []
    skipped = 0
    # Collect move events during drag, keyed by button
    pending_moves: dict[str, list[tuple[float, float]]] = {}

    for e in events:
        btn = e.mouse_button
        if not btn:
            skipped += 1
            continue

        if e.event_type == "mouse_press":
            if btn not in pending:
                pending[btn] = []
                pending_moves[btn] = []
            pending[btn].append((e.timestamp,
                                 e.mouse_rel_x or 0.0,
                                 e.mouse_rel_y or 0.0))
        elif e.event_type == "mouse_move":
            if btn in pending and pending[btn]:
                pending_moves.setdefault(btn, []).append(
                    (e.mouse_rel_x or 0.0, e.mouse_rel_y or 0.0))
        elif e.event_type == "mouse_release":
            if btn in pending and pending[btn]:
                press_ts, rel_x, rel_y = pending[btn].pop(0)
                duration_ms = int((e.timestamp - press_ts) * 1000.0)
                moves = pending_moves.pop(btn, [])
                if duration_ms > HOLD_THRESHOLD_MS:
                    groups.append(MouseGroup(
                        mouse_button=btn, rel_x=rel_x, rel_y=rel_y,
                        timestamp=press_ts, release_timestamp=e.timestamp,
                        is_hold=True, hold_duration_ms=duration_ms,
                        drag_path=moves,
                    ))
                else:
                    groups.append(MouseGroup(
                        mouse_button=btn, rel_x=rel_x, rel_y=rel_y,
                        timestamp=press_ts, release_timestamp=e.timestamp,
                        drag_path=moves,
                    ))

    # Unmatched presses → clicks
    for btn, stack in pending.items():
        for press_ts, rel_x, rel_y in stack:
            groups.append(MouseGroup(
                mouse_button=btn, rel_x=rel_x, rel_y=rel_y,
                timestamp=press_ts,
            ))

    groups.sort(key=lambda g: g.timestamp)
    return groups, skipped


# ------------------------------------------------------------------
# Timing estimation
# ------------------------------------------------------------------

def _estimate_key_delay(actions: list[KeyAction]) -> int:
    if len(actions) < 2:
        return 200

    intervals = []
    for i in range(1, len(actions)):
        gap_ms = (actions[i].timestamp - actions[i - 1].timestamp) * 1000.0
        if gap_ms <= 2000:
            intervals.append(gap_ms)

    if not intervals:
        return 200

    median_ms = statistics.median(intervals)
    return max(30, min(int(round(median_ms)), 2000))


def _sequence_duration_ms(groups: list[KeyGroup]) -> float:
    if not groups:
        return 0.0
    return (groups[-1].last_timestamp - groups[0].first_timestamp) * 1000.0


def _compute_delays(key_groups: list[KeyGroup],
                    mouse_groups: list[MouseGroup]) -> None:
    """
    Compute `delay_before_ms` for every key and mouse group based on
    the actual recorded timestamp gaps between consecutive actions.
    Modifies the groups in-place.
    """
    # Collect all objects with their start/end timestamps
    all_items: list[tuple[float, float, object]] = []  # (start_ts, end_ts, group)
    for g in key_groups:
        end_ts = (g.first_timestamp + g.hold_duration_ms / 1000.0
                  if g.is_hold else g.last_timestamp)
        all_items.append((g.first_timestamp, end_ts, g))
    for mg in mouse_groups:
        if mg.is_hold:
            end_ts = mg.timestamp + mg.hold_duration_ms / 1000.0
        elif mg.release_timestamp > 0:
            end_ts = mg.release_timestamp  # actual release time
        else:
            end_ts = mg.timestamp + 0.05  # fallback for unmatched presses
        all_items.append((mg.timestamp, end_ts, mg))

    all_items.sort(key=lambda x: x[0])

    prev_end = all_items[0][0] if all_items else 0.0  # first action starts at 0 delay
    for start_ts, end_ts, group in all_items:
        delay_ms = int(round((start_ts - prev_end) * 1000.0))
        if delay_ms < 0:
            delay_ms = 0  # overlapping events — shouldn't happen
        group.delay_before_ms = delay_ms
        prev_end = end_ts
