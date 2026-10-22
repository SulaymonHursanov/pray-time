"""
Работа с Windows: панель задач, кнопка «Пуск», окна «поверх всех», тема, одна копия программы.
"""

import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

HWND = wintypes.HWND
user32.FindWindowW.restype = HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = HWND
user32.FindWindowExW.argtypes = [HWND, HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.GetParent.restype = HWND
user32.GetParent.argtypes = [HWND]
user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsWindow.argtypes = [HWND]
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
_GetWL, _SetWL = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
_GetWL.restype, _GetWL.argtypes = ctypes.c_ssize_t, [HWND, ctypes.c_int]
_SetWL.restype, _SetWL.argtypes = ctypes.c_ssize_t, [HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.GetForegroundWindow.restype = HWND
user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
kernel32.CreateMutexW.restype = wintypes.HANDLE

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_APPWINDOW = 0x00000080, 0x08000000, 0x00040000
HWND_TOPMOST = HWND(-1)
SW_HIDE = 0
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040

OLD_WINDOWS = sys.getwindowsversion().build < 22000   # Windows 10


def single_instance(name):
    """Мьютекс «уже запущено»: None, если копия уже работает. Ссылку на результат нужно держать."""
    mutex = kernel32.CreateMutexW(None, False, name)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return mutex


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def find_taskbar():
    return user32.FindWindowW("Shell_TrayWnd", None)


def is_window(hwnd):
    return bool(user32.IsWindow(hwnd))


def window_rect(hwnd):
    """(left, top, right, bottom) окна."""
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def child_rect(parent, cls):
    """Прямоугольник дочернего окна (Win32) с классом cls или None."""
    h = user32.FindWindowExW(parent, None, cls, None)
    if not h:
        return None
    r = window_rect(h)
    return r if r[2] > r[0] else None


def make_tool_window(tk_window):
    """Окно tkinter без значка в Alt+Tab и без захвата фокуса; возвращает его HWND."""
    h = user32.GetParent(tk_window.winfo_id())
    ex = _GetWL(h, GWL_EXSTYLE) & 0xFFFFFFFF
    _SetWL(h, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW)
    return h


def show_topmost(hwnd, x, y, w, h):
    user32.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW)


def hide(hwnd):
    user32.ShowWindow(hwnd, SW_HIDE)


def fullscreen_app(ignore=()):
    """Активное окно занимает весь экран (игра, видео) — панель задач скрыта."""
    fg_hwnd = user32.GetForegroundWindow()
    if not fg_hwnd or fg_hwnd in ignore:
        return False
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(fg_hwnd, cls, 64)
    if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):   # рабочий стол
        return False
    left, top, right, bottom = window_rect(fg_hwnd)
    return (left <= 0 and top <= 0 and right >= user32.GetSystemMetrics(0)
            and bottom >= user32.GetSystemMetrics(1))


def is_light_theme():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "SystemUsesLightTheme")[0] == 1
    except Exception:
        return False


class StartButtonWatcher:
    """В фоне следит, где сейчас кнопка «Пуск» (через UI Automation, нужен comtypes)."""

    def __init__(self, taskbar_hwnd):
        import threading
        self.taskbar = taskbar_hwnd
        self.rect = None
        self.stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import time as _t
        try:
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning, module="comtypes")
            warnings.filterwarnings("ignore", message=".*comtypes.*")
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as U
            uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
        except Exception:
            return  # comtypes не установлен — работаем по сохранённому положению
        el = None
        while not self.stop:
            try:
                if el is None:
                    root_el = uia.ElementFromHandle(self.taskbar)
                    cond = uia.CreatePropertyCondition(U.UIA_AutomationIdPropertyId, "StartButton")
                    el = root_el.FindFirst(U.TreeScope_Descendants, cond)
                if el:
                    r = el.CurrentBoundingRectangle
                    self.rect = (r.left, r.top, r.right, r.bottom) if r.right > r.left else None
                    if self.rect is None:
                        el = None
            except Exception:
                el, self.rect = None, None
            _t.sleep(0.5)
