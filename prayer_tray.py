"""
Время намаза текстом прямо в панели задач Windows 11, слева от кнопки «Пуск».

Окошко — отдельное окно «поверх всех» с прозрачным фоном, лежащее на панели задач;
само следует за кнопкой «Пуск», когда та сдвигается, и прячется в полноэкранных приложениях.
- Левой кнопкой мыши можно подвинуть отступ от «Пуска» (запоминается в prayer_tray.json).
- Правая кнопка — расписание на день, «Сбросить положение», «Выход».
- Когда наступает намаз, текст 15 минут подсвечен зелёным + уведомление Windows.

Установка:   pip install comtypes pystray pillow
             (comtypes — чтобы находить «Пуск», pystray+pillow — для уведомлений)
Запуск:      pythonw prayer_tray.py
"""

import json
import math
import os
import sys

DEBUG = "--debug" in sys.argv   # python prayer_tray.py --debug
from datetime import date, datetime, timedelta

# ======================= НАСТРОЙКИ =======================
CITY = "Москва"
LAT, LNG = 55.7558, 37.6173      # координаты города
ELEVATION = 0                     # высота над уровнем моря, м

FAJR_ANGLE = 16.0                 # угол Солнца под горизонтом для Фаджра
ISHA_ANGLE = 15.0                 # угол для Иши (16/15 — метод ДУМ РФ)
ASR_FACTOR = 2                    # 2 = ханафитский Аср, 1 = шафиитский

# Поправки в минутах, чтобы подогнать под нужную таблицу (например, moynamaz.ru)
OFFSETS = {"Фаджр": 0, "Восход": 0, "Зухр": 0, "Аср": 0, "Магриб": 0, "Иша": 0}

UPDATE_SECONDS = 20

# Вид окошка
BG = "#1c1c1c"         # фон (под тёмную панель задач Windows 11)
FG = "#ffffff"         # основной текст
FG2 = "#b8b8b8"        # вторая строка
ACCENT = "#0e6e46"     # подсветка, когда намаз наступил
HIGHLIGHT_MINUTES = 15
SHOW_TRAY_ICON = True  # значок в трее нужен для уведомлений Windows
# =========================================================

NAMES = ["Фаджр", "Восход", "Зухр", "Аср", "Магриб", "Иша"]


# ---------- астрономия (алгоритм PrayTimes) ----------
def _dsin(d): return math.sin(math.radians(d))
def _dcos(d): return math.cos(math.radians(d))
def _dtan(d): return math.tan(math.radians(d))
def _darcsin(x): return math.degrees(math.asin(x))
def _darccos(x): return math.degrees(math.acos(x))
def _darctan2(y, x): return math.degrees(math.atan2(y, x))
def _darccot(x): return math.degrees(math.atan(1 / x))
def _fix(a, b): return a - b * math.floor(a / b)


def _julian(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _sun(jd):
    d = jd - 2451545.0
    g = _fix(357.529 + 0.98560028 * d, 360)
    q = _fix(280.459 + 0.98564736 * d, 360)
    l = _fix(q + 1.915 * _dsin(g) + 0.020 * _dsin(2 * g), 360)
    e = 23.439 - 0.00000036 * d
    ra = _darctan2(_dcos(e) * _dsin(l), _dcos(l)) / 15
    eqt = q / 15 - _fix(ra, 24)
    decl = _darcsin(_dsin(e) * _dsin(l))
    return decl, eqt


def compute(day: date, lat=LAT, lng=LNG, tz=None):
    """Возвращает {название: datetime} на указанный день."""
    if tz is None:
        tz = datetime.now().astimezone().utcoffset().total_seconds() / 3600
    jd = _julian(day.year, day.month, day.day) - lng / (15 * 24)

    def mid_day(t):
        return _fix(12 - _sun(jd + t)[1], 24)

    def angle_time(angle, t, ccw=False):
        decl = _sun(jd + t)[0]
        x = (-_dsin(angle) - _dsin(decl) * _dsin(lat)) / (_dcos(decl) * _dcos(lat))
        if x < -1 or x > 1:
            return float("nan")          # Солнце не достигает этого угла (белые ночи)
        t_ = _darccos(x) / 15
        return mid_day(t) + (-t_ if ccw else t_)

    def asr_time(factor, t):
        decl = _sun(jd + t)[0]
        angle = -_darccot(factor + _dtan(abs(lat - decl)))
        return angle_time(angle, t)

    rise_angle = 0.833 + 0.0347 * math.sqrt(max(ELEVATION, 0))
    t = {"Фаджр": 5, "Восход": 6, "Зухр": 12, "Аср": 13, "Магриб": 18, "Иша": 18}
    for _ in range(2):  # две итерации для точности
        p = {k: v / 24 for k, v in t.items()}
        t = {
            "Фаджр": angle_time(FAJR_ANGLE, p["Фаджр"], ccw=True),
            "Восход": angle_time(rise_angle, p["Восход"], ccw=True),
            "Зухр": mid_day(p["Зухр"]),
            "Аср": asr_time(ASR_FACTOR, p["Аср"]),
            "Магриб": angle_time(rise_angle, p["Магриб"]),
            "Иша": angle_time(ISHA_ANGLE, p["Иша"]),
        }
        # если угол недостижим (белые ночи) — ставим заведомо "далёкое" значение,
        # ниже его исправит правило высоких широт
        if math.isnan(t["Фаджр"]):
            t["Фаджр"] = t["Восход"] - 12
        if math.isnan(t["Иша"]):
            t["Иша"] = t["Магриб"] + 12

    # перевод из местного солнечного времени в часовой пояс
    t = {k: v + tz - lng / 15 for k, v in t.items()}

    # правило для высоких широт ("angle based"): летом в Москве сумерки не кончаются
    night = _fix(t["Восход"] - t["Магриб"], 24)
    fajr_portion = FAJR_ANGLE / 60 * night
    isha_portion = ISHA_ANGLE / 60 * night
    if _fix(t["Восход"] - t["Фаджр"], 24) > fajr_portion:
        t["Фаджр"] = t["Восход"] - fajr_portion
    if _fix(t["Иша"] - t["Магриб"], 24) > isha_portion:
        t["Иша"] = t["Магриб"] + isha_portion

    start = datetime(day.year, day.month, day.day)
    return {
        k: start + timedelta(hours=t[k], minutes=OFFSETS.get(k, 0))
        for k in NAMES
    }


def next_prayer(now: datetime):
    """(название, время) ближайшего намаза; Восход пропускаем."""
    for d in (now.date(), now.date() + timedelta(days=1)):
        for name, tm in compute(d).items():
            if name != "Восход" and tm > now:
                return name, tm
    return None, None


# ---------- окошко на панели задач ----------
# Настройки — в %APPDATA%\PrayTime: папка программы после установки может быть недоступна для записи
CFG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "PrayTime")
CFG_PATH = os.path.join(CFG_DIR, "prayer_tray.json")
_OLD_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prayer_tray.json")


def load_cfg():
    if not os.path.exists(CFG_PATH) and os.path.exists(_OLD_CFG_PATH):
        try:
            with open(_OLD_CFG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def current_or_next(now):
    """('now', имя, время) если намаз наступил недавно, иначе ('next', имя, время)."""
    for name, tm in compute(now.date()).items():
        if name != "Восход" and tm <= now < tm + timedelta(minutes=HIGHLIGHT_MINUTES):
            return "now", name, tm
    name, tm = next_prayer(now)
    return "next", name, tm


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


def main():
    import ctypes
    from ctypes import wintypes
    import tkinter as tk

    user32 = ctypes.windll.user32

    # только одна копия
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    _mutex = kernel32.CreateMutexW(None, False, "PrayTimeTrayMutex")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    HWND = wintypes.HWND
    user32.FindWindowW.restype = HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.GetParent.restype = HWND
    user32.GetParent.argtypes = [HWND]
    user32.SetParent.restype = HWND
    user32.SetParent.argtypes = [HWND, HWND]
    user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsWindow.argtypes = [HWND]
    user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    GetWL, SetWL = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
    GetWL.restype, GetWL.argtypes = ctypes.c_ssize_t, [HWND, ctypes.c_int]
    SetWL.restype, SetWL.argtypes = ctypes.c_ssize_t, [HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.GetForegroundWindow.restype = HWND
    user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_APPWINDOW = 0x00000080, 0x08000000, 0x00040000
    HWND_TOPMOST = HWND(-1)
    SW_HIDE = 0
    SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040

    taskbar = user32.FindWindowW("Shell_TrayWnd", None)
    if not taskbar:
        raise SystemExit("Панель задач не найдена")

    light = is_light_theme()
    key = "#eeeeee" if light else "#202020"     # этот цвет станет прозрачным
    fg = "#000000" if light else "#ffffff"
    fg2 = "#404040" if light else "#c8c8c8"

    cfg = load_cfg()
    state = {"quit": False}
    notified = set()

    # --- значок в трее только для уведомлений ---
    tray = None
    if SHOW_TRAY_ICON:
        try:
            import pystray
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(img).rounded_rectangle((0, 0, 63, 63), radius=12, fill=(14, 110, 70, 255))
            tray = pystray.Icon("prayer_times", img, "Время намаза", pystray.Menu(
                pystray.MenuItem("Выход", lambda: state.update(quit=True))))
            tray.run_detached()
        except Exception:
            tray = None

    root = tk.Tk()
    root.overrideredirect(True)
    if DEBUG:
        key = "#c00000"   # в режиме отладки фон красный и непрозрачный
    root.configure(bg=key)
    if not DEBUG:
        try:
            root.attributes("-transparentcolor", key)
        except Exception:
            pass

    top = tk.Label(root, font=("Segoe UI Semibold", 9), fg=fg, bg=key, width=16)
    bottom = tk.Label(root, font=("Segoe UI", 8), fg=fg2, bg=key, width=16)
    top.pack(pady=(0, 0))
    bottom.pack(pady=(0, 0))
    top.config(text="Фаджр 00:00")
    bottom.config(text="через 10 ч 00 мин")
    root.update_idletasks()
    W, H = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f"{W}x{H}+0+0")
    root.update_idletasks()

    # --- окно поверх панели задач ---
    # Дочернее окно панели задач (SetParent) новые сборки Windows 11 перекрывают своим
    # содержимым, поэтому окно отдельное: topmost, без значка в Alt+Tab и без захвата фокуса.
    hwnd = user32.GetParent(root.winfo_id())
    exstyle = GetWL(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    SetWL(hwnd, GWL_EXSTYLE, (exstyle | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW)
    if DEBUG:
        print(f"taskbar={taskbar} hwnd={hwnd} size={W}x{H}", flush=True)

    watcher = StartButtonWatcher(taskbar)
    GAP = 6

    dbg = {"n": 0}

    def fullscreen_app():
        """Активное окно занимает весь экран (игра, видео) — панель задач скрыта."""
        fg_hwnd = user32.GetForegroundWindow()
        if not fg_hwnd or fg_hwnd in (taskbar, hwnd):
            return False
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(fg_hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):   # рабочий стол
            return False
        fr = wintypes.RECT()
        user32.GetWindowRect(fg_hwnd, ctypes.byref(fr))
        return (fr.left <= 0 and fr.top <= 0 and fr.right >= user32.GetSystemMetrics(0)
                and fr.bottom >= user32.GetSystemMetrics(1))

    def place():
        if fullscreen_app():
            user32.ShowWindow(hwnd, SW_HIDE)
            return
        r = wintypes.RECT()
        user32.GetWindowRect(taskbar, ctypes.byref(r))
        tbw, tbh = r.right - r.left, r.bottom - r.top
        s = watcher.rect
        anchor = (s[0] - r.left) if s else (8 + W + GAP)   # левый край «Пуска»
        x = anchor - W - cfg.get("offset", GAP)
        x = max(0, min(x, tbw - W))
        y = max(0, (tbh - H) // 2)
        # панель задач тоже topmost и поднимается при щелчке по ней — каждый раз возвращаемся наверх
        user32.SetWindowPos(hwnd, HWND_TOPMOST, int(r.left + x), int(r.top + y), W, H,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)
        if DEBUG:
            dbg["n"] += 1
            if dbg["n"] % 4 == 1:
                print(f"taskbar=({r.left},{r.top},{r.right},{r.bottom}) start={s} -> x={x} y={y}",
                      flush=True)

    # --- перетаскивание: меняет отступ от «Пуска» ---
    drag = {}

    def on_press(e):
        drag["mx"], drag["off"] = e.x_root, cfg.get("offset", GAP)

    def on_move(e):
        cfg["offset"] = drag["off"] - (e.x_root - drag["mx"])
        place()

    def on_release(e):
        save_cfg(cfg)

    def on_menu(e):
        now = datetime.now()
        _, cur, _ = current_or_next(now)
        m = tk.Menu(root, tearoff=0)
        m.add_command(label=f"{CITY}, {now:%d.%m.%Y}", state="disabled")
        m.add_separator()
        for name, tm in compute(now.date()).items():
            mark = "▶ " if name == cur else "    "
            m.add_command(label=f"{mark}{name}   {tm:%H:%M}")
        m.add_separator()
        m.add_command(label="Сбросить положение",
                      command=lambda: (cfg.pop("offset", None), save_cfg(cfg), place()))
        m.add_command(label="Выход", command=lambda: state.update(quit=True))
        m.tk_popup(e.x_root, e.y_root)

    for w in (root, top, bottom):
        w.bind("<ButtonPress-1>", on_press)
        w.bind("<B1-Motion>", on_move)
        w.bind("<ButtonRelease-1>", on_release)
        w.bind("<Button-3>", on_menu)

    def refresh():
        now = datetime.now()
        kind, name, tm = current_or_next(now)
        top.config(text=f"{name} {tm:%H:%M}")
        if tray:
            tray.title = f"{name} в {tm:%H:%M}"
        if kind == "now":
            bg, f1, f2 = ACCENT, "#ffffff", "#ffffff"
            bottom.config(text="время наступило")
            k = (now.date(), name)
            if k not in notified:
                notified.add(k)
                if tray:
                    try:
                        tray.notify(f"Наступило время намаза {name} ({tm:%H:%M})", "Время намаза")
                    except Exception:
                        pass
        else:
            bg, f1, f2 = key, fg, fg2
            mins = int((tm - now).total_seconds() // 60) + 1
            h, m = divmod(mins, 60)
            bottom.config(text=f"через {h} ч {m:02d} мин" if h else f"через {m} мин")
        root.config(bg=bg)
        top.config(bg=bg, fg=f1)
        bottom.config(bg=bg, fg=f2)

    def tick_refresh():
        try:
            refresh()
        except Exception as e:
            top.config(text="Ошибка")
            bottom.config(text=str(e)[:20])
        root.after(UPDATE_SECONDS * 1000, tick_refresh)

    def tick_place():
        # если Проводник перезапустился — панель задач новая, выходим
        if state["quit"] or not user32.IsWindow(taskbar):
            watcher.stop = True
            if tray:
                try:
                    tray.stop()
                except Exception:
                    pass
            root.destroy()
            return
        place()
        root.after(250, tick_place)

    tick_refresh()
    tick_place()
    root.mainloop()


if __name__ == "__main__":
    main()
