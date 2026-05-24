"""
Macro Recorder - Main Application
Tkinter-based GUI for recording keyboard + mouse operations,
visual timeline editing, and generating PowerShell automation scripts.

Usage: python main.py
   or: double-click install.bat
"""

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime

from recorder import Recorder, Recording
from trimmer import trim
from analyzer import analyze, AnalyzedSequence, KeyGroup, MouseGroup
from code_generator import generate_ps1
from template_engine import generate_bat, generate_readme
from key_map import to_sendkeys


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "Macro Recorder v1.1"
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MacroOutputs")
TRIM_START_SECONDS = 5.0
TRIM_END_SECONDS = 5.0
STARTUP_DELAY_SECONDS = 5
PS1_FILENAME = "automation_script.ps1"
BAT_FILENAME = "run.bat"
README_FILENAME = "使用说明.txt"

COLOR_READY = "#4CAF50"
COLOR_RECORDING = "#F44336"
COLOR_PROCESSING = "#FF9800"
COLOR_DONE = "#2196F3"


# ---------------------------------------------------------------------------
# Timeline Editor (popup window)
# ---------------------------------------------------------------------------

class TimelineEditor(tk.Toplevel):
    """Editable timeline for adjusting recorded macro timing before saving."""

    def __init__(self, parent, analyzed: AnalyzedSequence, output_dir: str,
                 start_delay: int = 5):
        super().__init__(parent)
        self.title("Timeline Editor - Adjust Timing")
        self.geometry("780x520")
        self.minsize(600, 400)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._analyzed = analyzed
        self._output_dir = output_dir
        self._start_delay = start_delay
        self._saved = False

        # Editable globals
        self._var_key_delay = tk.StringVar(value=str(analyzed.estimated_key_delay_ms))
        self._var_cycle_interval = tk.StringVar(
            value=str(int(analyzed.estimated_cycle_interval_ms / 1000.0)))
        self._var_start_delay = tk.StringVar(value=str(start_delay))
        self._var_loop_count = tk.StringVar(value="0")

        # Per-action rows: list of (delay_var, hold_var_or_None)
        self._row_vars: list[tuple[tk.StringVar, tk.StringVar | None]] = []
        self._flat_actions: list[tuple[str, object]] = []  # ("key"|"mouse", group)

        self._build_ui()
        self._populate_table()

        # Make modal-like: grab focus
        self.transient(parent)
        self.grab_set()
        self.lift()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = ttk.Frame(self, padding="12 10 12 10")
        outer.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(outer, text="Timeline Editor",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(outer, text="Adjust timing values, then click Save to generate the script.",
                  font=("Segoe UI", 9), foreground="gray").pack(anchor=tk.W, pady=(2, 8))

        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))

        # --- Global settings row ---
        globals_frame = ttk.LabelFrame(outer, text="Global Settings", padding="8 6 8 6")
        globals_frame.pack(fill=tk.X, pady=(0, 8))

        gf = ttk.Frame(globals_frame)
        gf.pack(fill=tk.X)

        ttk.Label(gf, text="Key Delay (ms):", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self._var_key_delay, width=6,
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(4, 20))

        ttk.Label(gf, text="Cycle Interval (s):", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self._var_cycle_interval, width=6,
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(4, 20))

        ttk.Label(gf, text="Loop Count (0=infinite):", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self._var_loop_count, width=6,
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(4, 10))

        ttk.Label(gf, text="Startup Delay (s):", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Entry(gf, textvariable=self._var_start_delay, width=6,
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(4, 10))

        # Apply global button
        ttk.Button(gf, text="Apply & Rebuild",
                   command=self._apply_globals).pack(side=tk.RIGHT)

        # --- Action table ---
        table_frame = ttk.LabelFrame(outer, text="Actions", padding="4 4 4 4")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Treeview
        columns = ("step", "action", "delay", "duration")
        self._tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                   height=12, selectmode="browse")
        self._tree.heading("step", text="#")
        self._tree.heading("action", text="Action")
        self._tree.heading("delay", text="Delay before (ms)")
        self._tree.heading("duration", text="Hold Duration (ms)")

        self._tree.column("step", width=40, anchor=tk.CENTER, stretch=False)
        self._tree.column("action", width=280, anchor=tk.W)
        self._tree.column("delay", width=140, anchor=tk.CENTER)
        self._tree.column("duration", width=140, anchor=tk.CENTER)

        # Scrollbar
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self._tree.bind("<Double-1>", self._on_cell_edit)

        # --- Bottom buttons ---
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Reset to Auto-Detected",
                   command=self._reset_defaults).pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="Save",
                   command=self._save, width=18).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_frame, text="Cancel",
                   command=self._on_close, width=10).pack(side=tk.RIGHT)

        self._status_lbl = ttk.Label(outer, text="",
                                     font=("Segoe UI", 9), foreground="gray")
        self._status_lbl.pack(anchor=tk.W, pady=(6, 0))

    # ------------------------------------------------------------------
    # Populate
    # ------------------------------------------------------------------

    def _populate_table(self):
        """Fill the treeview with actions from the analyzed sequence."""
        self._flat_actions = self._analyzed.all_actions_sorted()
        self._row_vars = []

        # Clear existing
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Use per-action delay computed by the analyzer (actual recording gap)
        for i, (act_type, act) in enumerate(self._flat_actions):
            delay_ms = getattr(act, 'delay_before_ms', 0)

            # Action description
            desc = self._describe(act_type, act)

            # Hold duration (only for holds)
            is_hold = getattr(act, 'is_hold', False)
            hold_ms = getattr(act, 'hold_duration_ms', 0) if is_hold else 0

            delay_var = tk.StringVar(value=str(delay_ms))
            dur_var = tk.StringVar(value=str(hold_ms)) if is_hold else None
            self._row_vars.append((delay_var, dur_var))

            dur_display = str(hold_ms) if is_hold else "-"
            self._tree.insert("", tk.END, iid=str(i),
                              values=(i + 1, desc, delay_ms, dur_display))

        self._status_lbl.configure(
            text=f"{len(self._flat_actions)} actions loaded. "
                 "Double-click a cell to edit, or adjust globals above.")

    def _describe(self, act_type: str, act) -> str:
        """Build a short description string for an action."""
        if act_type == 'mouse':
            btn = act.mouse_button.upper()
            pos = f"({act.rel_x:.1%}, {act.rel_y:.1%})"
            if getattr(act, 'is_hold', False):
                return f"Mouse {btn} HOLD {act.hold_duration_ms}ms at {pos}"
            return f"Mouse {btn} CLICK at {pos}"
        else:
            sk = to_sendkeys(act.key_name)
            label = sk if sk else act.key_name.upper()
            # Clean up SendKeys wrapping
            if label and label.startswith("{") and label.endswith("}"):
                label = label[1:-1]
            if getattr(act, 'is_hold', False):
                return f"Key {label} HOLD {act.hold_duration_ms}ms"
            if act.count > 1:
                return f"Key {label} x{act.count}"
            return f"Key {label}"

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def _on_cell_edit(self, event):
        """Handle double-click on a cell to edit the value."""
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._tree.identify_column(event.x)
        item = self._tree.identify_row(event.y)
        if not item:
            return

        col_idx = int(column.replace("#", "")) - 1  # 0-based
        row_idx = int(item)

        if col_idx not in (2, 3):  # Only "delay" and "duration" columns
            return

        # Check if duration column is editable for this row
        _, dur_var = self._row_vars[row_idx]
        if col_idx == 3 and dur_var is None:
            return  # Not a hold - duration is not editable

        # Get current value
        current_values = self._tree.item(item, "values")
        current_val = current_values[col_idx]

        # Get cell bbox for overlay placement
        bbox = self._tree.bbox(item, column)
        if not bbox:
            return

        var = self._row_vars[row_idx][0] if col_idx == 2 else dur_var
        self._show_cell_editor(bbox, var, item, col_idx)

    def _show_cell_editor(self, bbox, var: tk.StringVar, item: str, col_idx: int):
        """Overlay an Entry on top of the cell for inline editing."""
        x, y, w, h = bbox

        editor = ttk.Entry(self._tree, textvariable=var,
                           font=("Segoe UI", 9), width=max(w // 8, 6))
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()
        editor.select_range(0, tk.END)

        def commit(_event=None):
            val = var.get().strip()
            try:
                int(val)
            except ValueError:
                editor.destroy()
                return
            # Update tree display
            values = list(self._tree.item(item, "values"))
            values[col_idx] = val
            self._tree.item(item, values=values)
            editor.destroy()
            self._status_lbl.configure(text="Value updated. Click Save to apply.")

        def cancel(_event=None):
            editor.destroy()

        editor.bind("<Return>", commit)
        editor.bind("<Escape>", cancel)
        editor.bind("<FocusOut>", commit)

    def _apply_globals(self):
        """Apply global delay to all non-zero delays and rebuild display."""
        try:
            new_delay = int(self._var_key_delay.get())
        except ValueError:
            messagebox.showwarning("Invalid", "Key Delay must be an integer.")
            return

        for delay_var, _ in self._row_vars:
            delay_var.set(str(new_delay))

        # Update tree display
        for i, item in enumerate(self._tree.get_children()):
            values = list(self._tree.item(item, "values"))
            values[2] = new_delay
            self._tree.item(item, values=values)

        self._status_lbl.configure(
            text=f"All delays set to {new_delay}ms. Click Save to apply.")

    def _reset_defaults(self):
        """Reset all values to the auto-analyzed defaults."""
        seq = self._analyzed
        self._var_key_delay.set(str(seq.estimated_key_delay_ms))
        self._var_cycle_interval.set(
            str(int(seq.estimated_cycle_interval_ms / 1000.0)))
        self._var_start_delay.set(str(STARTUP_DELAY_SECONDS))
        self._var_loop_count.set("0")

        self._populate_table()
        self._status_lbl.configure(text="Reset to auto-detected defaults.")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self):
        """Build a modified AnalyzedSequence from edited values, generate files."""
        # Read global values
        try:
            key_delay = int(self._var_key_delay.get())
            cycle_interval_ms = int(float(self._var_cycle_interval.get()) * 1000)
            start_delay = int(self._var_start_delay.get())
            loop_count = int(self._var_loop_count.get())
        except ValueError:
            messagebox.showwarning("Invalid", "Global settings must be numbers.")
            return

        # Build modified sequence
        modified = self._build_modified_sequence(key_delay, cycle_interval_ms)

        # Create output folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Macro_{timestamp}"

        # Ask user for a macro name FIRST, then name the folder with it
        macro_name = simpledialog.askstring(
            "命名宏",
            "为这个宏输入一个名字\n(留空则使用默认名称):",
            initialvalue="",
            parent=self)
        if not macro_name or not macro_name.strip():
            macro_name = default_name
        else:
            macro_name = macro_name.strip()
            # Sanitize: remove chars unsafe for folder names
            unsafe = '<>:"/\\|?*'
            for ch in unsafe:
                macro_name = macro_name.replace(ch, '_')

        folder_path = os.path.join(self._output_dir, macro_name)
        if os.path.exists(folder_path):
            ok = messagebox.askyesno(
                "文件夹已存在",
                f'"{macro_name}" 已存在。\n覆盖旧文件？')
            if not ok:
                self._status_lbl.configure(
                    text="Save cancelled.", foreground="gray")
                return
        os.makedirs(folder_path, exist_ok=True)

        # Generate files
        ps1_content = generate_ps1(modified, start_delay, loop_count)
        with open(os.path.join(folder_path, PS1_FILENAME), "w",
                  encoding="utf-8-sig") as f:
            f.write(ps1_content)

        bat_content = generate_bat(PS1_FILENAME)
        with open(os.path.join(folder_path, BAT_FILENAME), "w",
                  encoding="ascii") as f:
            f.write(bat_content)

        readme_content = generate_readme(
            modified,
            script_name=PS1_FILENAME.replace(".ps1", ""),
            folder_name=macro_name,
            start_delay=start_delay,
        )
        with open(os.path.join(folder_path, README_FILENAME), "w",
                  encoding="utf-8") as f:
            f.write(readme_content)

        # Save JSON for the composer
        json_data = {
            "name": macro_name,
            "folder": macro_name,
            "created": datetime.now().isoformat(),
            "start_delay_seconds": start_delay,
            "loop_count": loop_count,
            "cycle_interval_ms": modified.estimated_cycle_interval_ms,
            "sequence": modified.to_dict(),
        }
        with open(os.path.join(folder_path, "recording.json"), "w",
                  encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        self._saved = True
        self._status_lbl.configure(
            text=f"Saved to: {folder_path}", foreground=COLOR_READY)
        messagebox.showinfo("Done", f"Automation script saved to:\n{folder_path}")
        self.destroy()

    def _build_modified_sequence(self, key_delay: int,
                                  cycle_interval_ms: int) -> AnalyzedSequence:
        """Build a copy of the analyzed sequence with modified timing values."""
        import copy
        from analyzer import AnalyzedSequence

        new_key_groups = [copy.copy(g) for g in self._analyzed.key_groups]
        new_mouse_groups = [copy.copy(mg) for mg in self._analyzed.mouse_groups]

        # Apply per-action edits (delay and hold duration) from editor rows
        for i, (act_type, act) in enumerate(self._flat_actions):
            delay_var, dur_var = self._row_vars[i]

            try:
                new_delay = int(delay_var.get())
            except ValueError:
                new_delay = 0

            new_dur = 0
            if dur_var is not None:
                try:
                    new_dur = int(dur_var.get())
                except ValueError:
                    new_dur = 0

            # Match to the corresponding group and apply edits
            if act_type == 'mouse':
                for mg in new_mouse_groups:
                    if (mg.mouse_button == act.mouse_button and
                            abs(mg.timestamp - act.timestamp) < 0.01):
                        mg.delay_before_ms = new_delay
                        mg.hold_duration_ms = new_dur
                        mg.is_hold = new_dur > 0
                        break
            else:
                for kg in new_key_groups:
                    if (kg.key_name == act.key_name and
                            abs(kg.first_timestamp - act.first_timestamp) < 0.01):
                        kg.delay_before_ms = new_delay
                        kg.hold_duration_ms = new_dur
                        kg.is_hold = new_dur > 0
                        break

        return AnalyzedSequence(
            key_groups=new_key_groups,
            mouse_groups=new_mouse_groups,
            estimated_key_delay_ms=key_delay,
            estimated_cycle_interval_ms=cycle_interval_ms,
            total_events=self._analyzed.total_events,
            skipped_events=self._analyzed.skipped_events,
            tap_count=self._analyzed.tap_count,
            hold_count=self._analyzed.hold_count,
            mouse_click_count=self._analyzed.mouse_click_count,
            mouse_hold_count=self._analyzed.mouse_hold_count,
        )

    def _on_close(self):
        if not self._saved:
            ok = messagebox.askyesno(
                "Discard Changes?",
                "You have not saved. Discard timeline edits?")
            if not ok:
                return
        self.destroy()


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class MacroRecorderApp:
    """Main application window."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("540x420")
        self.root.resizable(True, True)
        self.root.minsize(480, 360)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._recorder = Recorder(on_stop_callback=self._on_hotkey_stop)
        self._recording: Recording | None = None
        self._analyzed: AnalyzedSequence | None = None
        self._output_dir = DEFAULT_OUTPUT_DIR
        self._poll_interval_ms = 200
        self._editor_open = False

        self._build_ui()
        self._set_status("ready", "Ready. Click \"Start Recording\" to begin.")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding="16 12 16 12")
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main, text=APP_TITLE,
                  font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 12))

        # Status indicator
        status_frame = ttk.Frame(main)
        status_frame.pack(fill=tk.X, pady=(0, 4))

        self._status_dot = tk.Canvas(status_frame, width=14, height=14,
                                     highlightthickness=0)
        self._status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self._status_text = ttk.Label(status_frame, text="Ready",
                                      font=("Segoe UI", 10))
        self._status_text.pack(side=tk.LEFT)

        # Event count
        self._event_count_lbl = ttk.Label(main, text="Events recorded: 0",
                                          font=("Segoe UI", 9))
        self._event_count_lbl.pack(anchor=tk.W, pady=(0, 8))

        # Button frame
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        self._record_btn = ttk.Button(btn_frame, text="Start Recording",
                                      command=self._toggle_recording, width=22)
        self._record_btn.pack(side=tk.LEFT, padx=(0, 10))

        self._hotkey_hint = ttk.Label(
            btn_frame,
            text="Stop: ScrollLock + F6",
            font=("Segoe UI", 8), foreground="gray")
        self._hotkey_hint.pack(side=tk.LEFT)

        # Mouse checkbox
        mouse_frame = ttk.Frame(main)
        mouse_frame.pack(fill=tk.X, pady=(0, 6))

        self._mouse_var = tk.BooleanVar(value=True)
        self._mouse_cb = ttk.Checkbutton(
            mouse_frame,
            text="Record mouse clicks (resolution-adaptive: stores % position)",
            variable=self._mouse_var,
        )
        self._mouse_cb.pack(side=tk.LEFT)

        # Output directory
        out_frame = ttk.Frame(main)
        out_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(out_frame, text="Output:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self._out_dir_var = tk.StringVar(value=self._output_dir)
        ttk.Entry(out_frame, textvariable=self._out_dir_var,
                  font=("Segoe UI", 8), width=48).pack(
            side=tk.LEFT, padx=(6, 4), fill=tk.X, expand=True)
        ttk.Button(out_frame, text="Browse", command=self._browse_output,
                   width=8).pack(side=tk.RIGHT)

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))

        # Log area
        ttk.Label(main, text="Log:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

        log_frame = ttk.Frame(main)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self._log_text = tk.Text(log_frame, height=6, width=58,
                                 font=("Consolas", 9), wrap=tk.WORD,
                                 state=tk.DISABLED, bg="#f5f5f5",
                                 relief=tk.FLAT, borderwidth=1)
        log_scroll = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom bar
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X, pady=(8, 0))

        self._trims_lbl = ttk.Label(
            bottom,
            text=f"Trimming: first {TRIM_START_SECONDS:.0f}s + last {TRIM_END_SECONDS:.0f}s",
            font=("Segoe UI", 8), foreground="gray")
        self._trims_lbl.pack(side=tk.LEFT)

        self._edit_btn = ttk.Button(bottom, text="Edit Last Recording",
                                    command=self._reopen_editor, width=18,
                                    state=tk.DISABLED)
        self._edit_btn.pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Button(bottom, text="Composer",
                   command=self._open_composer, width=12).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(bottom, text="Open Output Folder",
                   command=self._open_output_folder, width=18).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _set_status(self, state: str, message: str):
        colors = {
            "ready": COLOR_READY, "recording": COLOR_RECORDING,
            "processing": COLOR_PROCESSING, "done": COLOR_DONE,
        }
        color = colors.get(state, COLOR_READY)
        self._status_dot.delete("all")
        self._status_dot.create_oval(2, 2, 12, 12, fill=color, outline="")
        labels = {
            "ready": "Ready", "recording": "Recording...",
            "processing": "Processing...", "done": "Done!",
        }
        self._status_text.configure(text=labels.get(state, state))
        self._log(message)

    def _log(self, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        line = f"[{now}] {message}\n"
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, line)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _toggle_recording(self):
        if self._recorder.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        try:
            self._recorder.start(record_mouse=self._mouse_var.get())
        except RuntimeError as e:
            messagebox.showerror("Error", str(e))
            return

        self._set_status("recording", "Recording started! Switch to your target window.")
        self._record_btn.configure(text="Stop Recording")
        self._event_count_lbl.configure(text="Events recorded: 0")
        self._edit_btn.configure(state=tk.DISABLED)
        self._poll()

    def _stop_recording(self):
        self._set_status("processing", "Processing recording...")
        self._record_btn.configure(text="Start Recording", state=tk.DISABLED)
        self.root.update_idletasks()

        self._recording = self._recorder.stop()

        count = self._recording.event_count
        duration = self._recording.duration
        self._event_count_lbl.configure(text=f"Events recorded: {count}")
        self._log(f"Recording stopped. Duration: {duration:.1f}s, "
                  f"Events: {count} "
                  f"(keys: {self._recording.key_event_count}, "
                  f"mouse: {self._recording.mouse_event_count})")

        success = self._process(self._recording)

        self._record_btn.configure(state=tk.NORMAL)
        if success:
            notes = []
            if self._analyzed.hold_count > 0:
                notes.append(f"{self._analyzed.hold_count} key hold(s)")
            if self._analyzed.mouse_click_count > 0:
                notes.append(f"{self._analyzed.mouse_click_count} mouse click(s)")
            note_str = f", {', '.join(notes)}" if notes else ""
            self._set_status("done",
                             f"Timeline editor opened "
                             f"({self._analyzed.total_key_presses} keys, "
                             f"{self._analyzed.total_mouse_actions} mouse{note_str})")
            self._edit_btn.configure(state=tk.NORMAL)
        else:
            self._set_status("ready", "Processing failed. Check log.")

    def _on_hotkey_stop(self):
        self.root.after(0, self._hotkey_stop_handler)

    def _hotkey_stop_handler(self):
        if self._recorder.is_recording:
            self._log("Stop hotkey detected (ScrollLock+F6).")
            self._stop_recording()

    def _poll(self):
        if not self._recorder.is_recording:
            return
        count = self._recorder.event_count
        self._event_count_lbl.configure(text=f"Events recorded: {count}")
        self.root.after(self._poll_interval_ms, self._poll)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _process(self, recording: Recording) -> bool:
        """Trim and analyze, then open timeline editor. Returns True on success."""
        events = recording.events
        self._log(f"Raw events: {len(events)}")

        # Trim
        result = trim(events, TRIM_START_SECONDS, TRIM_END_SECONDS)
        if result.warning:
            self._log(f"Trimming warning: {result.warning}")
        if result.was_trimmed:
            removed = len(events) - len(result.events)
            self._log(f"Trimmed: {removed} events removed "
                      f"({len(result.events)} remaining)")
            events = result.events
        else:
            self._log("Trimming: skipped (recording too short or empty)")

        if not events:
            messagebox.showwarning(
                "No Events",
                "No key events remain after trimming.\n\n"
                "Possible causes:\n"
                "- Recording was too short\n"
                "- Only modifier keys were pressed\n"
                "- You didn't switch to the target window"
            )
            return False

        # Analyze
        self._analyzed = analyze(events)
        parts = []
        if self._analyzed.hold_count > 0:
            parts.append(f"{self._analyzed.hold_count} key hold(s)")
        if self._analyzed.mouse_click_count > 0:
            parts.append(f"{self._analyzed.mouse_click_count} mouse click(s)")
        if self._analyzed.mouse_hold_count > 0:
            parts.append(f"{self._analyzed.mouse_hold_count} mouse hold(s)")
        extra = ", ".join(parts)
        self._log(f"Analysis: {len(self._analyzed.key_groups)} key groups, "
                  f"{self._analyzed.total_key_presses} total presses, "
                  f"{len(self._analyzed.mouse_groups)} mouse actions"
                  + (f" ({extra})" if extra else "") +
                  f", {self._analyzed.skipped_events} skipped")

        if self._analyzed.skipped_events > 0 and self._analyzed.total_key_presses == 0:
            messagebox.showwarning(
                "Only Modifier Keys",
                "Only modifier keys (Shift, Ctrl, Alt) were recorded.\n"
                "These cannot be sent standalone by PowerShell SendKeys.\n\n"
                "Please record letter, number, or function keys."
            )
            return False

        # Open timeline editor (auto-save is gone; user must confirm in editor)
        self._open_editor()
        return True

    def _open_editor(self):
        """Open the timeline editor for the current analyzed sequence."""
        if self._analyzed is None:
            return
        if self._editor_open:
            return
        self._editor_open = True

        def on_destroy():
            self._editor_open = False

        editor = TimelineEditor(self.root, self._analyzed,
                                self._output_dir, STARTUP_DELAY_SECONDS)
        # Let the editor's own _on_close handle the confirmation dialog
        # Poll for editor close
        self._poll_editor(editor, on_destroy)

    def _poll_editor(self, editor, on_destroy):
        if editor.winfo_exists():
            self.root.after(500, lambda: self._poll_editor(editor, on_destroy))
        else:
            on_destroy()

    def _reopen_editor(self):
        """Re-open the editor for the most recent analysis."""
        if self._analyzed is not None:
            self._open_editor()

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------

    def _browse_output(self):
        folder = filedialog.askdirectory(
            initialdir=self._output_dir, title="Select Output Folder")
        if folder:
            self._output_dir = folder
            self._out_dir_var.set(folder)

    def _open_composer(self):
        """Open the Macro Composer tool."""
        from composer import MacroComposer
        MacroComposer(self.root, self._output_dir)

    def _open_output_folder(self):
        os.startfile(self._output_dir)

    def _on_close(self):
        if self._recorder.is_recording:
            self._recorder.stop()
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    MacroRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
