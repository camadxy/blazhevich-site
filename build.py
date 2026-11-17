"""Сборка сайта Blazhevich.

  python3 build.py                                   черновик: noindex, плашка «не опубликовано»
  python3 build.py --release --domain https://site   публичная версия: индексация, canonical,
                                                     Open Graph с полными адресами, sitemap.xml, robots.txt

Результат в папке site/: index.html — весь сайт одной страницей (первый экран и все разделы подряд,
боковое меню), досье moscow.html и leningrad.html, en/index.html — английская версия одной страницей,
assets/. Старые адреса разделов (scores.html, en/scores.html, …) остаются короткими страницами-переадресациями. Эту папку целиком загружают на хостинг.
Для зеркал (РФ и США) собирайте обе копии с одним --domain — адресом основного сайта.
С флагом --single-page дополнительно собирается artifact.html — вся русская версия одной
страницей (нужна только для предпросмотра в Claude, на сервер не загружается; шрифты берёт с Google Fonts).
"""
import argparse, datetime, hashlib, json, pathlib, re, shutil, time

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
# Стили живут отдельным файлом с хэшем содержимого в имени: страницы не таскают стили при каждом
# переходе, а .deploy/htaccess кэширует такой файл навсегда (immutable). Инлайн остаётся только
# в artifact.html — он собирается одним файлом для предпросмотра вне сайта.
CSS_FILE = 'main.' + hashlib.sha256(CSS.encode('utf-8')).hexdigest()[:10] + '.css'

FONTS_GOOGLE = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Onest:wght@400;600&display=swap">')
FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23e8dbbf'/%3E%3Ctext x='32' y='46' text-anchor='middle' font-family='Georgia,serif' font-weight='600' font-size='40' fill='%232a2118'%3EB%3C/text%3E%3C/svg%3E\">")

def sec(name, lang='ru'):
    return (SRC / lang / f'{name}.html').read_text()

# ---------------- Русские страницы ----------------
PAGES = {  # файл: (секции, заголовок, описание)
    'index.html': (['hero', 'scores', 'listen', 'biography', 'usa', 'schools', 'concertos', 'about'],
                   'Blazhevich — Владислав Блажевич: тромбон, ноты, история',
                   'Владислав Блажевич (1881–1942): ноты, записи, биография, 13 концертов для тромбона, школы тромбона и признание в США.'),
    'moscow.html': (['moscow'], 'Московская тромбоновая школа — Blazhevich',
                    'Московская школа тромбона: Витнебен, Борк, Блажевич, Щербинин и его ученики, гнесинская ветвь, ноты и записи.'),
    'leningrad.html': (['leningrad'], 'Ленинградская тромбоновая школа — Blazhevich',
                       'Петербургско-ленинградская школа тромбона: Тюрнер, Волков, Козлов, Венгловский, Квартет тромбонов филармонии, дискография.'),
    'us-schools.html': (['us-schools'], 'Американские школы тромбона — Blazhevich',
                        'Истмен и Ремингтон, Чикаго и Джейкобс, Curtis и Алесси, Northwestern: как устроены американские тромбоновые школы и чем они похожи на московскую и ленинградскую.'),
}
NAV_RU = [('scores', 'Ноты'), ('listen', 'Слушать'), ('biography', 'Биография'), ('usa', 'В США'),
          ('us-schools', 'Школы США'), ('schools', 'Школы'), ('concertos', 'Концерты'), ('about', 'О проекте')]
# досье-подстраницы: крошка ведёт на родительский раздел, в меню подсвечен он же
PARENT_RU = {'moscow.html': ('schools', 'Школы'), 'leningrad.html': ('schools', 'Школы')}
# английские досье: src/en/<имя>.html → en/<имя>.html (заголовок, описание)
EN_DOSSIERS = {
    'moscow.html': ('The Moscow trombone school — Blazhevich',
                    'The Moscow trombone school: Wittneben, Bork, Blazhevich, Shcherbinin and his pupils, the Gnesin branch, scores and recordings.'),
    'leningrad.html': ('The Leningrad trombone school — Blazhevich',
                       'The St. Petersburg–Leningrad trombone school: Türner, Volkov, Kozlov, Venglovsky, the Philharmonic Trombone Quartet, discography.'),
}
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
        if i == tgt[1] and tgt[0] != 'index.html':   # главная секция страницы → просто страница
            return f'href="{tgt[0]}"'
        return f'href="{tgt[0]}#{i}"'
    return re.sub(r'href="#([\w-]+)"', fix, html)

DRAFT = '' if a.release else '<div class="draft">Предварительный просмотр · не опубликовано</div>\n'

def header(nav_html, lang_link, home):
    return (f'<a class="skip" href="#main">Перейти к содержимому</a>\n' + DRAFT
            + f'<header id="top-bar"><div class="wrap bar">\n  <a href="{home}" class="brand" aria-label="Blazhevich — на главную">Blazhevich</a>\n'
            f'  <nav aria-label="Основная навигация">{nav_html}{lang_link}</nav>\n</div></header>\n')

# архивная виньетка в шапке раздела: декоративная (alt=""), источники снимков — в «О проекте»
VIGNETTE = {'scores': 'v-conservatory-portico.webp', 'listen': 'v-bolshoi-colonnade.webp',
            'biography': 'conservatory-1940s.webp', 'concertos': 'bolshoi-1905.webp',
            'schools': 'conservatory-1940s.webp'}
# размеры файлов виньеток: с width/height браузер резервирует место до загрузки, вёрстка не прыгает
VIGNETTE_WH = {'v-conservatory-portico.webp': (420, 490), 'v-bolshoi-colonnade.webp': (470, 460),
               'conservatory-1940s.webp': (960, 600), 'bolshoi-1905.webp': (960, 600)}
def vignette(v, prefix=''):
    w, h = VIGNETTE_WH[v]
    return (f'<figure class="head-vignette" aria-hidden="true"><img src="{prefix}assets/{v}" alt="" '
            f'width="{w}" height="{h}" loading="lazy" decoding="async"></figure>')
# сцена во всю ширину с текстом поверх (assets/scene-*.webp делает tools/scenes/*.py)
SCENE = {'moscow', 'leningrad'}

def inner(h, crumb, href='index.html', prefix=''):
    """На внутренней странице заголовок секции становится h1 с «хлебной крошкой»."""
    sid = re.match(r'\s*<section id="([\w-]+)"', h)
    v = VIGNETTE.get(sid.group(1)) if sid else None
    fig = vignette(v, prefix) if v else ''
    cls = f' scene scene-{sid.group(1)}' if sid and sid.group(1) in SCENE else ''
    # url() во встроенном CSS считается от страницы: из папки en/ картинку сцены даём с префиксом
    sty = (f' style="--scene:url({prefix}assets/scene-{sid.group(1)}.webp);--scene-sm:url({prefix}assets/scene-{sid.group(1)}-960.webp)"'
           if cls and prefix else '')
    h = h.replace('<div class="section-head reveal">',
                  f'<div class="section-head{cls} reveal"{sty}><a class="crumb" href="{href}">← {crumb}</a>{fig}', 1)
    return re.sub(r'<h2>(.*?)</h2>', r'<h1 class="page-title">\1</h1>', h, count=1)

def deco(h, prefix='', n=0):
    """Раздел на общей странице: заголовок остаётся h2, справа — архивная виньетка, над заголовком — номер раздела."""
    if n:
        h = h.replace('<div class="section-head reveal">', f'<div class="section-head reveal" data-n="{n:02d}">', 1)
    sid = re.match(r'\s*<section id="([\w-]+)"', h)
    v = VIGNETTE.get(sid.group(1)) if sid else None
    if not v:
        return h
    fig = vignette(v, prefix)
    return re.sub(r'(<div class="section-head reveal"[^>]*>)', lambda m: m.group(1) + fig, h, count=1)

def rail(items, lang_link, label):
    """Боковое меню общей страницы (на узких экранах вместо него кнопка «Меню»)."""
    edge = 'Меню' if label == 'Разделы' else 'Menu'   # то же слово, что на кнопках первого экрана и телефона
    return (f'<div class="rail-edge" aria-hidden="true"><span>{edge}</span></div>\n'
            f'<nav class="rail" aria-label="{label}">' + ''.join(f'<a href="#{i}">{t}</a>' for i, t in items)
            + f'{lang_link}</nav>\n')

def stub(target, title, lang):
    """Старый адрес раздела → раздел общей страницы."""
    return ('<!doctype html>\n'
            f'<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n<meta name="robots" content="noindex,follow">\n'
            f'<meta http-equiv="refresh" content="0; url={target}">\n<title>{title}</title>\n</head>\n<body>\n'
            f'<p><a href="{target}">{title}</a></p>\n</body>\n</html>\n')

EN_WORDS = [('Перейти к содержимому', 'Skip to content'), ('Основная навигация', 'Main navigation'), ('на главную', 'home'),
            ('Предварительный просмотр · не опубликовано', 'Preview · not published')]
def en_words(html):
    for ru, en_ in EN_WORDS:
        html = html.replace(ru, en_)
    return html

def site_footer(lang):
    """Подвал: имя и годы, разделы, досье школ, язык. Ссылки с адресом страницы — подвал общий для главной и досье."""
    ru = lang == 'ru'
    nav = NAV_RU if ru else [(k, v[0]) for k, v in EN_PAGES.items()]

    def nav_href(i):
        if f'{i}.html' in PAGES:                 # отдельная страница: из папки en/ путь на уровень выше
            return ('../' if not ru else '') + f'{i}.html'
        return f'index.html#{i}'

    secs = ''.join(f'<li><a href="{nav_href(i)}">{t}</a></li>' for i, t in nav)
    T = (dict(who='Владислав Блажевич', about='Тромбонист, педагог, композитор. Независимый проект о его жизни, нотах и школе.',
              s='Разделы', d='Школы тромбона', m='Московская тромбоновая школа', l='Ленинградская тромбоновая школа', u='Американские школы',
              o='Язык', other='<a href="en/index.html" hreflang="en" lang="en">English version</a>',
              fine='Источники и права на изображения указаны в разделе <a href="index.html#about">«О проекте»</a>.', top='Наверх', nav='Подвал')
         if ru else
         dict(who='Vladislav Blazhevich', about='Trombonist, teacher, composer. An independent project about his life, scores and school.',
              s='Sections', d='Trombone schools', m='The Moscow trombone school', l='The Leningrad trombone school', u='American schools',
              o='Language', other='<a href="../index.html" hreflang="ru" lang="ru">Русская версия</a>',
              fine='Sources and image credits are listed under <a href="index.html#about">About</a>.', top='Back to top', nav='Footer'))
    return ('<footer><div class="wrap foot">\n'
            f'  <div class="foot-id"><a href="index.html" class="brand">Blazhevich</a><p class="foot-name">{T["who"]} <span>1881–1942</span></p><p>{T["about"]}</p></div>\n'
            f'  <div class="foot-col" role="navigation" aria-label="{T["nav"]}"><h2>{T["s"]}</h2><ul class="foot-secs">{secs}</ul></div>\n'
            f'  <div class="foot-col"><h2>{T["d"]}</h2><ul><li><a href="moscow.html">{T["m"]}</a></li><li><a href="leningrad.html">{T["l"]}</a></li><li><a href="{(T["u"] == "American schools" and "../" or "")}us-schools.html">{T["u"]}</a></li></ul>'
            f'<h2>{T["o"]}</h2><ul><li>{T["other"]}</li></ul></div>\n'
            f'  <p class="foot-fine">{T["fine"]}</p>\n'
            '</div></footer>\n'
            f'<button class="totop" id="totop" type="button" aria-label="{T["top"]}">↑</button>\n')

# ---- типографика русских страниц ----
_NB = ' '
_SHORT = re.compile(r'(?<![\w-])(в|во|к|ко|с|со|о|об|у|и|а|на|по|из|за|от|до|не|ни|но) (?=\S)', re.I)
def typo(html):
    """Неразрывные пробелы в русском тексте: после коротких предлогов и союзов, после №, между инициалами,
    перед тире и между числом и словом «год/лет» — чтобы строка не кончалась на «в», «и», «№» или «1905». Теги не трогаются."""
    def fix(t):
        t = t.replace('№ ', '№' + _NB)
        t = re.sub(r'(?<![А-Яа-яЁё])([А-ЯЁ]\.) (?=[А-ЯЁ])', r'\1' + _NB, t)
        t = re.sub(r'(\d) (год[а-я]{0,2}|лет|г\.|гг\.)(?![а-яё])', r'\1' + _NB + r'\2', t)
        t = _SHORT.sub(lambda m: m.group(1) + _NB, t)
        return t.replace(' —', _NB + '—')
    return ''.join(x if x.startswith('<') else fix(x) for x in re.split(r'(<[^>]+>)', html))

FOOTER_RU = lambda: site_footer('ru')
FOOTER_EN = lambda: site_footer('en')

# ---------------- JSON-LD: разметка для поисковиков (только в публичной сборке, адреса абсолютные) ----------------
PERSON_SAME_AS = ['https://ru.wikipedia.org/wiki/Блажевич,_Владислав_Михайлович',
                  'https://en.wikipedia.org/wiki/Vladislav_Blazhevich',
                  'https://imslp.org/wiki/Category:Blazhevich,_Vladislav']
CRUMBS = {  # страница: цепочка «хлебных крошек» (подпись, адрес от корня сайта)
    'moscow.html': [('Главная', ''), ('Школы', '#schools'), ('Московская тромбоновая школа', 'moscow.html')],
    'leningrad.html': [('Главная', ''), ('Школы', '#schools'), ('Ленинградская тромбоновая школа', 'leningrad.html')],
    'us-schools.html': [('Главная', ''), ('Американские школы тромбона', 'us-schools.html')],
    'en/moscow.html': [('Home', 'en/'), ('Schools', 'en/#schools'), ('The Moscow trombone school', 'en/moscow.html')],
    'en/leningrad.html': [('Home', 'en/'), ('Schools', 'en/#schools'), ('The Leningrad trombone school', 'en/leningrad.html')],
}
_plain = lambda t: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()

def concerto_rows(lang):
    """Номер, тональность и дата каждого концерта — из таблицы раздела «Концерты», чтобы разметка не расходилась с текстом."""
    src = sec('concertos') if lang == 'ru' else sec('page', 'en')
    body = re.search(r'<table class="conc">.*?<tbody>(.*?)</tbody>', src, re.S).group(1)
    return [tuple(_plain(c) for c in re.findall(r'<td>(.*?)</td>', r, re.S)[:3]) for r in re.findall(r'<tr>(.*?)</tr>', body, re.S)]

def jsonld(path, lang, url, title, desc):
    ru = lang == 'ru'
    person = {'@type': 'Person', '@id': f'{DOM}/#blazhevich',
              'name': 'Владислав Блажевич' if ru else 'Vladislav Blazhevich',
              'alternateName': ['Vladislav Blazhevich', 'Владислав Михайлович Блажевич'] if ru
                               else ['Владислав Блажевич', 'Владислав Михайлович Блажевич'],
              'birthDate': '1881-08-15', 'deathDate': '1942-04-10',
              'jobTitle': 'Тромбонист, педагог, композитор' if ru else 'Trombonist, teacher, composer',
              'sameAs': PERSON_SAME_AS}
    g = []
    if path in ('index.html', 'en/index.html'):
        g.append({'@type': 'WebSite', '@id': f'{DOM}/#website', 'url': f'{DOM}/', 'name': 'Blazhevich',
                  'inLanguage': ['ru', 'en'], 'about': {'@id': person['@id']}})
        g.append(person)
        items = []
        for n, key, date in concerto_rows(lang):
            c = {'@type': 'MusicComposition', '@id': f'{url}#concerto-{n}',
                 'name': f'Концерт № {n} для тромбона' if ru else f'Trombone Concerto No. {n}',
                 'composer': {'@id': person['@id']}, 'url': f'{url}#concertos'}
            if key != '—':
                c['musicalKey'] = key
            if re.fullmatch(r'\d{4}', date):   # спорные даты («1926 или 1930-е») в разметку не идут
                c['dateCreated'] = date
            items.append({'@type': 'ListItem', 'position': int(n), 'item': c})
        g.append({'@type': 'ItemList', '@id': f'{url}#concertos-list',
                  'name': '13 концертов для тромбона' if ru else 'The 13 trombone concertos',
                  'numberOfItems': len(items), 'itemListElement': items})
    else:
        g.append({'@type': 'WebPage', '@id': f'{url}#page', 'url': url, 'name': title, 'description': desc,
                  'inLanguage': lang, 'isPartOf': {'@id': f'{DOM}/#website'}, 'about': {'@id': person['@id']}})
        g.append(person)
    if path in CRUMBS:
        g.append({'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i, 'name': n_, 'item': f'{DOM}/{u}'} for i, (n_, u) in enumerate(CRUMBS[path], 1)]})
    data = json.dumps({'@context': 'https://schema.org', '@graph': g}, ensure_ascii=False, separators=(',', ':'))
    return '<script type="application/ld+json">' + data.replace('</', '<\\/') + '</script>'

def head(title, desc, path, lang, prefix, fonts):
    url = f'{DOM}/{path}'.replace('/index.html', '/') if DOM else ''
    img = f'{DOM}/assets/og-image.jpg' if DOM else f'{prefix}assets/og-image.jpg'
    m = [f'<title>{title}</title>',
         f'<meta name="description" content="{desc}">',
         f'<meta name="robots" content="{"index,follow" if a.release else "noindex,nofollow"}">',
         '<meta name="theme-color" content="#e8dbbf">', FAVICON,
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
        if path in ('index.html', 'en/index.html'):   # языковые пары: общая страница и два досье
            m += [f'<link rel="alternate" hreflang="ru" href="{DOM}/">',
                  f'<link rel="alternate" hreflang="en" href="{DOM}/en/">',
                  f'<link rel="alternate" hreflang="x-default" href="{DOM}/">']
        elif path.removeprefix('en/') in EN_DOSSIERS:
            f_ = path.removeprefix('en/')
            m += [f'<link rel="alternate" hreflang="ru" href="{DOM}/{f_}">',
                  f'<link rel="alternate" hreflang="en" href="{DOM}/en/{f_}">',
                  f'<link rel="alternate" hreflang="x-default" href="{DOM}/{f_}">']
        elif lang == 'ru':   # страница только по-русски (например, «Школы США»): ссылка на себя
            m += [f'<link rel="alternate" hreflang="ru" href="{url}">',
                  f'<link rel="alternate" hreflang="x-default" href="{url}">']
        m.append(jsonld(path, lang, url, title, desc))
    if path in ('index.html', 'en/index.html'):   # снимок первого экрана браузер начинает качать сразу, не дожидаясь разбора встроенных стилей
        hs = ', '.join(f'{prefix}assets/hero-home-{w}.avif {w}w' for w in (960, 1440, 2880))   # те же srcset и sizes, что у <source> в hero
        m.append(f'<link rel="preload" as="image" type="image/avif" imagesrcset="{hs}" '
                 'imagesizes="(max-aspect-ratio: 2880/1568) 184vh, 100vw" fetchpriority="high">')
        # шрифт надписи BLAZHEVICH на первом экране: без preload браузер узнаёт о нём только после разбора fonts.css
        m.append(f'<link rel="preload" as="font" type="font/woff2" href="{prefix}assets/fonts/cormorant-garamond-normal-latin.woff2" crossorigin>')
    m.append(fonts)
    return '\n'.join(m)

def page(lang, title, desc, path, prefix, body, fonts, footer):
    if lang == 'ru':
        body, footer = typo(body), typo(footer)
    return ('<!doctype html>\n'
            f'<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            + head(title, desc, path, lang, prefix, fonts)
            + f'\n<link rel="stylesheet" href="{prefix}assets/{CSS_FILE}">\n</head>\n<body>\n{body}{footer}<script>\n{JS}</script>\n</body>\n</html>\n')

def clean_out(path, tries=5):
    """Очистка site/. На Windows свежие файлы иногда заняты антивирусом или индексатором — повторяем."""
    for i in range(tries):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.3 * (i + 1))
    raise SystemExit(f'Не удалось очистить {path}: файлы заняты другим процессом, закройте просмотр и повторите')


OUT = ROOT / 'site'
clean_out(OUT)
(OUT / 'en').mkdir(parents=True)
shutil.copytree(ROOT / 'assets', OUT / 'assets')
(OUT / 'assets' / CSS_FILE).write_text(CSS)

# карта «id → (страница, главная секция страницы)»
id_page = {}
for f, (ss, _, _) in PAGES.items():
    for s_ in ss:
        for i in ids_in(sec(s_)):
            id_page[i] = (f, s_)

nav = ''.join(f'<a href="#{i}">{t}</a>' for i, t in NAV_RU)
for f, (ss, title, desc) in PAGES.items():
    par = PARENT_RU.get(f)
    if f == 'index.html':   # весь сайт одной страницей: первый экран, разделы подряд, боковое меню
        body = (f'<a class="skip" href="#main">Перейти к содержимому</a>\n' + DRAFT
                + rail(NAV_RU, '<a class="lang" href="en/index.html" hreflang="en" lang="en">EN</a>', 'Разделы')
                + '<div class="progress" aria-hidden="true"></div>\n<button class="fab" type="button" popovertarget="menu">Меню</button>\n'
                + '<main id="main">\n' + ''.join(deco(sec(s_), n=i) for i, s_ in enumerate(ss)) + '</main>\n')
        footer = FOOTER_RU()
    else:
        crumb = (par[1], f'index.html#{par[0]}') if par else ('Главная', 'index.html')
        en_href = f'en/{f}' if f in EN_DOSSIERS else 'en/index.html'
        body = header(nav, f'<a class="lang" href="{en_href}" hreflang="en" lang="en">EN</a>', 'index.html') \
            + '<main id="main">\n' + ''.join(inner(sec(s_), *crumb) for s_ in ss) + '</main>\n'
        footer = FOOTER_RU()
    body = relink(body, f, id_page)
    if f != 'index.html':
        body = body.replace(f'<a href="#{ss[0]}">', f'<a href="{f}">', 1)
    if par:
        body = body.replace(f'<a href="index.html#{par[0]}">', f'<a href="index.html#{par[0]}" class="active">', 1)
    (OUT / f).write_text(page('ru', title, desc, f, '', body,
                              '<link rel="stylesheet" href="assets/fonts-v2.css">', footer))
for i, t in NAV_RU:   # старые адреса разделов
    if f'{i}.html' in PAGES:   # отдельная страница уже собрана — стаб не нужен
        continue
    (OUT / f'{i}.html').write_text(stub(f'index.html#{i}', f'{t} — Blazhevich', 'ru'))

# ---------------- Английские страницы: один исходник, по странице на секцию ----------------
en = re.sub(r'(src="|srcset="|, )assets/', r'\1../assets/', sec('page', 'en'))  # пути к картинкам из папки en/
EN_PAGES = {  # id секции: (подпись в меню, заголовок, описание)
    'scores': ('Scores', 'Scores by Vladislav Blazhevich — Blazhevich', 'Method books, studies, duets and concertos by Vladislav Blazhevich for trombone and tuba, with links to libraries.'),
    'listen': ('Listen', 'Listen to Blazhevich — Blazhevich', 'Recordings of music by Vladislav Blazhevich and where to hear them.'),
    'biography': ('Biography', 'Vladislav Blazhevich: biography — Blazhevich', 'The life of Vladislav Blazhevich (1881–1942): military bands, the Moscow Conservatory, the Bolshoi Theatre, his professorship.'),
    'usa': ('In America', 'Blazhevich in America — Blazhevich', 'How the music of Blazhevich reached the United States: Jacob Raichman, the Clef Studies and the American editions.'),
    'schools': ('Schools', 'The Moscow and St Petersburg trombone schools — Blazhevich', 'Who studied with whom: the Moscow and St Petersburg lines of Russian trombone teaching.'),
    'concertos': ('Concertos', 'The 13 trombone concertos of Blazhevich — Blazhevich', 'All 13 trombone concertos by Vladislav Blazhevich: keys, dates, first editions and recordings.'),
    'about': ('About', 'About the project and sources — Blazhevich', 'An independent project about Vladislav Blazhevich: principles, sources and image credits.'),
}
en_secs = {re.match(r'<section id="([\w-]+)"', p).group(1): p for p in re.split(r'(?=<section id=")', en) if p.strip()}
assert set(en_secs) == {'hero', *EN_PAGES}, sorted(en_secs)
id_page_en = {i: ('index.html', k) for k in EN_PAGES for i in ids_in(en_secs[k])}
nav_en = ''.join(f'<a href="#{k}">{v[0]}</a>' for k, v in EN_PAGES.items())
FONTS_EN = '<link rel="stylesheet" href="../assets/fonts-v2.css">'
body = ('<a class="skip" href="#main">Skip to content</a>\n' + DRAFT
        + rail([(k, v[0]) for k, v in EN_PAGES.items()], '<a class="lang" href="../index.html" hreflang="ru" lang="ru">RU</a>', 'Sections')
        + '<div class="progress" aria-hidden="true"></div>\n<button class="fab" type="button" popovertarget="menu">Menu</button>\n'
        + '<main id="main">\n' + en_secs['hero'] + ''.join(deco(en_secs[k], '../', i) for i, k in enumerate(EN_PAGES, 1)) + '</main>\n')
(OUT / 'en' / 'index.html').write_text(page(
    'en', 'Vladislav Blazhevich — trombone: life, concertos, Clef Studies',
    'Vladislav Blazhevich (1881–1942): biography, the 13 trombone concertos, Clef Studies and other method books, how his music reached America.',
    'en/index.html', '../', en_words(relink(body, 'index.html', id_page_en)), FONTS_EN, FOOTER_EN()))
for k, (label, title, _) in EN_PAGES.items():   # старые адреса английских разделов
    (OUT / 'en' / f'{k}.html').write_text(stub(f'index.html#{k}', title, 'en'))
act = ' class="active"'  # вне f-string-выражения: бэкслеш внутри выражения валиден только с Python 3.12
nav_en_idx = ''.join(f'<a href="index.html#{k}"{act if k == "schools" else ""}>{v[0]}</a>' for k, v in EN_PAGES.items())
for f, (title, desc) in EN_DOSSIERS.items():
    src = re.sub(r'(src="|srcset="|, )assets/', r'\1../assets/', sec(f[:-5], 'en'))
    body = (header(nav_en_idx, f'<a class="lang" href="../{f}" hreflang="ru" lang="ru">RU</a>', 'index.html')
            + '<main id="main">\n' + inner(src, 'Schools', 'index.html#schools', '../') + '</main>\n')
    (OUT / 'en' / f).write_text(page('en', title, desc, f'en/{f}', '../', en_words(body), FONTS_EN, FOOTER_EN()))

if a.release:
    today = datetime.date.fromisoformat(a.lastmod).isoformat() if a.lastmod else datetime.date.today().isoformat()
    urls = [''] + [f for f in PAGES if f != 'index.html'] + ['en/'] + [f'en/{f}' for f in EN_DOSSIERS]
    (OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + ''.join(f'  <url><loc>{DOM}/{u}</loc><lastmod>{today}</lastmod></url>\n' for u in urls) + '</urlset>\n')
    (OUT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {DOM}/sitemap.xml\n')

# ---------------- Одностраничная версия для предпросмотра на claude.ai ----------------
one = ''.join(sec(s_) for s_ in ['scores', 'listen', 'biography', 'usa', 'schools', 'concertos', 'about'])
nav = ''.join(f'<a href="#{i}">{t}</a>' for i, t in NAV_RU)
art = ('<title>Blazhevich</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
       '<meta name="robots" content="noindex,nofollow">\n<meta name="theme-color" content="#e8dbbf">\n' + FAVICON + '\n' + FONTS_GOOGLE
       + f'\n<style>\n{CSS}</style>\n\n'
       + header(nav, '', '#scores')
       + f'<main id="main">\n{one}</main>\n'
       + '<footer><div class="wrap foot"><a href="#scores" class="brand">Blazhevich</a><span>Владислав Блажевич · Vladislav Blazhevich</span></div></footer>\n'
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
