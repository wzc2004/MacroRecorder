"""
Macro Composer — chains multiple saved recordings into a single
automation script, with per-macro loop counts and playlist ordering.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from analyzer import AnalyzedSequence
from cs_templates import CS_KEY_SIM, CS_MOUSE_SIM
from template_engine import generate_bat, generate_readme


SCAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MacroOutputs")
PS1_FILENAME = "composed_script.ps1"
BAT_FILENAME = "run.bat"
README_FILENAME = "使用说明.txt"


# ---------------------------------------------------------------------------
# Scan saved macros
# ---------------------------------------------------------------------------

def scan_macros(scan_dir: str = SCAN_DIR) -> list[dict]:
    """Find all directories containing recording.json and return macro info."""
    macros = []
    if not os.path.isdir(scan_dir):
        return macros

    for entry in os.listdir(scan_dir):
        folder = os.path.join(scan_dir, entry)
        json_path = os.path.join(folder, "recording.json")
        if os.path.isdir(folder) and os.path.isfile(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                macros.append({
                    "name": data.get("name", entry),
                    "folder": entry,
                    "path": folder,
                    "json_path": json_path,
                    "created": data.get("created", ""),
                    "data": data,
                })
            except Exception:
                continue

    macros.sort(key=lambda m: m["created"], reverse=True)
    return macros


# ---------------------------------------------------------------------------
# Generate combined PS1
# ---------------------------------------------------------------------------

def generate_composed_ps1(playlist: list[dict],
                           start_delay: int = 5,
                           total_loop_count: int = 0) -> str:
    """
    Generate a combined PowerShell script from a playlist of macros.

    Args:
        playlist: List of dicts with keys: name, data, repeat_count
        start_delay: Delay before starting (for window switching).

    Returns:
        Complete .ps1 script content.
    """
    lines: list[str] = []
    all_sequences: list[tuple[str, AnalyzedSequence, int]] = []

    # Parse all sequences first
    for item in playlist:
        name = item["name"]
        repeat = item.get("repeat_count", 1)
        seq_data = item["data"]["sequence"]
        seq = AnalyzedSequence.from_dict(seq_data)
        all_sequences.append((name, seq, repeat))

    # Collect which Add-Type blocks are needed
    has_holds = any(
        any(g.is_hold for g in s.key_groups)
        for _, s, _ in all_sequences
    )
    has_mouse = any(
        len(s.mouse_groups) > 0
        for _, s, _ in all_sequences
    )
    has_keys = any(
        len(s.key_groups) > 0
        for _, s, _ in all_sequences
    )

    # Header
    lines.append("Add-Type -AssemblyName System.Windows.Forms")

    if has_keys:
        lines.append("")
        lines.append(CS_KEY_SIM)

    if has_mouse:
        lines.append("")
        lines.append(CS_MOUSE_SIM)

    lines.append("")
    lines.append("")
    lines.append(f"$startupDelaySeconds = {start_delay}")
    lines.append("")

    # Description
    desc_parts = []
    for name, _, repeat in all_sequences:
        if repeat == 1:
            desc_parts.append(name)
        else:
            desc_parts.append(f"{name} x{repeat}")
    desc = " -> ".join(desc_parts)
    lines.append("Write-Host 'Composed Macro Script'")
    lines.append(f"Write-Host 'Playlist: {desc}'")
    lines.append(f'Write-Host "Switch to the target window now. Starting in $startupDelaySeconds seconds..."')
    lines.append("Start-Sleep -Seconds $startupDelaySeconds")
    lines.append("")

    # Main loop
    if total_loop_count > 0:
        lines.append(f"for ($_total = 0; $_total -lt {total_loop_count}; $_total++) {{")
    else:
        lines.append("while ($true) {")

    first_macro = True
    for name, seq, repeat in all_sequences:
        interval_s = max(seq.estimated_cycle_interval_ms / 1000.0, 1.0)
        delay_ms = seq.estimated_key_delay_ms

        lines.append(f"    # === Macro: {name} (x{repeat}) ===")
        lines.append(f"    Write-Host '>> Stage: {name}'")

        if repeat == 1:
            # Single run — generate inline
            _gen_sequence_body(seq, lines, delay_ms, first_macro)
            first_macro = False
            lines.append(f"    Start-Sleep -Seconds {interval_s:.0f}")
        else:
            # Repeat N times
            lines.append(f"    for ($_rep = 0; $_rep -lt {repeat}; $_rep++) {{")
            _gen_sequence_body(seq, lines, delay_ms, first_macro, indent="        ")
            first_macro = False
            lines.append(f"        Start-Sleep -Seconds {interval_s:.0f}")
            lines.append("    }")

    # Outer cycle interval — wait before repeating the full playlist
    total_cycle = max(
        int(sum(
            max(s.estimated_cycle_interval_ms, 1000)
            for _, s, _ in all_sequences
        ) / 1000.0),
        2,
    )
    lines.append("")
    lines.append(f"    Start-Sleep -Seconds {total_cycle}")
    lines.append("}")

    return "\n".join(lines) + "\n"


def _gen_sequence_body(seq: AnalyzedSequence, lines: list[str],
                        default_delay_ms: int, first: bool,
                        indent: str = "    "):
    """Generate the key/mouse actions for one sequence (without outer loop)."""
    from code_generator import _gen_key_action, _gen_mouse_action, _get_delay_before

    all_items = seq.all_actions_sorted()
    is_first_in_seq = True
    for item_type, item in all_items:
        delay = _get_delay_before(item)
        if delay > 0:
            lines.append(f"{indent}Start-Sleep -Milliseconds {delay}")
        elif not is_first_in_seq:
            pass

        if item_type == 'mouse':
            _gen_mouse_action_inline(item, lines, indent)
        else:
            _gen_key_action_inline(item, lines, indent, default_delay_ms)

        is_first_in_seq = False


def _gen_key_action_inline(group, lines: list[str], indent: str,
                            default_delay_ms: int):
    """Inline version of _gen_key_action (see code_generator.py)."""
    from key_map import to_vk_code

    vk = to_vk_code(group.key_name)
    if vk is None:
        return

    if group.is_hold:
        lines.append(f"{indent}[KeySim]::HoldKey(0x{vk:02X}, {group.hold_duration_ms})")
        return

    intra_ms = int(group.avg_interval_ms) if group.avg_interval_ms > 0 else 0

    if group.count >= 3:
        delay_str = str(intra_ms) if intra_ms > 0 else str(default_delay_ms)
        lines.append(f"{indent}for ($i = 0; $i -lt {group.count}; $i++) {{")
        lines.append(f"{indent}    [KeySim]::TapKey(0x{vk:02X})")
        lines.append(f"{indent}    Start-Sleep -Milliseconds {delay_str}")
        lines.append(f"{indent}}}")
    else:
        for j in range(group.count):
            lines.append(f"{indent}[KeySim]::TapKey(0x{vk:02X})")
            if j < group.count - 1 and intra_ms > 0:
                lines.append(f"{indent}Start-Sleep -Milliseconds {intra_ms}")


def _gen_mouse_action_inline(group, lines: list[str], indent: str):
    """Inline version of _gen_mouse_action (see code_generator.py)."""
    btn = group.mouse_button
    lines.append(f"{indent}[MouseSim]::MoveTo({group.rel_x}, {group.rel_y})")
    lines.append(f"{indent}Start-Sleep -Milliseconds 50")
    if group.is_hold:
        if group.drag_path:
            for mx, my in group.drag_path:
                lines.append(f"{indent}[MouseSim]::MoveTo({mx}, {my})")
                lines.append(f"{indent}Start-Sleep -Milliseconds 20")
        lines.append(f'{indent}[MouseSim]::Hold("{btn}", {group.hold_duration_ms})')
    elif group.drag_path:
        for mx, my in group.drag_path:
            lines.append(f"{indent}[MouseSim]::MoveTo({mx}, {my})")
            lines.append(f"{indent}Start-Sleep -Milliseconds 20")
        lines.append(f'{indent}[MouseSim]::Click("{btn}")')
    else:
        lines.append(f'{indent}[MouseSim]::Click("{btn}")')


# ---------------------------------------------------------------------------
# Composer UI
# ---------------------------------------------------------------------------

class MacroComposer(tk.Toplevel):
    """Window for composing multiple macros into one script."""

    def __init__(self, parent, output_dir: str = None):
        super().__init__(parent)
        self.title("宏组合器 - Macro Composer")
        self.geometry("780x540")
        self.minsize(600, 400)

        self._output_dir = output_dir or SCAN_DIR
        self._macros = scan_macros(self._output_dir)
        self._playlist: list[dict] = []  # {name, data, repeat_count}

        self._build_ui()
        self._refresh_macro_list()

        self.transient(parent)
        self.grab_set()
        self.lift()

    def _build_ui(self):
        outer = ttk.Frame(self, padding="12 10 12 10")
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="宏组合器",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(outer, text="将已保存的宏按播放列表顺序组合成一个自动化脚本",
                  font=("Segoe UI", 9), foreground="gray").pack(anchor=tk.W, pady=(2, 8))

        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))

        # Two-panel layout
        panels = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        panels.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Left: saved macros
        left_frame = ttk.LabelFrame(panels, text="已保存的宏", padding="4 4 4 4")
        panels.add(left_frame, weight=1)

        self._macro_listbox = tk.Listbox(left_frame, font=("Segoe UI", 9),
                                          selectmode=tk.SINGLE)
        self._macro_listbox.pack(fill=tk.BOTH, expand=True)

        # Right: playlist
        right_frame = ttk.LabelFrame(panels, text="播放列表", padding="4 4 4 4")
        panels.add(right_frame, weight=2)

        # Playlist treeview
        cols = ("name", "repeat")
        self._playlist_tree = ttk.Treeview(right_frame, columns=cols,
                                            show="headings", height=8,
                                            selectmode="browse")
        self._playlist_tree.heading("name", text="宏名称")
        self._playlist_tree.heading("repeat", text="重复次数")
        self._playlist_tree.column("name", width=280, anchor=tk.W)
        self._playlist_tree.column("repeat", width=100, anchor=tk.CENTER)
        self._playlist_tree.pack(fill=tk.BOTH, expand=True)

        # Drag-drop support
        self._drag_data = {"item": None, "y": 0}
        self._playlist_tree.bind("<ButtonPress-1>", self._on_drag_start)
        self._playlist_tree.bind("<B1-Motion>", self._on_drag_motion)
        self._playlist_tree.bind("<ButtonRelease-1>", self._on_drag_stop)

        # Playlist buttons
        pl_btn_frame = ttk.Frame(right_frame)
        pl_btn_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(pl_btn_frame, text="移除", command=self._remove_from_playlist,
                   width=8).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_frame, text="修改次数", command=self._edit_repeat,
                   width=10).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_frame, text="上移", command=self._move_up,
                   width=6).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_frame, text="下移", command=self._move_down,
                   width=6).pack(side=tk.LEFT)

        # Add button (between panels)
        btn_mid_frame = ttk.Frame(outer)
        btn_mid_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btn_mid_frame, text=">> 添加到播放列表 >>",
                   command=self._add_to_playlist, width=30).pack()

        # Bottom
        ttk.Separator(outer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))

        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X)

        ttk.Button(bottom, text="刷新列表",
                   command=self._refresh_macro_list, width=14).pack(side=tk.LEFT)

        ttk.Label(bottom, text="总循环次数 (0=无限):",
                  font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(12, 4))
        self._var_total_loop = tk.StringVar(value="0")
        ttk.Entry(bottom, textvariable=self._var_total_loop, width=5,
                  font=("Segoe UI", 9)).pack(side=tk.LEFT)

        ttk.Button(bottom, text="生成组合脚本",
                   command=self._generate, width=20).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(bottom, text="取消",
                   command=self.destroy, width=10).pack(side=tk.RIGHT)

    def _refresh_macro_list(self):
        self._macros = scan_macros(self._output_dir)
        self._macro_listbox.delete(0, tk.END)
        for m in self._macros:
            self._macro_listbox.insert(tk.END, m["name"])

    def _add_to_playlist(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先从左侧列表中选择一个宏。")
            return
        idx = sel[0]
        if idx >= len(self._macros):
            return

        macro = self._macros[idx]
        repeat = simpledialog.askinteger(
            "重复次数",
            f'"{macro["name"]}" 要重复多少次?',
            initialvalue=1, minvalue=1, maxvalue=9999, parent=self)
        if repeat is None:
            return

        self._playlist.append({
            "name": macro["name"],
            "data": macro["data"],
            "repeat_count": repeat,
        })
        self._playlist_tree.insert("", tk.END,
                                   values=(macro["name"], repeat))
        self._playlist_tree.yview_moveto(1.0)

    def _remove_from_playlist(self):
        sel = self._playlist_tree.selection()
        if not sel:
            return
        # Find index
        all_items = self._playlist_tree.get_children()
        idx = all_items.index(sel[0])
        self._playlist_tree.delete(sel[0])
        if idx < len(self._playlist):
            self._playlist.pop(idx)

    def _edit_repeat(self):
        sel = self._playlist_tree.selection()
        if not sel:
            return
        all_items = self._playlist_tree.get_children()
        idx = all_items.index(sel[0])
        if idx >= len(self._playlist):
            return

        current = self._playlist[idx]["repeat_count"]
        new_val = simpledialog.askinteger(
            "修改次数",
            f'"{self._playlist[idx]["name"]}" 新的重复次数:',
            initialvalue=current, minvalue=1, maxvalue=9999, parent=self)
        if new_val is None:
            return

        self._playlist[idx]["repeat_count"] = new_val
        self._playlist_tree.item(sel[0], values=(self._playlist[idx]["name"], new_val))

    # ------------------------------------------------------------------
    # Drag-drop reordering
    # ------------------------------------------------------------------

    def _on_drag_start(self, event):
        """Record the item being dragged."""
        item = self._playlist_tree.identify_row(event.y)
        if item:
            self._drag_data["item"] = item
            self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        """Show a visual indicator while dragging."""
        if self._drag_data["item"]:
            self._drag_data["y"] = event.y

    def _on_drag_stop(self, event):
        """Drop the item at its new position."""
        src_item = self._drag_data.get("item")
        self._drag_data["item"] = None
        if not src_item:
            return

        # Find the target position
        target_item = self._playlist_tree.identify_row(event.y)
        all_items = self._playlist_tree.get_children()
        if not target_item or target_item == src_item:
            return

        src_idx = all_items.index(src_item)
        target_idx = all_items.index(target_item)

        # Reorder playlist
        item_data = self._playlist.pop(src_idx)
        self._playlist.insert(target_idx, item_data)

        # Rebuild tree
        self._rebuild_playlist_tree()
        # Re-select the moved item
        new_items = self._playlist_tree.get_children()
        if target_idx < len(new_items):
            self._playlist_tree.selection_set(new_items[target_idx])

    # ------------------------------------------------------------------
    # Playlist ordering buttons (kept for precision)
    # ------------------------------------------------------------------

    def _move_up(self):
        sel = self._playlist_tree.selection()
        if not sel:
            return
        all_items = self._playlist_tree.get_children()
        idx = all_items.index(sel[0])
        if idx <= 0:
            return

        # Swap in playlist
        self._playlist[idx], self._playlist[idx - 1] = \
            self._playlist[idx - 1], self._playlist[idx]
        # Rebuild tree
        self._rebuild_playlist_tree()
        # Re-select
        new_items = self._playlist_tree.get_children()
        self._playlist_tree.selection_set(new_items[idx - 1])

    def _move_down(self):
        sel = self._playlist_tree.selection()
        if not sel:
            return
        all_items = self._playlist_tree.get_children()
        idx = all_items.index(sel[0])
        if idx >= len(self._playlist) - 1:
            return

        self._playlist[idx], self._playlist[idx + 1] = \
            self._playlist[idx + 1], self._playlist[idx]
        self._rebuild_playlist_tree()
        new_items = self._playlist_tree.get_children()
        self._playlist_tree.selection_set(new_items[idx + 1])

    def _rebuild_playlist_tree(self):
        self._playlist_tree.delete(*self._playlist_tree.get_children())
        for item in self._playlist:
            self._playlist_tree.insert("", tk.END,
                                       values=(item["name"], item["repeat_count"]))

    def _generate(self):
        if not self._playlist:
            messagebox.showinfo("播放列表为空", "请至少添加一个宏到播放列表。")
            return

        # Output folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"Composed_{timestamp}"
        folder_path = os.path.join(self._output_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        total_loop = int(self._var_total_loop.get() or "0")
        ps1_content = generate_composed_ps1(self._playlist,
                                             total_loop_count=total_loop)
        with open(os.path.join(folder_path, PS1_FILENAME), "w",
                  encoding="utf-8-sig") as f:
            f.write(ps1_content)

        # Generate BAT
        from template_engine import generate_bat
        bat_content = generate_bat(PS1_FILENAME)
        with open(os.path.join(folder_path, BAT_FILENAME), "w",
                  encoding="ascii") as f:
            f.write(bat_content)

        # Generate README
        desc_parts = []
        for item in self._playlist:
            if item["repeat_count"] == 1:
                desc_parts.append(f'{item["name"]} x1')
            else:
                desc_parts.append(f'{item["name"]} x{item["repeat_count"]}')
        playlist_desc = " -> ".join(desc_parts)

        readme = f"""============================================
  Composed Macro Script - 使用说明
============================================

[功能说明]

这个脚本由 Macro Composer 生成，按播放列表顺序执行多个宏：

  {playlist_desc}

整个播放列表会无限循环执行。


[播放列表内容]

"""
        for i, item in enumerate(self._playlist):
            readme += f"  {i + 1}. {item['name']} — 重复 {item['repeat_count']} 次\n"

        readme += f"""
[运行方法]

  1. 双击 run.bat
  2. 在 5 秒内切换到目标窗口
  3. 脚本按播放列表顺序自动执行


[停止方法]

  按 Ctrl + C


[文件说明]

  - {PS1_FILENAME} ：主 PowerShell 脚本
  - {BAT_FILENAME} ：双击启动文件
  - {README_FILENAME} ：本说明文档
"""
        with open(os.path.join(folder_path, README_FILENAME), "w",
                  encoding="utf-8") as f:
            f.write(readme)

        self._status = f"Saved to: {folder_path}"
        messagebox.showinfo("完成", f"组合脚本已保存到:\n{folder_path}")
        self.destroy()
