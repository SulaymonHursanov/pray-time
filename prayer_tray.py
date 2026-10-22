"""
Время намаза текстом прямо в панели задач Windows 11, слева от кнопки «Пуск».

Окошко — отдельное окно «поверх всех» с прозрачным фоном, лежащее на панели задач;
само следует за кнопкой «Пуск», когда та сдвигается, и прячется в полноэкранных приложениях.
Если слева от «Пуска» места нет («Пуск» у левого края в Windows 11 или Windows 10),
окошко стоит справа — слева от области уведомлений.
- Левой кнопкой мыши можно подвинуть отступ от «Пуска» (запоминается в prayer_tray.json).
- Правая кнопка — расписание на день, выбор города, «Сбросить положение», «Выход».
- За 10 минут до намаза — уведомление Windows и окошко один раз мигает зелёным.
- Когда наступает намаз, текст 15 минут подсвечен зелёным + уведомление Windows.

Файлы:       prayer_calc.py — расчёт времени, methods/ — методы и города по странам,
             win_utils.py — работа с Windows.
Установка:   pip install comtypes pystray pillow
             (comtypes — чтобы находить «Пуск», pystray+pillow — для уведомлений)
Запуск:      pythonw prayer_tray.py
"""

import json
import os
import sys
from datetime import datetime

import prayer_calc
import win_utils as win
from prayer_calc import compute, current_or_next

DEBUG = "--debug" in sys.argv   # python prayer_tray.py --debug

# ======================= НАСТРОЙКИ =======================
# Город и метод расчёта выбираются в меню; список городов — в methods/, остальное — в prayer_calc.py

UPDATE_SECONDS = 20

# Вид окошка
ACCENT = "#0e6e46"     # подсветка, когда намаз наступил
HIGHLIGHT_MINUTES = 15
REMIND_MINUTES = 10    # за сколько минут до намаза уведомить и один раз мигнуть (0 — выключено)
BLINK_MS = 800         # сколько длится мигание
SHOW_TRAY_ICON = True  # значок в трее нужен для уведомлений Windows
# =========================================================


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


def main():
    import tkinter as tk

    _mutex = win.single_instance("PrayTimeTrayMutex")   # только одна копия
    if _mutex is None:
        return
    win.set_dpi_aware()

    taskbar = win.find_taskbar()
    if not taskbar:
        raise SystemExit("Панель задач не найдена")

    light = win.is_light_theme()
    key = "#eeeeee" if light else "#202020"     # этот цвет станет прозрачным
    fg = "#000000" if light else "#ffffff"
    fg2 = "#404040" if light else "#c8c8c8"

    cfg = load_cfg()
    prayer_calc.set_city(cfg.get("city", prayer_calc.CITY))
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
    hwnd = win.make_tool_window(root)

    # Через прозрачный (-transparentcolor) фон клики проходят насквозь на панель задач.
    # Поэтому поверх кладём почти невидимое (alpha 1%) окно того же размера — оно ловит мышь.
    catcher = tk.Toplevel(root)
    catcher.overrideredirect(True)
    catcher.configure(bg="#000000")
    catcher.attributes("-alpha", 0.01)
    catcher.geometry(f"{W}x{H}+0+0")
    catcher.update_idletasks()
    chwnd = win.make_tool_window(catcher)
    if DEBUG:
        print(f"taskbar={taskbar} hwnd={hwnd} size={W}x{H}", flush=True)

    watcher = win.StartButtonWatcher(taskbar)
    GAP = 6

    dbg = {"n": 0}

    def offset_key():
        """Слева от «Пуска» нет места (выравнивание влево в Windows 11, Windows 10) —
        окошко стоит справа, слева от области уведомлений. У каждого места свой отступ."""
        left = win.window_rect(taskbar)[0]
        s = watcher.rect or win.child_rect(taskbar, "Start")   # в Windows 10 UIA «Пуск» может не найти
        if s is None:
            return "offset_right" if win.OLD_WINDOWS else "offset"
        return "offset_right" if s[0] - left < W + GAP else "offset"

    def place():
        if state.get("menu"):
            return
        if win.fullscreen_app(ignore=(taskbar, hwnd, chwnd)):
            win.hide(hwnd)
            win.hide(chwnd)
            return
        r = win.window_rect(taskbar)
        tbw, tbh = r[2] - r[0], r[3] - r[1]
        s = watcher.rect or win.child_rect(taskbar, "Start")
        k = offset_key()
        if k == "offset_right":
            tray_rect = win.child_rect(taskbar, "TrayNotifyWnd")
            anchor = (tray_rect[0] - r[0]) if tray_rect else tbw   # левый край трея
        else:
            anchor = (s[0] - r[0]) if s else (8 + W + GAP)   # левый край «Пуска»
        x = anchor - W - cfg.get(k, GAP)
        x = max(0, min(x, tbw - W))
        y = max(0, (tbh - H) // 2)
        # панель задач тоже topmost и поднимается при щелчке по ней — каждый раз возвращаемся наверх
        for h in (hwnd, chwnd):   # ловушка мыши — последней, то есть над надписью
            win.show_topmost(h, r[0] + x, r[1] + y, W, H)
        if DEBUG:
            dbg["n"] += 1
            if dbg["n"] % 4 == 1:
                print(f"taskbar={r} start={s} {k} -> x={x} y={y}",
                      flush=True)

    # --- перетаскивание: меняет отступ от «Пуска» (или от трея) ---
    drag = {}

    def on_press(e):
        drag["key"] = offset_key()
        drag["mx"], drag["off"] = e.x_root, cfg.get(drag["key"], GAP)

    def on_move(e):
        cfg[drag["key"]] = drag["off"] - (e.x_root - drag["mx"])
        place()

    def on_release(e):
        save_cfg(cfg)

    def on_menu(e):
        now = datetime.now()
        _, cur, _ = current_or_next(now, HIGHLIGHT_MINUTES)
        m = tk.Menu(root, tearoff=0)
        m.add_command(label=f"{prayer_calc.CITY}, {now:%d.%m.%Y}", state="disabled")
        m.add_separator()
        for name, tm in compute(now.date()).items():
            mark = "▶ " if name == cur else "    "
            m.add_command(label=f"{mark}{name}   {tm:%H:%M}")
        m.add_separator()
        cities = tk.Menu(m, tearoff=0)
        city_var = tk.StringVar(m, value=prayer_calc.CITY)
        for i, country in enumerate(prayer_calc.methods.COUNTRIES):
            if i:
                cities.add_separator()
            for c in country.CITIES:
                cities.add_radiobutton(label=c[0], value=c[0], variable=city_var,
                                       command=lambda n=c[0]: choose_city(n))
        m.add_cascade(label="Город", menu=cities)
        m.add_command(label="Сбросить положение",
                      command=lambda: (cfg.pop("offset", None), cfg.pop("offset_right", None),
                                       save_cfg(cfg), place()))
        m.add_command(label="Выход", command=lambda: state.update(quit=True))
        # пока меню открыто, place() не поднимает окошко наверх — иначе оно перекрывает меню
        # (на Windows tk_popup возвращается только после закрытия меню)
        state["menu"] = True
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            state["menu"] = False

    def choose_city(name):
        prayer_calc.set_city(name)
        cfg["city"] = name
        save_cfg(cfg)
        refresh()

    for w in (root, top, bottom, catcher):
        w.bind("<ButtonPress-1>", on_press)
        w.bind("<B1-Motion>", on_move)
        w.bind("<ButtonRelease-1>", on_release)
        w.bind("<Button-3>", on_menu)

    def notify(text):
        if tray:
            try:
                tray.notify(text, "Время намаза")
            except Exception:
                pass

    def blink():
        root.config(bg=ACCENT)
        top.config(bg=ACCENT, fg="#ffffff")
        bottom.config(bg=ACCENT, fg="#ffffff")
        root.after(BLINK_MS, refresh)   # refresh вернёт обычные цвета

    def refresh():
        now = datetime.now()
        kind, name, tm = current_or_next(now, HIGHLIGHT_MINUTES)
        top.config(text=f"{name} {tm:%H:%M}")
        if tray:
            tray.title = f"{name} в {tm:%H:%M}"
        if kind == "now":
            bg, f1, f2 = ACCENT, "#ffffff", "#ffffff"
            bottom.config(text="время наступило")
            k = (now.date(), name)
            if k not in notified:
                notified.add(k)
                notify(f"Наступило время намаза {name} ({tm:%H:%M})")
        else:
            bg, f1, f2 = key, fg, fg2
            mins = int((tm - now).total_seconds() // 60) + 1
            h, m = divmod(mins, 60)
            bottom.config(text=f"через {h} ч {m:02d} мин" if h else f"через {m} мин")
        root.config(bg=bg)
        top.config(bg=bg, fg=f1)
        bottom.config(bg=bg, fg=f2)
        if kind == "next" and mins <= REMIND_MINUTES:
            k = (tm.date(), name, "скоро")
            if k not in notified:
                notified.add(k)
                notify(f"Через {mins} мин — {name} ({tm:%H:%M})")
                blink()

    def tick_refresh():
        try:
            refresh()
        except Exception as e:
            top.config(text="Ошибка")
            bottom.config(text=str(e)[:20])
        root.after(UPDATE_SECONDS * 1000, tick_refresh)

    def tick_place():
        # если Проводник перезапустился — панель задач новая, выходим
        if state["quit"] or not win.is_window(taskbar):
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
