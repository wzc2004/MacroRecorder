"""
Trimming: remove first N seconds and last N seconds from a recording.
This strips setup/teardown noise (Alt+Tab, reaching for stop hotkey, etc.)
"""

from recorder import InputEvent


class TrimmingResult:
    """Result of trimming operation."""
    def __init__(self, events: list[InputEvent], was_trimmed: bool, warning: str | None = None):
        self.events = events
        self.was_trimmed = was_trimmed
        self.warning = warning


def trim(events: list[InputEvent],
         trim_start: float = 5.0,
         trim_end: float = 5.0) -> TrimmingResult:
    """
    Remove events in the first `trim_start` seconds and last `trim_end` seconds.
    Rebase remaining timestamps so the first event starts at 0.0.

    Args:
        events: List of recorded key events sorted by timestamp.
        trim_start: Seconds to remove from the beginning.
        trim_end: Seconds to remove from the end.

    Returns:
        TrimmingResult with processed events and metadata.
    """
    if not events:
        return TrimmingResult([], was_trimmed=False,
                              warning="No events to trim (recording is empty).")

    total_duration = events[-1].timestamp

    if total_duration <= (trim_start + trim_end):
        return TrimmingResult(
            events=list(events),
            was_trimmed=False,
            warning=(
                f"Recording too short ({total_duration:.1f}s) for "
                f"{trim_start}s + {trim_end}s trimming. "
                "No trimming was applied. Consider recording a longer sequence."
            ),
        )

    cut_start = trim_start
    cut_end = total_duration - trim_end

    filtered = [e for e in events if cut_start <= e.timestamp <= cut_end]

    if not filtered:
        return TrimmingResult(list(events), was_trimmed=False,
                              warning="Trimming removed all events. Keeping original recording.")

    # Rebase timestamps so first event = 0.0, preserving intervals
    first_ts = filtered[0].timestamp
    for e in filtered:
        e.timestamp = round(e.timestamp - first_ts, 6)

    return TrimmingResult(filtered, was_trimmed=True)
