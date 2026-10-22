"""Рисует значок программы (тот же зелёный квадрат, что и в трее) в installer/PrayTime.ico."""
import os

from PIL import Image, ImageDraw

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PrayTime.ico")
img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, 255, 255), radius=48, fill=(14, 110, 70, 255))
# полумесяц
d.ellipse((58, 48, 198, 188), fill=(255, 255, 255, 255))
d.ellipse((92, 34, 222, 164), fill=(14, 110, 70, 255))
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
