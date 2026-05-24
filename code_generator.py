"""
Generate PowerShell .ps1 automation script from analyzed key + mouse sequence.

Keyboard:
  - Taps   → SendKeys::SendWait()
  - Holds  → KeySim::HoldKey()   (Win32 keybd_event)

Mouse:
  - Clicks → MouseSim::MoveTo() + MouseSim::Click()
  - Holds  → MouseSim::MoveTo() + MouseSim::Hold()
  - Positions stored as screen-relative percentages (0.0-1.0),
    converted to absolute at runtime → resolution-adaptive.
"""

from analyzer import AnalyzedSequence, KeyGroup, MouseGroup
from key_map import to_sendkeys, to_vk_code
from cs_templates import CS_KEY_SIM, CS_MOUSE_SIM


def generate_ps1(sequence: AnalyzedSequence,
                 start_delay_seconds: int = 5,
                 loop_count: int = 0) -> str:
    """
    Generate a complete PowerShell automation script from analyzed sequence.

    Args:
        sequence: The analyzed key + mouse sequence.
        start_delay_seconds: Delay before starting (for window switching).
        loop_count: Number of iterations. 0 = infinite (while $true).
    """
    interval_s = max(sequence.estimated_cycle_interval_ms / 1000.0, 1.0)
    delay_ms = sequence.estimated_key_delay_ms

    lines: list[str] = []
    has_holds = any(g.is_hold for g in sequence.key_groups)
    has_mouse = len(sequence.mouse_groups) > 0
    has_keys = len(sequence.key_groups) > 0

    # Header
    lines.append("Add-Type -AssemblyName System.Windows.Forms")

    # Embed KeySim for ALL keyboard actions (TapKey + HoldKey)
    if has_keys:
        lines.append("")
        lines.append(CS_KEY_SIM)

    # Embed MouseSim if any mouse actions
    if has_mouse:
        lines.append("")
        lines.append(CS_MOUSE_SIM)

    lines.append("")
    lines.append("")

    # Configuration
    lines.append(f"$intervalSeconds = {interval_s:.0f}")
    lines.append(f"$clickDelayMilliseconds = {delay_ms}")
    lines.append(f"$startupDelaySeconds = {start_delay_seconds}")
    lines.append("")

    # Status
    seq_desc = _describe_sequence(sequence)
    lines.append(f'Write-Host "Auto-generated macro script"')
    lines.append(f'Write-Host "Sequence: {seq_desc}"')
    extra = []
    if sequence.hold_count > 0:
        extra.append(f"{sequence.hold_count} hold(s)")
    if sequence.mouse_click_count > 0:
        extra.append(f"{sequence.mouse_click_count} mouse click(s)")
    if sequence.mouse_hold_count > 0:
        extra.append(f"{sequence.mouse_hold_count} mouse hold(s)")
    if extra:
        lines.append(f'Write-Host "{"  |  ".join(extra)}"')
    lines.append(f'Write-Host "Cycle interval: every $intervalSeconds seconds | Default key delay: {delay_ms}ms"')
    lines.append(f'Write-Host "Switch to the target window now. Starting in $startupDelaySeconds seconds..."')
    lines.append("Start-Sleep -Seconds $startupDelaySeconds")
    lines.append("")

    # Main loop — use for-loop with count or while-true for infinite
    if loop_count > 0:
        lines.append(f"for ($_loop = 0; $_loop -lt {loop_count}; $_loop++) {{")
    else:
        lines.append("while ($true) {")

    # Interleave key groups and mouse groups by timestamp
    all_items = sequence.all_actions_sorted()
    first = True
    for item_type, item in all_items:
        # Per-action delay (actual recorded gap before this action)
        delay = _get_delay_before(item)
        if delay > 0:
            lines.append(f"    Start-Sleep -Milliseconds {delay}")
        elif not first:
            # Even if delay is 0, add a tiny sleep to avoid overwhelming the target
            pass

        if item_type == 'mouse':
            _gen_mouse_action(item, lines)
        else:
            _gen_key_action(item, lines)
        first = False

    lines.append("")
    lines.append("    Start-Sleep -Seconds $intervalSeconds")
    lines.append("}")

    return "\n".join(lines) + "\n"


def _gen_key_action(group: KeyGroup, lines: list[str]):
    """Generate PowerShell code for a keyboard action group using KeySim::TapKey/HoldKey."""
    vk = to_vk_code(group.key_name)
    if vk is None:
        return

    if group.is_hold:
        lines.append(f"    [KeySim]::HoldKey(0x{vk:02X}, {group.hold_duration_ms})")
        return

    intra_ms = int(group.avg_interval_ms) if group.avg_interval_ms > 0 else 0

    if group.count >= 3:
        delay_str = (f"{intra_ms}"
                     if intra_ms > 0
                     else "$clickDelayMilliseconds")
        lines.append(f"    for ($i = 0; $i -lt {group.count}; $i++) {{")
        lines.append(f"        [KeySim]::TapKey(0x{vk:02X})")
        lines.append(f"        Start-Sleep -Milliseconds {delay_str}")
        lines.append("    }")
    else:
        for j in range(group.count):
            lines.append(f"    [KeySim]::TapKey(0x{vk:02X})")
            if j < group.count - 1 and intra_ms > 0:
                lines.append(f"    Start-Sleep -Milliseconds {intra_ms}")
            # Single taps don't need intra-group delay; delay is handled before next action


def _gen_mouse_action(group: MouseGroup, lines: list[str]):
    """Generate PowerShell code for a mouse action (delay handled by caller)."""
    btn = group.mouse_button
    rel_x = group.rel_x
    rel_y = group.rel_y

    lines.append(f"    [MouseSim]::MoveTo({rel_x}, {rel_y})")
    lines.append("    Start-Sleep -Milliseconds 50")

    if group.is_hold:
        if group.drag_path:
            for mx, my in group.drag_path:
                lines.append(f"    [MouseSim]::MoveTo({mx}, {my})")
                lines.append("    Start-Sleep -Milliseconds 20")
        lines.append(f"    [MouseSim]::Hold(\"{btn}\", {group.hold_duration_ms})")
    elif group.drag_path:
        for mx, my in group.drag_path:
            lines.append(f"    [MouseSim]::MoveTo({mx}, {my})")
            lines.append("    Start-Sleep -Milliseconds 20")
        lines.append(f"    [MouseSim]::Click(\"{btn}\")")
    else:
        lines.append(f"    [MouseSim]::Click(\"{btn}\")")


def _get_delay_before(group) -> int:
    """Get the delay_before_ms for a key or mouse group."""
    return getattr(group, 'delay_before_ms', 0)


def _describe_sequence(sequence: AnalyzedSequence) -> str:
    """Build a human-readable description of the full sequence."""
    parts = []
    for item_type, item in sequence.all_actions_sorted():
        if item_type == 'mouse':
            mg = item
            btn = mg.mouse_button.upper()
            if mg.is_hold:
                parts.append(f"[MOUSE {btn} HOLD {mg.hold_duration_ms}ms]")
            else:
                parts.append(f"[MOUSE {btn} CLICK]")
        else:
            g = item
            if g.is_hold:
                parts.append(f"[HOLD {g.key_name.upper()} {g.hold_duration_ms}ms]")
            elif g.count == 1:
                parts.append(g.key_name.upper())
            else:
                parts.append(f"{g.key_name.upper()} x{g.count}")
    return " -> ".join(parts)
