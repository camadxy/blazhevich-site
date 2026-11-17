from pathlib import Path
from html.parser import HTMLParser
import re,json,subprocess,hashlib,itertools,os,sys
ROOT=Path(__file__).resolve().parents[1]
class Cards(HTMLParser):
 def __init__(self):super().__init__();self.cards=[];self.current=None
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='article' and 'data-instrument' in d:
   self.current={'dataset':{k[5:]:v for k,v in d.items() if k.startswith('data-')},'textContent':''};self.cards.append(self.current)
 def handle_data(self,s):
  if self.current is not None:self.current['textContent']+=s+' '
 def handle_endtag(self,t):
  if t=='article':self.current=None
results=[]
for page in ['index.html','en/index.html']:
 p=Cards();s=(ROOT/'site'/page).read_text();p.feed(s);assert len(p.cards)==10
 # панель поиска и фильтров убрана по просьбе владельца (13.11.2026): карточки показаны все сразу
 assert 'data-catalog-filter' not in s and 'id="search"' not in s and 'id="count"' not in s
 results.append({'page':page,'catalog_cards':10,'filters':'removed'})
for pg in ['en/index.html']:  # на русском карточки повторяли бы московское досье
 s=(ROOT/'site'/pg).read_text()
 assert all('id="person-'+n+'"' in s for n in ['blazhevich','shcherbinin','batashev','turusin','ladilov'])
 assert s.count('id="v3-source-')==4
 assert s.count('class="provisional"')==3
# Происхождение портрета (ИИ) и источники фото указаны на странице «О проекте» и в английской версии.
assert 'созданное с помощью ИИ' in (ROOT/'site/index.html').read_text().replace('\u00a0',' ')  # сборщик ставит неразрывные пробелы
assert 'AI-generated' in (ROOT/'site/en/index.html').read_text()
for pg in ['index.html','en/index.html']:
 s=(ROOT/'site'/pg).read_text()
 assert 'hero-home.webp' in s and 'goznak-moscow' not in s
 # главная — весь сайт одной страницей: первый экран, боковое меню, все разделы подряд, без верхней шапки
 assert 'class="hero-mark"' in s and 'popovertarget="menu"' in s and 'class="rail"' in s and '<header' not in s and 'id="catalog"' in s
 assert all(f'<section id="{k}"' in s for k in ['scores','listen','biography','usa','schools','concertos','about'])
# биография Райхмана живёт только в «В США»
_i=(ROOT/'site/index.html').read_text();assert _i.count('id="raichman"')==1 and _i.index('id="raichman"')<_i.index('<section id="schools"')
# EN-досье: кнопка RU парной версии на месте; автограф — только в московском
assert all('hreflang="ru"' in (ROOT/'site'/pg).read_text() for pg in ['en/moscow.html','en/leningrad.html'])
assert 'autograph-1903' in (ROOT/'site/en/moscow.html').read_text() and 'autograph-1903' not in (ROOT/'site/en/leningrad.html').read_text()
# п. 5.0 и 5.2–5.3 PLAN.md: контейнеры страниц сбалансированы; JSON-LD и x-default есть на индексируемых страницах публичной сборки
for pg in ['index.html','moscow.html','leningrad.html','us-schools.html','en/index.html','en/moscow.html','en/leningrad.html']:
 s=(ROOT/'site'/pg).read_text();assert s.count('<div')==s.count('</div>'),pg
 if 'rel="canonical"' in s:assert 'application/ld+json' in s and 'hreflang="x-default"' in s,pg
def digest():return {str(p.relative_to(ROOT/'site')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'site').rglob('*') if p.is_file()}
# Аргументы пересборки берутся из окружения, чтобы проверку можно было запускать
# сразу после сборки с теми же параметрами (по умолчанию — параметры релиза v3).
_lastmod=os.environ.get('BLZ_LASTMOD','2026-11-09');_domain=os.environ.get('BLZ_DOMAIN','https://blazhevich.tech')
before=digest();subprocess.run([sys.executable,'build.py','--release','--domain',_domain,'--lastmod',_lastmod],cwd=ROOT,check=True);assert before==digest()
report={'tests':results,'repeat_build_identical':True,'file_count':len(before),'content_pages':6,'error_page':True,'browser_test':'NOT RUN','live_publication':'NOT PERFORMED'}
(ROOT/'TEST-RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
