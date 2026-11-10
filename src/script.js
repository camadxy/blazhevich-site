'use strict';
(function(){
  document.documentElement.classList.add('js');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Каталог: поиск и фильтр */
  const search=document.getElementById('search'), instrument=document.getElementById('instrument');
  const cards=[...document.querySelectorAll('#catalog .card')];
  const norm=s=>s.toLocaleLowerCase().replaceAll('ё','е').trim();
  const countEl=document.getElementById('count');
  const extraFilters=[...document.querySelectorAll('[data-catalog-filter]')];
  function filterCatalog(){
    const q=norm(search.value); let n=0;
    for(const c of cards){const ok=norm(c.textContent).includes(q)&&(instrument.value==='all'||c.dataset.instrument===instrument.value)&&extraFilters.every(f=>f.value==='all'||c.dataset[f.dataset.catalogFilter]===f.value);c.hidden=!ok;if(ok)n++}
    countEl.textContent=(countEl.dataset.tpl||'Показано: {n} из {t}').replace('{n}',n).replace('{t}',cards.length);
    document.getElementById('empty').hidden=n!==0;
  }
  if(search&&instrument){search.addEventListener('input',filterCatalog); instrument.addEventListener('change',filterCatalog); extraFilters.forEach(f=>f.addEventListener('change',filterCatalog)); filterCatalog();}


  /* Шапка, кнопка «наверх», активный пункт меню */
  const bar=document.getElementById('top-bar'), totop=document.getElementById('totop');
  const onScroll=()=>{const y=scrollY;bar.classList.toggle('scrolled',y>(bar.classList.contains('home')?innerHeight*.6:10));totop.classList.toggle('show',y>700)};
  addEventListener('scroll',onScroll,{passive:true}); onScroll();
  totop.addEventListener('click',()=>{scrollTo({top:0,behavior:reduce?'auto':'smooth'});(document.querySelector('h1')||document.querySelector('.brand')).setAttribute('tabindex','-1');(document.querySelector('h1')||document.querySelector('.brand')).focus({preventScroll:true})});
  const links=[...document.querySelectorAll('nav a')];
  if('IntersectionObserver' in window){
    /* Подсветка пункта меню: на многостраничной версии — текущая страница, на одностраничной — раздел в поле зрения */
    const here=location.pathname.split('/').pop()||'index.html';
    const pageLink=links.find(a=>a.getAttribute('href')===here);
    if(pageLink) pageLink.classList.add('active');
    const spy=new IntersectionObserver(es=>{for(const e of es){if(e.isIntersecting){links.forEach(a=>{const h=a.getAttribute('href');if(h.includes('#'))a.classList.toggle('active',h.endsWith('#'+e.target.id))})}}},{rootMargin:'-45% 0px -50% 0px'});
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
