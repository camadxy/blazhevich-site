#!/usr/bin/env python3
"""Сборщик выпуска «Ленты»: RSS -> отбор -> склейка дублей -> data/news/ГГГГ-ММ-ДД.json.

Только стандартная библиотека Python 3. Ключей и секретов не требует и не читает.
Запуск из корня репозитория (на сервере, по расписанию):

    python tools/news_agent.py                 # выпуск за сегодня (UTC)
    python tools/news_agent.py --date 2026-11-17
    python tools/news_agent.py --feeds-dir ПАПКА   # без сети: фиды из файлов <имя источника>.xml (для проверки)

Что делает (PLAN.md, этап «Лента», шаги fetch / dedupe / score / cluster / emit):
  1. читает источники из data/news/sources.json (только type=rss);
  2. отбрасывает уже виденное за 45 дней (data/news/seen.json) — по адресу и по заголовку;
  3. оценивает правилами, без языковой модели: инструмент x тип события x свежесть x вес источника;
  4. склеивает сообщения об одном событии в одну карточку (остальные ссылки — в cluster);
  5. пишет выпуск, index.json (последние 90 выпусков) и обновляет seen.json.

Чего не делает: не пересказывает (поле summary остаётся пустым — карточка показывает заголовок
и ссылку на первоисточник), не ходит на сайты без RSS, не коммитит. Повторный запуск за ту же дату
перезаписывает выпуск, а не дублирует его. Запись без даты публикации в выпуск не идёт.
"""
import argparse, datetime, hashlib, json, pathlib, re, sys, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = pathlib.Path(__file__).resolve().parents[1]
UA = 'Mozilla/5.0 (compatible; brass-news-digest/1.0)'

# Словари отбора. Основы слов, регистр не важен. «horn»/«труба» многозначны, поэтому для общих
# источников (require_match) одного такого слова мало — нужен ещё тип события или второй инструмент.
INSTR = {
    'trombone': r'trombon|тромбон', 'trumpet': r'trumpet|трубач|\bтруб[аыуе]\b|\bтрубой\b',
    'horn': r'french horn|\bhorn(?:ist|s)?\b|валторн', 'tuba': r'\btuba|тубист|\bтуб[аыуе]\b',
    'euphonium': r'euphonium|эуфониум', 'cornet': r'\bcornet|корнет', 'flugelhorn': r'flugelhorn|flügelhorn|флюгельгорн',
    'brass-band': r'brass band|brass quintet|\bbrass\b|брасс|духово[йг][о ]? ?оркестр|медны[ех] духов',
}
AMBIGUOUS = {'horn', 'trumpet', 'tuba'}
KINDS = {
    'competition': r'competition|contest|championship|prize|winner|конкурс|лауреат|победител|преми[яию]',
    'vacancy': r'audition|vacanc|job opening|position open|вакан|прослушиван',
    'premiere': r'premiere|première|world première|new concerto|премьер',
    'appointment': r'appoint|named principal|joins .* as|назначен|принят в оркестр',
    'obituary': r'obituar|dies|died|passes|passed away|in memoriam|tribute|ушёл из жизни|ушел из жизни|скончал|памяти',
    'festival': r'festival|symposium|workshop week|фестивал|симпозиум',
    'album': r'\balbum|new recording|new release|альбом|запис[ьи] вышл',
    'masterclass': r'master ?class|мастер-класс',
}
KIND_WEIGHT = {'competition': 1.5, 'vacancy': 1.5, 'appointment': 1.4, 'premiere': 1.4, 'obituary': 1.3,
               'festival': 1.1, 'album': 1.0, 'masterclass': 1.0}
THRESHOLD = 2.0      # порог отсечки; подбирается по первым выпускам
FRESH_DAYS = 7       # старше — в выпуск не идёт


def canon(url, moves):
    """Адрес без меток кампаний и якоря; перенесённые домены приводятся к новым."""
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix('www.')
    host = moves.get(host, host)
    q = urlencode([(k, v) for k, v in parse_qsl(p.query) if not re.match(r'utm_|fbclid|gclid|ref$', k)])
    return urlunsplit(('https', host, p.path.rstrip('/'), q, ''))


def trigrams(title):
    t = re.sub(r'[^0-9a-zа-яё]+', ' ', title.lower()).strip()
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def similar(a, b):
    return len(a & b) / max(1, len(a | b))


def parse_date(text):
    """Дата записи из RSS (RFC 822) или Atom (ISO 8601) -> ГГГГ-ММ-ДД; None, если даты нет."""
    if not text:
        return None
    text = text.strip()
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.datetime.fromisoformat(text.replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        m = re.match(r'\d{4}-\d\d-\d\d', text)
        return m.group(0) if m else None


def parse_feed(xml_bytes):
    """Записи RSS 2.0 и Atom: (заголовок, ссылка, дата, текст анонса без разметки)."""
    root = ET.fromstring(xml_bytes)
    loc = lambda e: e.tag.rsplit('}', 1)[-1]
    out = []
    for e in root.iter():
        if loc(e) not in ('item', 'entry'):
            continue
        f = {}
        for c in e:
            n = loc(c)
            if n == 'link':
                href = c.get('href') or (c.text or '').strip()
                if href and (c.get('rel') in (None, 'alternate')) and 'link' not in f:
                    f['link'] = href
            elif n in ('title', 'pubDate', 'published', 'updated', 'date', 'description', 'summary', 'content') and n not in f:
                f[n] = (c.text or '').strip()
        text = re.sub(r'<[^>]+>|&\w+;', ' ', f.get('description') or f.get('summary') or f.get('content') or '')
        date = parse_date(f.get('pubDate') or f.get('published') or f.get('date') or f.get('updated'))
        if f.get('title') and f.get('link'):
            out.append((re.sub(r'\s+', ' ', f['title']), f['link'], date, re.sub(r'\s+', ' ', text)[:600]))
    return out


def classify(text, src):
    found = [k for k, rx in INSTR.items() if re.search(rx, text, re.I)]
    kinds = [k for k, rx in KINDS.items() if re.search(rx, text, re.I)]
    if src.get('require_match'):      # общий источник: нужен однозначный признак, что заметка про медные
        if not found or (set(found) <= AMBIGUOUS and len(found) < 2 and not kinds):
            return None, None
    instruments = sorted(set(found) | set(src.get('instruments', [])))
    return instruments, kinds


def score(kinds, age_days, weight):
    k = max((KIND_WEIGHT[x] for x in kinds), default=0.6)   # без распознанного типа события — ниже порога для слабых источников
    fresh = max(0.3, 1 - age_days / FRESH_DAYS)
    return round(weight * k * fresh * 2, 2)


def fetch(src, feeds_dir):
    if feeds_dir:
        f = pathlib.Path(feeds_dir) / (re.sub(r'[^\w.-]+', '_', src['name']) + '.xml')
        return f.read_bytes() if f.exists() else None
    req = urllib.request.Request(src['feed_url'], headers={'User-Agent': UA, 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(5_000_000)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--date', default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    ap.add_argument('--data', default=str(ROOT / 'data' / 'news'))
    ap.add_argument('--feeds-dir', default='', help='читать фиды из файлов вместо сети')
    a = ap.parse_args()
    data, today = pathlib.Path(a.data), datetime.date.fromisoformat(a.date)
    cfg = json.loads((data / 'sources.json').read_text(encoding='utf-8'))
    moves, window = cfg.get('domain_moves', {}), cfg.get('dedupe_window_days', 45)
    seen_file = data / 'seen.json'
    seen = json.loads(seen_file.read_text(encoding='utf-8')) if seen_file.exists() else {}
    # идемпотентность: виденное в прошлый прогон за эту же дату не мешает собрать выпуск заново
    seen = {k: v for k, v in seen.items() if v != a.date and (today - datetime.date.fromisoformat(v)).days <= window}
    key = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]

    fetched = dupes = 0
    failed, cand = [], []
    for src in cfg['sources']:
        if src.get('type') != 'rss':
            continue
        try:
            raw = fetch(src, a.feeds_dir)
            rows = parse_feed(raw) if raw else []
        except Exception as e:                                   # один сломанный источник выпуск не срывает
            failed.append(f'{src["name"]}: {type(e).__name__}')
            continue
        for title, link, date, text in rows:
            fetched += 1
            if not date or not re.match(r'https?://', link):
                continue
            age = (today - datetime.date.fromisoformat(date)).days
            if age < -1 or age > FRESH_DAYS:
                continue
            url = canon(link, moves)
            tk = ' '.join(sorted(trigrams(title)))
            if key(url) in seen or key(tk) in seen:
                dupes += 1
                continue
            instruments, kinds = classify(f'{title}. {text}', src)
            if instruments is None:
                continue
            sc = score(kinds, max(age, 0), src.get('weight', 1))
            if sc < THRESHOLD:
                continue
            cand.append({'title': title, 'url': link, 'source': src['name'], 'source_weight': src.get('weight', 1),
                         'lang': src.get('lang', 'en'), 'published': date, 'summary': '', 'instruments': instruments,
                         'kinds': kinds, 'score': sc, 'cluster': [], '_tg': trigrams(title), '_keys': [key(url), key(tk)]})

    cand.sort(key=lambda i: i['published'], reverse=True)
    cand.sort(key=lambda i: i['score'], reverse=True)
    items = []
    for c in cand:                                               # одно событие — одна карточка
        twin = next((i for i in items if similar(i['_tg'], c['_tg']) >= 0.55 or canon(i['url'], moves) == canon(c['url'], moves)), None)
        if twin:
            dupes += 1
            twin['_keys'] += c['_keys']
            if c['source'] != twin['source'] and len(twin['cluster']) < 3:
                twin['cluster'].append({'source': c['source'], 'url': c['url']})
        else:
            items.append(c)
    items = items[:cfg.get('max_items', 15)]
    for n, i in enumerate(items, 1):
        i['id'] = f'{a.date}-{n:02d}'
        for k in i.pop('_keys'):
            seen[k] = a.date
        del i['_tg']
    issue = {'release': a.date, 'generated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'counts': {'fetched': fetched, 'kept': len(items), 'dropped_dupes': dupes}, 'items': items}
    dump = lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    if items:                                                    # пустой выпуск не пишем: на сайте остаётся предыдущий
        dump(data / f'{a.date}.json', issue)
        dump(seen_file, dict(sorted(seen.items())))
    idx = []
    for f in sorted(data.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json'), reverse=True)[:90]:
        d = json.loads(f.read_text(encoding='utf-8'))
        idx.append({'release': f.stem, 'count': len(d.get('items', [])), 'top': [i['title'] for i in d.get('items', [])[:3]]})
    dump(data / 'index.json', idx)
    print(f'{a.date}: получено {fetched}, в выпуске {len(items)}, дублей {dupes}' + (f'; не ответили: {", ".join(failed)}' if failed else ''))
    # код возврата для расписания: 2 — выпуск пуст, 3 — не ответили больше трёх источников (повод написать владельцу)
    return 3 if len(failed) > 3 else (0 if items else 2)


if __name__ == '__main__':
    sys.exit(main())
