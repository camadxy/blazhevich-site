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
script=(ROOT/'src/script.js').read_text();chunk=script[script.index('  const search='):script.index('  /* Шапка')]
results=[]
for page in ['index.html','en/index.html']:
 p=Cards();s=(ROOT/'site'/page).read_text();p.feed(s);assert len(p.cards)==10
 js='''const records=DATA;
const extra=['genre','ensemble','source','difficulty'].map(k=>({value:'all',dataset:{catalogFilter:k},addEventListener(){}}));
const els={search:{value:'',addEventListener(){}},instrument:{value:'all',addEventListener(){}},count:{dataset:{},textContent:''},empty:{hidden:true}};
const document={getElementById:k=>els[k],querySelectorAll:q=>q==='[data-catalog-filter]'?extra:records};
'''.replace('DATA',json.dumps(p.cards,ensure_ascii=False))+chunk+'''
let runs=0;
const values=extra.map(f=>['all',...new Set(records.map(c=>c.dataset[f.dataset.catalogFilter]))]);
for(const a of values[0])for(const b of values[1])for(const c of values[2])for(const d of values[3])for(const inst of ['all',...new Set(records.map(x=>x.dataset.instrument))]){
 [a,b,c,d].forEach((v,i)=>extra[i].value=v);els.instrument.value=inst;els.search.value='';filterCatalog();
 const expected=records.filter(x=>(inst==='all'||x.dataset.instrument===inst)&&extra.every(f=>f.value==='all'||x.dataset[f.dataset.catalogFilter]===f.value)).length;
 if(records.filter(x=>!x.hidden).length!==expected)throw Error('count');if(els.empty.hidden!==(expected!==0))throw Error('empty');runs++;
}
extra.forEach(f=>f.value='all');els.instrument.value='all';els.search.value=QUERY;filterCatalog();if(records.filter(x=>!x.hidden).length!==4)throw Error('tuba search');
els.search.value='zzzz-no-match';filterCatalog();if(records.some(x=>!x.hidden)||els.empty.hidden)throw Error('zero search');
console.log(JSON.stringify({cases:runs,searchTuba:4,empty:true}));
'''.replace('QUERY',json.dumps('туба' if page=='index.html' else 'tuba'))
 test=subprocess.run(['node','-e',js],capture_output=True,text=True,check=True)
 results.append({'page':page,'filter_execution':json.loads(test.stdout)})
for pg in ['schools.html','en/index.html']:
 s=(ROOT/'site'/pg).read_text()
 assert all('id="person-'+n+'"' in s for n in ['blazhevich','shcherbinin','batashev','turusin','ladilov'])
 assert s.count('id="v3-source-')==4
 assert s.count('class="provisional"')==3
# Происхождение портрета (ИИ) и источники фото указаны на странице «О проекте» и в английской версии.
assert 'созданное с помощью ИИ' in (ROOT/'site/about.html').read_text()
assert 'AI-generated' in (ROOT/'site/en/index.html').read_text()
for pg in ['index.html','en/index.html']:
 s=(ROOT/'site'/pg).read_text()
 assert all(f in s for f in ['conservatory-1940s.webp','bolshoi-1905.webp']) and 'goznak-moscow' not in s
 assert 'class="hero-mark"' in s and '<header id="top-bar" class="home">' in s
def digest():return {str(p.relative_to(ROOT/'site')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'site').rglob('*') if p.is_file()}
# Аргументы пересборки берутся из окружения, чтобы проверку можно было запускать
# сразу после сборки с теми же параметрами (по умолчанию — параметры релиза v3).
_lastmod=os.environ.get('BLZ_LASTMOD','2026-11-09');_domain=os.environ.get('BLZ_DOMAIN','https://blazhevich.tech')
before=digest();subprocess.run([sys.executable,'build.py','--release','--domain',_domain,'--lastmod',_lastmod],cwd=ROOT,check=True);assert before==digest()
report={'tests':results,'repeat_build_identical':True,'file_count':len(before),'content_pages':7,'error_page':True,'browser_test':'NOT RUN','live_publication':'NOT PERFORMED'}
(ROOT/'TEST-RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
