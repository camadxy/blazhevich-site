"""Сборка сайта Blazhevich.

  python3 build.py                                   черновик: noindex, плашка «не опубликовано»
  python3 build.py --release --domain https://site   публичная версия: индексация, canonical,
                                                     Open Graph с полными адресами, sitemap.xml, robots.txt

Результат в папке site/: index.html, biography.html, usa.html, schools.html,
concertos.html, about.html, en/index.html и assets/. Эту папку целиком загружают на хостинг.
Для зеркал (РФ и США) собирайте обе копии с одним --domain — адресом основного сайта.
С флагом --single-page дополнительно собирается artifact.html — вся русская версия одной
страницей (нужна только для предпросмотра в Claude, на сервер не загружается; шрифты берёт с Google Fonts).
"""
import argparse, datetime, pathlib, re, shutil

ROOT = pathlib.Path(__file__).parent

# Кросс-платформенная детерминированность сборки: текстовые файлы всегда пишутся с LF,
# чтобы сборка на Windows была байт-в-байт равна сборке на Linux — это нужно для сверки
# с опубликованной версией и повторяемости проверок. По умолчанию write_text на Windows
# переводит \n в CRLF, из-за чего собранные файлы отличались от живого сайта.
import sys as _sys
if _sys.version_info >= (3, 10):
    _write_text_orig = pathlib.Path.write_text
    def _write_text_lf(self, data, *args, **kwargs):
        kwargs.setdefault('newline', '\n')
        return _write_text_orig(self, data, *args, **kwargs)
    pathlib.Path.write_text = _write_text_lf

SRC = ROOT / 'src'
ap = argparse.ArgumentParser()
ap.add_argument('--release', action='store_true')
ap.add_argument('--domain', default='')
ap.add_argument('--lastmod', default='', help='optional YYYY-MM-DD content revision date')
ap.add_argument('--single-page', action='store_true', help='дополнительно собрать artifact.html (предпросмотр)')
a = ap.parse_args()
DOM = a.domain.rstrip('/')
if a.release and not DOM:
    raise SystemExit('Для --release нужен --domain, например --domain https://blazhevich.ru')

CSS = (SRC / 'style.css').read_text()
JS = (SRC / 'script.js').read_text()
EXTRA_CSS = ""  # всё оформление в src/style.css
CSS = CSS + EXTRA_CSS

FONTS_GOOGLE = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Onest:wght@400;600&display=swap">')
FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23f4eee1'/%3E%3Ctext x='32' y='46' text-anchor='middle' font-family='Georgia,serif' font-weight='600' font-size='40' fill='%232a2118'%3EB%3C/text%3E%3C/svg%3E\">")

def sec(name, lang='ru'):
    return (SRC / lang / f'{name}.html').read_text()

# ---------------- Русские страницы ----------------
PAGES = {  # файл: (секции, заголовок, описание)
    'index.html': (['hero', 'scores', 'listen', 'explore'],
                   'Blazhevich — Владислав Блажевич: тромбон, ноты, история',
                   'Владислав Блажевич (1881–1942): ноты, записи, биография, 13 концертов для тромбона, школы тромбона и признание в США.'),
    'biography.html': (['biography'], 'Биография Владислава Блажевича — Blazhevich',
                       'Жизнь Владислава Блажевича: детство на Смоленщине, военные оркестры, Московская консерватория, Большой театр, Персимфанс, профессура.'),
    'usa.html': (['usa'], 'Блажевич в Америке — Blazhevich',
                 'Как ноты Блажевича попали в США: Яков Райхман, Clef Studies, американские издания и права наследников.'),
    'schools.html': (['schools'], 'Московская и петербургская школы тромбона — Blazhevich',
                     'Кто у кого учился: Борк, Блажевич, Щербинин, Григорьев; Волков, Рейхе, Козлов, Коршунов, Венгловский. Биография Якова Райхмана.'),
    'concertos.html': (['concertos'], '13 концертов для тромбона Блажевича — Blazhevich',
                       'Все 13 концертов Владислава Блажевича: тональности, даты, первые издания, записи и устройство формы.'),
    'moscow.html': (['moscow'], 'Московская тромбонная школа — Blazhevich',
                    'Досье о московской школе тромбона: Витнебен, Борк, Блажевич, Щербинин и его ученики, гнесинская ветвь, ноты и записи.'),
    'leningrad.html': (['leningrad'], 'Ленинградская тромбонная школа — Blazhevich',
                       'Петербургско-ленинградская школа тромбона: Тюрнер, Волков, Козлов, Венгловский, Квартет тромбонов филармонии, дискография.'),
    'about.html': (['about'], 'О проекте и источники — Blazhevich',
                   'Независимый проект о Владиславе Блажевиче: принципы, источники и иллюстрации.'),
}
NAV_RU = [('scores', 'Ноты'), ('listen', 'Слушать'), ('biography', 'Биография'), ('usa', 'В США'),
          ('schools', 'Школы'), ('concertos', 'Концерты'), ('about', 'О проекте')]
PAGE_OF_SECTION = {s: f for f, (ss, _, _) in PAGES.items() for s in ss}

def ids_in(html):
    return set(re.findall(r'\bid="([\w-]+)"', html))

def relink(html, page, id_page):
    """#id → нужная страница: якорь своей страницы остаётся, чужой становится page.html#id."""
    here = ids_in(html)
    def fix(m):
        i = m.group(1)
        if i in here:
            return m.group(0)
        tgt = id_page.get(i)
        if not tgt:
            return m.group(0)
        if i == tgt[1]:          # главная секция страницы → просто страница
            return f'href="{tgt[0]}"'
        return f'href="{tgt[0]}#{i}"'
    return re.sub(r'href="#([\w-]+)"', fix, html)

def header(nav_html, lang_link, home, cls=''):
    return (f'<a class="skip" href="#main">{"Перейти к содержимому" if home=="index.html" else "Skip to content"}</a>\n'
            + ('<div class="draft">Предварительный просмотр · не опубликовано</div>\n' if not a.release else '')
            + f'<header id="top-bar"{cls}><div class="wrap bar">\n  <a href="{home}" class="brand" aria-label="Blazhevich — на главную">Blazhevich</a>\n'
            f'  <nav aria-label="Основная навигация">{nav_html}{lang_link}</nav>\n</div></header>\n')

FOOTER_RU = ('<footer><div class="wrap foot"><a href="index.html" class="brand">Blazhevich</a>'
             '<span>Владислав Блажевич, Vladislav Blazhevich</span><a href="en/index.html" hreflang="en" lang="en">English</a></div></footer>\n'
             '<button class="totop" id="totop" type="button" aria-label="Наверх">↑</button>\n')
FOOTER_EN = ('<footer><div class="wrap foot"><a href="index.html" class="brand">Blazhevich</a>'
             '<span>Vladislav Blazhevich, Владислав Блажевич</span><a href="../index.html" hreflang="ru" lang="ru">Русский</a></div></footer>\n'
             '<button class="totop" id="totop" type="button" aria-label="Back to top">↑</button>\n')

def head(title, desc, path, lang, prefix, fonts):
    url = f'{DOM}/{path}'.replace('/index.html', '/') if DOM else ''
    img = f'{DOM}/assets/og-image.jpg' if DOM else f'{prefix}assets/og-image.jpg'
    m = [f'<title>{title}</title>',
         f'<meta name="description" content="{desc}">',
         f'<meta name="robots" content="{"index,follow" if a.release else "noindex,nofollow"}">',
         '<meta name="theme-color" content="#f4eee1">', FAVICON,
         '<meta property="og:type" content="website">',
         f'<meta property="og:locale" content="{"ru_RU" if lang == "ru" else "en_US"}">',
         '<meta property="og:site_name" content="Blazhevich">',
         f'<meta property="og:title" content="{title}">',
         f'<meta property="og:description" content="{desc}">',
         f'<meta property="og:image" content="{img}">',
         '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
         '<meta name="twitter:card" content="summary_large_image">']
    if DOM:
        m += [f'<link rel="canonical" href="{url}">', f'<meta property="og:url" content="{url}">']
        if path in ('index.html', 'en/index.html'):   # языковые пары есть только у главных страниц
            m += [f'<link rel="alternate" hreflang="ru" href="{DOM}/">',
                  f'<link rel="alternate" hreflang="en" href="{DOM}/en/">']
    m.append(fonts)
    return '\n'.join(m)

def page(lang, title, desc, path, prefix, body, fonts, footer):
    return ('<!doctype html>\n'
            f'<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            + head(title, desc, path, lang, prefix, fonts)
            + f'\n<style>\n{CSS}</style>\n</head>\n<body>\n{body}{footer}<script>\n{JS}</script>\n</body>\n</html>\n')

OUT = ROOT / 'site'
shutil.rmtree(OUT, ignore_errors=True)
(OUT / 'en').mkdir(parents=True)
shutil.copytree(ROOT / 'assets', OUT / 'assets')

# карта «id → (страница, главная секция страницы)»
id_page = {}
for f, (ss, _, _) in PAGES.items():
    for s_ in ss:
        for i in ids_in(sec(s_)):
            id_page[i] = (f, s_)

for f, (ss, title, desc) in PAGES.items():
    main = ''
    for s_ in ss:
        h = sec(s_)
        if f != 'index.html':   # на внутренних страницах заголовок секции становится h1 с «хлебной крошкой»
            h = h.replace('<div class="section-head reveal">',
                          '<div class="section-head reveal"><a class="crumb" href="index.html">← Главная</a>', 1)
            h = re.sub(r'<h2>(.*?)</h2>', r'<h1 class="page-title">\1</h1>', h, count=1)
        main += h
    nav = ''.join(f'<a href="#{i}">{t}</a>' for i, t in NAV_RU)
    body = header(nav, '<a class="lang" href="en/index.html" hreflang="en" lang="en">EN</a>', 'index.html', ' class="home"' if f == 'index.html' else '') \
        + f'<main id="main">\n{main}</main>\n'
    body = relink(body, f, id_page)
    if f != 'index.html':
        body = body.replace(f'<a href="#{ss[0]}">', f'<a href="{f}">', 1)
    (OUT / f).write_text(page('ru', title, desc, f, '', body,
                              '<link rel="stylesheet" href="assets/fonts.css">', FOOTER_RU))

# ---------------- Английская страница ----------------
en = re.sub(r'(src="|srcset="|, )assets/', r'\1../assets/', sec('page', 'en'))  # пути к картинкам из папки en/
nav_en = ''.join(f'<a href="#{i}">{t}</a>' for i, t in
                 [('scores', 'Scores'), ('listen', 'Listen'), ('biography', 'Biography'), ('usa', 'In America'), ('schools', 'Schools'), ('concertos', 'Concertos'), ('about', 'About')])
body_en = header(nav_en, '<a class="lang" href="../index.html" hreflang="ru" lang="ru">RU</a>', 'index.html', ' class="home"') \
    .replace('Основная навигация', 'Main navigation').replace('на главную', 'home').replace('Предварительный просмотр · не опубликовано', 'Preview · not published') \
    + f'<main id="main">\n{en}</main>\n'
(OUT / 'en' / 'index.html').write_text(page(
    'en', 'Blazhevich — Vladislav Blazhevich, trombone: life, concertos, Clef Studies',
    'Vladislav Blazhevich (1881–1942): biography, the 13 trombone concertos, Clef Studies and other method books, how his music reached America.',
    'en/index.html', '../', body_en, '<link rel="stylesheet" href="../assets/fonts.css">', FOOTER_EN))

if a.release:
    today = datetime.date.fromisoformat(a.lastmod).isoformat() if a.lastmod else datetime.date.today().isoformat()
    urls = [''] + [f for f in PAGES if f != 'index.html'] + ['en/']
    (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + ''.join(f'  <url><loc>{DOM}/{u}</loc><lastmod>{today}</lastmod></url>\n' for u in urls) + '</urlset>\n')
    (OUT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {DOM}/sitemap.xml\n')

# ---------------- Одностраничная версия для предпросмотра на claude.ai ----------------
one = ''.join(sec(s_) for s_ in ['hero', 'scores', 'listen', 'biography', 'usa', 'schools', 'concertos', 'about'])
nav = ''.join(f'<a href="#{i}">{t}</a>' for i, t in NAV_RU)
art = ('<title>Blazhevich</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
       '<meta name="robots" content="noindex,nofollow">\n<meta name="theme-color" content="#f4eee1">\n' + FAVICON + '\n' + FONTS_GOOGLE
       + f'\n<style>\n{CSS}</style>\n\n'
       + header(nav, '', '#hero').replace('href="#hero" class="brand"', 'href="#hero" class="brand"')
       + f'<main id="main">\n{one}</main>\n'
       + '<footer><div class="wrap foot"><a href="#hero" class="brand">Blazhevich</a><span>Владислав Блажевич · Vladislav Blazhevich</span></div></footer>\n'
       + '<button class="totop" id="totop" type="button" aria-label="Наверх">↑</button>\n'
       + f'<script>\n{JS}</script>\n')
if a.single_page:
    (ROOT / 'artifact.html').write_text(art)
try:
    from enhancements import apply
except ModuleNotFoundError:
    # Изолированные сборки Python (python313._pth, например встроенный Python в приложениях)
    # не добавляют папку скрипта в sys.path — добавляем её явно и повторяем импорт.
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from enhancements import apply
apply()
print('Собрано в', OUT, ':', 'ПУБЛИЧНАЯ версия для ' + DOM if a.release else 'черновик')
