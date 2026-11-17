'use strict';
(function(){
  document.documentElement.classList.add('js');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Плеер: внешний iframe (Яндекс Музыка) подгружается только по нажатию кнопки */
  document.querySelectorAll('.player').forEach(box=>{const btn=box.querySelector('button');
    btn.addEventListener('click',()=>{const f=document.createElement('iframe');f.src=box.dataset.src;f.title=box.dataset.title;f.loading='lazy';f.allow='clipboard-write';box.replaceChildren(f)})});

  /* Меню-поповер: после перехода к разделу закрывается, чтобы не висеть над текстом */
  const menu=document.getElementById('menu');
  if(menu&&menu.hidePopover)menu.addEventListener('click',e=>{if(e.target.closest('a'))menu.hidePopover()});
  /* кнопка «Меню» сообщает экранному диктору, открыто меню или закрыто */
  const fab=document.querySelector('.fab');
  if(fab&&menu&&menu.hidePopover){fab.setAttribute('aria-controls','menu');fab.setAttribute('aria-expanded','false');
    menu.addEventListener('toggle',e=>fab.setAttribute('aria-expanded',String(e.newState==='open')))}

  /* «Лента»: фильтр по инструментам и подтягивание более свежего выпуска с сервера.
     Без JavaScript остаётся выпуск, запечённый в страницу при сборке. */
  document.querySelectorAll('[data-agent-list]').forEach(list=>{
    const chips=list.parentNode.querySelector('[data-agent-chips]'), limit=+list.dataset.agentLimit||Infinity;
    let filter='';
    const show=()=>{let n=0,last=null;list.querySelectorAll('.news-item').forEach(li=>{
        const ok=(!filter||li.dataset.agentInstruments.split(' ').includes(filter))&&n<limit;if(ok){n++;last=li}
        li.classList.toggle('is-on',ok);li.classList.remove('is-last')});
      if(last)last.classList.add('is-last');
      let empty=list.querySelector('.news-empty');
      if(!n&&!empty){empty=document.createElement('li');empty.className='news-empty';empty.textContent='В этом выпуске таких заметок нет.';list.append(empty)}
      if(empty)empty.hidden=n>0;
      list.setAttribute('data-agent-ready','')};
    if(chips){chips.hidden=false;chips.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;filter=b.dataset.agentFilter;
      chips.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));show()})}
    show();
    const live=list.dataset.agentLive;if(!live||!window.fetch)return;
    const MON='января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split(' ');
    const date=s=>{const m=/^(\d{4})-(\d\d)-(\d\d)/.exec(s||'');return m?(+m[3])+' '+MON[m[2]-1]+' '+m[1]:''};
    const web=u=>/^https?:\/\//.test(u||'');
    const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
    fetch(live,{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!Array.isArray(d.items)||!(d.release>list.dataset.agentRelease))return;
      const rows=d.items.filter(i=>i&&i.title&&web(i.url)&&i.published).slice(0,15);if(!rows.length)return;
      list.replaceChildren(...rows.map(i=>{const li=el('li','news-item');li.dataset.agentInstruments=(i.instruments||[]).join(' ');
        const meta=el('p','news-meta');meta.append(el('span','news-source',i.source||''));const t=el('time','',date(i.published));t.dateTime=i.published;meta.append(t);
        const h=el('h3');if(i.lang&&i.lang!=='ru')h.lang=i.lang;const a=el('a','',i.title);a.href=i.url;a.rel='noopener';h.append(a);li.append(meta,h);
        if(i.summary)li.append(el('p','news-sum',i.summary));return li}));
      list.dataset.agentRelease=d.release;
      const tm=list.parentNode.querySelector('.eyebrow time');if(tm){tm.dateTime=d.release;tm.textContent=date(d.release)}
      show()}).catch(()=>{});
  });

  /* Шапка, кнопка «наверх», активный пункт меню */
  const bar=document.getElementById('top-bar'), totop=document.getElementById('totop'), hero=document.getElementById('hero');
  if(!totop)return;
  /* тонкая линия прочитанного вверху общей страницы и название текущего раздела на вкладке меню у края */
  const prog=document.querySelector('.progress'), edge=document.querySelector('.rail-edge span'), edgeWord=edge?edge.textContent:'';
  /* главная — одна длинная страница: боковое меню и кнопка «Меню» появляются, когда первый экран ушёл вверх */
  const onScroll=()=>{const y=scrollY;if(bar)bar.classList.toggle('scrolled',y>10);totop.classList.toggle('show',y>700);
    if(hero)document.documentElement.classList.toggle('past-hero',y>hero.offsetHeight*.6);
    if(prog){const max=document.documentElement.scrollHeight-innerHeight;prog.style.setProperty('--p',max>0?Math.min(1,y/max):0)}};
  addEventListener('scroll',onScroll,{passive:true}); onScroll();
  totop.addEventListener('click',()=>{scrollTo({top:0,behavior:reduce?'auto':'smooth'});(document.querySelector('h1')||document.querySelector('.brand')).setAttribute('tabindex','-1');(document.querySelector('h1')||document.querySelector('.brand')).focus({preventScroll:true})});
  const links=[...document.querySelectorAll('nav a')];
  if('IntersectionObserver' in window){
    /* Подсветка пункта меню: на многостраничной версии — текущая страница, на одностраничной — раздел в поле зрения */
    const here=location.pathname.split('/').pop()||'index.html';
    const pageLink=links.find(a=>a.getAttribute('href')===here);
    if(pageLink) pageLink.classList.add('active');
    const spy=new IntersectionObserver(es=>{for(const e of es){if(e.isIntersecting){links.forEach(a=>{const h=a.getAttribute('href');if(h.includes('#'))a.classList.toggle('active',h.endsWith('#'+e.target.id))});
      const cur=document.querySelector('.rail a.active');if(edge&&cur)edge.textContent=edgeWord+' · '+cur.textContent}}},{rootMargin:'-45% 0px -50% 0px'});
    links.map(a=>a.getAttribute('href').split('#')[1]).filter(Boolean).forEach(id=>{const el=document.getElementById(id);if(el)spy.observe(el)});

    /* Плавное появление: прячем только то, что ниже первого экрана */
    if(!reduce){
      const els=[...document.querySelectorAll('.reveal')].filter(el=>el.getBoundingClientRect().top>innerHeight);
      els.forEach(el=>el.classList.add('pre'));
      const io=new IntersectionObserver(es=>{for(const e of es){if(e.isIntersecting){e.target.classList.remove('pre');io.unobserve(e.target)}}},{rootMargin:'0px 0px -8% 0px'});
      els.forEach(el=>io.observe(el));
    }
  }

})();
