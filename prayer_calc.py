"""
Расчёт времени намаза (алгоритм PrayTimes) для выбранного города.

Параметры расчёта по странам — в пакете methods.
"""

import math
from datetime import date, datetime, timedelta

import methods

DEFAULT_CITY = "Москва"
ASR_FACTOR = 2                    # 2 = ханафитский Аср, 1 = шафиитский (если в методе нет "asr")

# Поправки в минутах поверх метода, чтобы подогнать под нужную таблицу (например, moynamaz.ru)
OFFSETS = {"Фаджр": 0, "Восход": 0, "Зухр": 0, "Аср": 0, "Магриб": 0, "Иша": 0}

NAMES = ["Фаджр", "Восход", "Зухр", "Аср", "Магриб", "Иша"]

CITY = DEFAULT_CITY
LAT, LNG, METHOD = methods.CITIES[CITY]   # выбранный город, меняет set_city()


def set_city(name):
    """Выбрать город из methods.CITIES; неизвестное название (старый конфиг) — оставить текущий."""
    global CITY, LAT, LNG, METHOD
    if name in methods.CITIES:
        CITY = name
        LAT, LNG, METHOD = methods.CITIES[name]


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


def compute(day: date, lat=None, lng=None, tz=None, method=None):
    """Возвращает {название: datetime} на указанный день (по умолчанию — для выбранного города)."""
    if lat is None:
        lat, lng = LAT, LNG
    method = method or METHOD
    fajr_angle = method["fajr"]
    isha_angle = method.get("isha", 18.0)   # при isha_min угол нужен только для первого приближения
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

    rise_angle = 0.833 + 0.0347 * math.sqrt(max(method.get("elevation", 0), 0))
    t = {"Фаджр": 5, "Восход": 6, "Зухр": 12, "Аср": 13, "Магриб": 18, "Иша": 18}
    for _ in range(2):  # две итерации для точности
        p = {k: v / 24 for k, v in t.items()}
        t = {
            "Фаджр": angle_time(fajr_angle, p["Фаджр"], ccw=True),
            "Восход": angle_time(rise_angle, p["Восход"], ccw=True),
            "Зухр": mid_day(p["Зухр"]),
            "Аср": asr_time(method.get("asr", ASR_FACTOR), p["Аср"]),
            "Магриб": angle_time(rise_angle, p["Магриб"]),
            "Иша": angle_time(isha_angle, p["Иша"]),
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
    fajr_portion = fajr_angle / 60 * night
    isha_portion = isha_angle / 60 * night
    if _fix(t["Восход"] - t["Фаджр"], 24) > fajr_portion:
        t["Фаджр"] = t["Восход"] - fajr_portion
    if _fix(t["Иша"] - t["Магриб"], 24) > isha_portion:
        t["Иша"] = t["Магриб"] + isha_portion

    start = datetime(day.year, day.month, day.day)
    offsets = method.get("offsets", {})
    res = {
        k: start + timedelta(hours=t[k], minutes=offsets.get(k, 0) + OFFSETS.get(k, 0))
        for k in NAMES
    }
    if "isha_min" in method:
        res["Иша"] = res["Магриб"] + timedelta(minutes=method["isha_min"] + OFFSETS.get("Иша", 0))
    # округляем до минуты, как в таблицах (иначе %H:%M просто отбрасывает секунды)
    return {k: (v + timedelta(seconds=30)).replace(second=0, microsecond=0) for k, v in res.items()}


def next_prayer(now: datetime):
    """(название, время) ближайшего намаза; Восход пропускаем."""
    for d in (now.date(), now.date() + timedelta(days=1)):
        for name, tm in compute(d).items():
            if name != "Восход" and tm > now:
                return name, tm
    return None, None


def current_or_next(now, highlight_minutes):
    """('now', имя, время) если намаз наступил не раньше highlight_minutes назад,
    иначе ('next', имя, время)."""
    for name, tm in compute(now.date()).items():
        if name != "Восход" and tm <= now < tm + timedelta(minutes=highlight_minutes):
            return "now", name, tm
    name, tm = next_prayer(now)
    return "next", name, tm


if __name__ == "__main__":
    # Сверка с таблицей: python prayer_calc.py Город [ГГГГ-ММ-ДД] [часовой пояс, напр. 5]
    import sys
    args = sys.argv[1:]
    if not args or args[0] not in methods.CITIES:
        sys.exit("Город не найден. Есть: " + ", ".join(methods.CITIES))
    set_city(args[0])
    day = date.fromisoformat(args[1]) if len(args) > 1 else date.today()
    tz = float(args[2]) if len(args) > 2 else None   # по умолчанию — пояс Windows
    print(f"{CITY} ({LAT}, {LNG}), метод: {METHOD}")
    print("Дата        " + "  ".join(f"{n:>6}" for n in NAMES))
    for i in range(7):
        d = day + timedelta(days=i)
        print(f"{d:%d.%m.%Y}  " + "  ".join(f"{t:%H:%M}".rjust(6) for t in compute(d, tz=tz).values()))
