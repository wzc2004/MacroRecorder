"""
Shared C# code templates used by both code_generator.py and composer.py.
Single source of truth — edit here, both generators pick up the change.
"""

# Keyboard simulation via Win32 keybd_event
CS_KEY_SIM = r"""Add-Type @"
using System;
using System.Runtime.InteropServices;
public class KeySim {
    private const uint KEYEVENTF_KEYDOWN = 0x0000;
    private const uint KEYEVENTF_KEYUP = 0x0002;

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    public static void TapKey(byte vkCode) {
        keybd_event(vkCode, 0, KEYEVENTF_KEYDOWN, UIntPtr.Zero);
        keybd_event(vkCode, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    }

    public static void HoldKey(byte vkCode, int durationMs) {
        keybd_event(vkCode, 0, KEYEVENTF_KEYDOWN, UIntPtr.Zero);
        System.Threading.Thread.Sleep(durationMs);
        keybd_event(vkCode, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
        System.Threading.Thread.Sleep(50);
        keybd_event(vkCode, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);  // ensure release
    }

    public static void ComboKey(byte modVk, byte keyVk) {
        keybd_event(modVk, 0, KEYEVENTF_KEYDOWN, UIntPtr.Zero);
        keybd_event(keyVk, 0, KEYEVENTF_KEYDOWN, UIntPtr.Zero);
        System.Threading.Thread.Sleep(30);
        keybd_event(keyVk, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
        keybd_event(modVk, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    }
}
"@"""

# Mouse simulation via Win32 mouse_event + SetCursorPos + GetSystemMetrics
CS_MOUSE_SIM = r"""Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MouseSim {
    private const uint MOUSEEVENTF_LEFTDOWN   = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP     = 0x0004;
    private const uint MOUSEEVENTF_RIGHTDOWN  = 0x0008;
    private const uint MOUSEEVENTF_RIGHTUP    = 0x0010;
    private const uint MOUSEEVENTF_MIDDLEDOWN = 0x0020;
    private const uint MOUSEEVENTF_MIDDLEUP   = 0x0040;

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int nIndex);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy,
                                           uint dwData, UIntPtr dwExtraInfo);

    private const int SM_CXSCREEN = 0;
    private const int SM_CYSCREEN = 1;

    public static void MoveTo(double relX, double relY) {
        int screenW = GetSystemMetrics(SM_CXSCREEN);
        int screenH = GetSystemMetrics(SM_CYSCREEN);
        int absX = (int)(relX * screenW);
        int absY = (int)(relY * screenH);
        SetCursorPos(absX, absY);
    }

    public static void Click(string button) {
        uint down, up;
        GetFlags(button, out down, out up);
        mouse_event(down, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(30);
        mouse_event(up, 0, 0, 0, UIntPtr.Zero);
    }

    public static void DoubleClick(string button) {
        Click(button);
        System.Threading.Thread.Sleep(50);
        Click(button);
    }

    public static void Hold(string button, int durationMs) {
        uint down, up;
        GetFlags(button, out down, out up);
        mouse_event(down, 0, 0, 0, UIntPtr.Zero);
        System.Threading.Thread.Sleep(durationMs);
        mouse_event(up, 0, 0, 0, UIntPtr.Zero);
    }

    private static void GetFlags(string button, out uint down, out uint up) {
        switch (button.ToLower()) {
            case "left":
                down = MOUSEEVENTF_LEFTDOWN; up = MOUSEEVENTF_LEFTUP; break;
            case "right":
                down = MOUSEEVENTF_RIGHTDOWN; up = MOUSEEVENTF_RIGHTUP; break;
            case "middle":
                down = MOUSEEVENTF_MIDDLEDOWN; up = MOUSEEVENTF_MIDDLEUP; break;
            default:
                down = MOUSEEVENTF_LEFTDOWN; up = MOUSEEVENTF_LEFTUP; break;
        }
    }
}
"@"""
