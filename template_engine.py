"""
Generate .bat launcher and 使用说明.txt documentation for the automation package.
Matches the exact format of the existing 自动开局/自动售卖 packages.
"""

import os
from analyzer import AnalyzedSequence


def generate_bat(ps1_filename: str = "automation_script.ps1") -> str:
    """Generate a .bat launcher that invokes the PowerShell script."""
    basename = ps1_filename.replace(".ps1", "")
    return f"""@echo off
setlocal

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0{basename}.ps1"

echo.
echo Script stopped. Press any key to close this window.
pause >nul
"""


def generate_readme(sequence: AnalyzedSequence,
                    script_name: str = "automation_script",
                    folder_name: str = "",
                    start_delay: int = 5) -> str:
    """
    Generate Chinese-language usage documentation.

    Args:
        sequence: The analyzed sequence for documentation.
        script_name: Base name of the .ps1 file (without extension).
        folder_name: Name of the output folder for display.
        start_delay: Startup delay in seconds.
    """
    interval_s = int(sequence.estimated_cycle_interval_ms / 1000.0)
    delay_ms = sequence.estimated_key_delay_ms
    total_presses = sequence.total_key_presses

    # Build sequence description
    seq_lines = _build_sequence_steps(sequence)
    seq_text = "\n".join(seq_lines)

    return f"""============================================
  自动宏脚本 - 使用说明
============================================

[功能说明]

这个脚本是通过 Macro Recorder 录制生成的，会在当前选中窗口中无限循环执行以下按键序列：

{seq_text}

每轮操作完成后等待 {interval_s} 秒，然后进入下一轮。
每次按键之间的间隔为 {delay_ms} 毫秒。
共 {total_presses} 次按键。

脚本启动后会先等待 {start_delay} 秒，方便你切换到目标窗口。


[文件说明]

  - {script_name}.ps1  ：主 PowerShell 脚本
  - run.bat            ：双击启动文件
  - 使用说明.txt       ：本说明文档


[运行方法]

  1. 双击 run.bat 启动脚本
  2. 出现 PowerShell 窗口后，在 {start_delay} 秒内切换到需要自动按键的目标窗口
  3. 脚本会自动开始循环按键


[停止方法]

  - 回到脚本运行的 PowerShell 窗口
  - 按 Ctrl + C 停止脚本
  - 如果提示确认，输入 Y 后回车
  - 如果窗口无响应，可直接关闭 PowerShell 窗口


[自定义修改方法]

  修改参数：用记事本打开 {script_name}.ps1，修改以下变量即可：

  $intervalSeconds = {interval_s}
    -> 每轮操作之间的等待时间（单位：秒）

  $clickDelayMilliseconds = {delay_ms}
    -> 每次按键之间的间隔（单位：毫秒）

  $startupDelaySeconds = {start_delay}
    -> 启动后等待切换窗口的时间（单位：秒）

  修改按键序列：找到 while ($true) 循环内的 SendWait 部分，
  根据需要增删或修改按键。


[注意事项]

  - 运行期间脚本会持续模拟键盘输入，请确保目标窗口正确
  - 避免将按键输入到聊天窗口、文档、命令行等不希望输入的位置
  - 不需要安装任何第三方软件，仅需 Windows 自带的 PowerShell


[环境要求]

  - Windows 操作系统
  - PowerShell（系统自带）
  - .NET Framework（系统自带）
"""


def _build_sequence_steps(sequence: AnalyzedSequence) -> list[str]:
    """Build numbered list of sequence steps for documentation."""
    from key_map import to_sendkeys

    steps: list[str] = []
    step_num = 1

    for item_type, item in sequence.all_actions_sorted():
        if item_type == 'mouse':
            mg = item
            btn_label = {"left": "鼠标左键", "right": "鼠标右键", "middle": "鼠标中键"}.get(
                mg.mouse_button, mg.mouse_button)
            if mg.is_hold:
                steps.append(f"  {step_num}. 移动到相对位置({mg.rel_x:.2%}, {mg.rel_y:.2%})，按住{btn_label} {mg.hold_duration_ms} 毫秒（拖拽）")
            else:
                steps.append(f"  {step_num}. 移动到相对位置({mg.rel_x:.2%}, {mg.rel_y:.2%})，点击{btn_label}")
            step_num += 1
            continue

        g = item  # KeyGroup
        if g.is_hold:
            sk = to_sendkeys(g.key_name)
            label = _key_label(sk) if sk else g.key_name.upper()
            steps.append(f"  {step_num}. 按住 {label} 键 {g.hold_duration_ms} 毫秒（长按）")
            step_num += 1
            continue

        sk = to_sendkeys(g.key_name)
        if sk is None:
            continue

        label = _key_label(sk)
        if g.count == 1:
            steps.append(f"  {step_num}. 按下 {label} 键 1 次")
        else:
            steps.append(f"  {step_num}. 按下 {label} 键 {g.count} 次")
        step_num += 1

    return steps


def _key_label(sendkeys_str: str) -> str:
    """Convert SendKeys code to a human-readable Chinese key name."""
    name_map = {
        "{ENTER}": "Enter（回车）",
        "{TAB}": "Tab",
        "{BACKSPACE}": "Backspace（退格）",
        "{DELETE}": "Delete",
        "{ESC}": "Esc",
        "{UP}": "上箭头",
        "{DOWN}": "下箭头",
        "{LEFT}": "左箭头",
        "{RIGHT}": "右箭头",
        "{HOME}": "Home",
        "{END}": "End",
        "{PGUP}": "Page Up",
        "{PGDN}": "Page Down",
        "{INSERT}": "Insert",
        "{F1}": "F1", "{F2}": "F2", "{F3}": "F3",
        "{F4}": "F4", "{F5}": "F5", "{F6}": "F6",
        "{F7}": "F7", "{F8}": "F8", "{F9}": "F9",
        "{F10}": "F10", "{F11}": "F11", "{F12}": "F12",
        " ": "Space（空格）",
        "{PRTSC}": "Print Screen",
        "{NUMLOCK}": "Num Lock",
        "{CAPSLOCK}": "Caps Lock",
    }
    if sendkeys_str in name_map:
        return name_map[sendkeys_str]
    if len(sendkeys_str) == 1:
        return sendkeys_str.upper()
    return sendkeys_str
