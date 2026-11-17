"""Версии снимка первого экрана для srcset: WebP 960/1440 и AVIF 960/1440/2880.

Источник — assets/hero-home.webp (2880×1568, эталон владельца; сам файл не меняется).
Запуск из корня репозитория: python tools/scenes/hero_sizes.py
Результат коммитится в assets/; сборка (build.py) эти файлы только копирует.
"""
import pathlib
from PIL import Image

A = pathlib.Path(__file__).resolve().parents[2] / 'assets'
src = Image.open(A / 'hero-home.webp').convert('RGB')
for w in (960, 1440, 2880):
    im = src if w == src.width else src.resize((w, round(src.height * w / src.width)), Image.LANCZOS)
    if w != src.width:
        im.save(A / f'hero-home-{w}.webp', 'WEBP', quality=82, method=6)
    im.save(A / f'hero-home-{w}.avif', 'AVIF', quality=62, speed=2)
    print(w, im.size)
