# MacroRecorder

Keyboard & mouse macro recorder for Windows. Records your operations in the background and generates ready-to-run PowerShell automation scripts (.ps1).

## Features

- **Global recording** — captures keyboard and mouse events system-wide via pynput
- **Long-press detection** — keys held >1s are replayed as HoldKey via Win32 keybd_event
- **Mouse recording** — clicks and drags stored as screen percentages (resolution-adaptive)
- **Per-action timing** — each action's delay matches the original recording, not a median
- **Timeline editor** — visual table to adjust delays, hold durations, loop count before saving
- **Macro Composer** — chain multiple saved macros into a playlist with per-macro repeat counts
- **UTF-8 BOM output** — generated .ps1 files work correctly with Chinese text
- **Auto-environment setup** — `environment.bat` auto-installs Python + pynput on fresh machines

## Quick Start

```
1. Double-click install.bat
2. Click "Start Recording"
3. Switch to your target window within 5 seconds
4. Perform one complete cycle of your operation
5. Press ScrollLock + F6 to stop (no need to switch back)
6. Adjust timing in the Timeline Editor (optional)
7. Click Save, enter a name
8. Open MacroOutputs/your-name/ and double-click run.bat
```

## Requirements

- Windows OS
- Python 3.7+ (if missing, run `environment.bat` for auto-install)
- pynput (auto-installed by install.bat)

## Project Structure

```
MacroRecorder/
  main.py              # Tkinter GUI
  recorder.py          # pynput keyboard + mouse listener
  trimmer.py           # First/last 5s trimming
  analyzer.py          # Press/release pairing, hold detection, pattern grouping
  code_generator.py    # Generate .ps1 from analyzed sequence
  composer.py          # Chain multiple macros into one script
  template_engine.py   # Generate .bat launcher + documentation
  key_map.py           # Key name -> SendKeys / VK code mapping
  cs_templates.py      # Shared C# code (KeySim, MouseSim)
  install.bat          # One-click launcher
  environment.bat      # Auto environment setup
  MacroRecorder使用手册.txt  # Full manual (Chinese)
```

## Generated Output

Each recording produces a folder containing:
- `automation_script.ps1` — main PowerShell script
- `run.bat` — double-click launcher
- `使用说明.txt` — usage instructions (Chinese)
- `recording.json` — macro data (for the Composer)

## Stopping Scripts

Press `Ctrl+C` in the PowerShell window.

## Notes

- Modifier keys (Ctrl/Shift/Alt) are not supported standalone
- Key combinations (Ctrl+C, etc.) are not yet supported
- The first and last 5 seconds of each recording are automatically trimmed
