"""
Методы расчёта по странам: в каждом файле — METHOD (параметры расчёта) и CITIES (города).

METHOD:
    fajr, isha  — угол Солнца под горизонтом для Фаджра и Иши
    isha_min    — вместо угла: Иша через столько минут после Магриба
    elevation   — высота над уровнем моря, м (закат позже, восход раньше)
    offsets     — поправки в минутах
CITIES: (название, широта, долгота[, замены в METHOD]).

Чтобы добавить страну — новый файл по образцу и строчка в COUNTRIES.
"""

from . import russia, uzbekistan, kyrgyzstan, kazakhstan, tajikistan, azerbaijan

COUNTRIES = [russia, uzbekistan, kyrgyzstan, kazakhstan, tajikistan, azerbaijan]

# {город: (широта, долгота, метод)}; порядок — как в меню
CITIES = {
    c[0]: (c[1], c[2], {**country.METHOD, **(c[3] if len(c) > 3 else {})})
    for country in COUNTRIES for c in country.CITIES
}
