"""Проверка собранного сайта без внешних зависимостей (только Python 3 из коробки).

  python3 tools/check_site.py            проверяет папку site/
  python3 tools/check_site.py путь/к/site

Что проверяется:
  • все 7 страниц на месте;
  • каждая внутренняя ссылка (href/src/srcset и url() в fonts.css) ведёт на существующий файл,
    а ссылка с #якорем — на существующий id в целевой странице;
  • нет повторяющихся id на странице, у каждой страницы ровно один <h1>;
  • ни одна страница не загружает внешние ресурсы (скрипты, стили, картинки, шрифты с http/https);
  • состояние публикации: robots, плашка черновика, canonical, sitemap.xml, robots.txt.
Внешние ссылки (<a href="https://…">) только перечисляются; их доступность не проверяется.
Код выхода 1 — если найдены ошибки.
"""
import pathlib, re, sys
from html.parser import HTMLParser

SITE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent / 'site').resolve()
PAGES = ['index.html', 'biography.html', 'usa.html', 'schools.html', 'moscow.html', 'leningrad.html', 'concertos.html', 'about.html', 'en/index.html']
errors, external = [], set()

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.refs = []; self.ids = []; self.h1 = 0; self.res = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if 'id' in d: self.ids.append(d['id'])
        if tag == 'h1': self.h1 += 1
        for k in ('href', 'src'):
            if k in d and d[k]:
                self.refs.append((tag, k, d[k], d.get('rel')))
        if 'srcset' in d:
            for part in d['srcset'].split(','):
                self.refs.append((tag, 'srcset', part.strip().split(' ')[0], None))

parsed = {}
for pg in PAGES:
    f = SITE / pg
    if not f.exists():
        errors.append(f'нет страницы {pg}'); continue
    p = P(); p.feed(f.read_text(encoding='utf-8')); parsed[pg] = p
    dup = {i for i in p.ids if p.ids.count(i) > 1}
    if dup: errors.append(f'{pg}: повторяющиеся id {sorted(dup)}')
    if p.h1 != 1: errors.append(f'{pg}: <h1> встречается {p.h1} раз')

def ids_of(path):
    rel = path.relative_to(SITE).as_posix()
    if rel not in parsed:
        q = P(); q.feed(path.read_text(encoding='utf-8')); parsed[rel] = q
    return set(parsed[rel].ids)

checked = 0
for pg, p in list(parsed.items()):
    if pg not in PAGES: continue
    base = (SITE / pg).parent
    for tag, attr, url, rel in p.refs:
        if url.startswith(('http://', 'https://')):
            if tag == 'a': external.add(re.sub(r'^https?://([^/]+).*', r'\1', url))
            elif not (tag == 'link' and rel in ('canonical', 'alternate')) and not (tag == 'meta'):
                errors.append(f'{pg}: внешний ресурс <{tag} {attr}> {url}')
            continue
        if url.startswith(('data:', 'mailto:', 'tel:')): continue
        path, _, frag = url.partition('#')
        target = (base / path).resolve() if path else (SITE / pg)
        checked += 1
        if path.endswith('/'): target = target / 'index.html'
        if not target.exists():
            errors.append(f'{pg}: битая ссылка {url}'); continue
        if frag and target.suffix == '.html' and frag not in ids_of(target):
            errors.append(f'{pg}: нет якоря #{frag} в {target.relative_to(SITE)}')

css = SITE / 'assets' / 'fonts.css'
if css.exists():
    for u in re.findall(r'url\(([^)]+)\)', css.read_text()):
        checked += 1
        if not (css.parent / u.strip('\'"')).exists(): errors.append(f'fonts.css: нет файла {u}')
else:
    errors.append('нет assets/fonts.css')

idx = (SITE / 'index.html').read_text(encoding='utf-8') if (SITE / 'index.html').exists() else ''
robots = re.search(r'<meta name="robots" content="([^"]+)"', idx)
canon = re.search(r'<link rel="canonical" href="([^"]+)"', idx)
print(f'Папка: {SITE}')
print(f'Страниц: {sum(1 for p in PAGES if (SITE / p).exists())} из {len(PAGES)}; проверено локальных ссылок и путей: {checked}')
print('Режим:', 'ПУБЛИЧНЫЙ' if robots and robots.group(1).startswith('index') else 'ЧЕРНОВИК (noindex)',
      '| плашка черновика:', 'есть' if 'class="draft"' in idx else 'нет',
      '| canonical:', canon.group(1) if canon else 'нет',
      '| sitemap.xml:', 'есть' if (SITE / 'sitemap.xml').exists() else 'нет',
      '| robots.txt:', 'есть' if (SITE / 'robots.txt').exists() else 'нет')
print('Внешние сайты в ссылках (не проверялись на доступность):', ', '.join(sorted(external)))
if errors:
    print('\nОШИБКИ:'); [print(' -', e) for e in errors]; sys.exit(1)
print('Ошибок не найдено.')
