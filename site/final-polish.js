(function () {
  'use strict';
  if (typeof document === 'undefined') return;

  const CSS = `
    /* Polimento final aprovado — somente apresentação do Time Sugerido/modal. */
    #time details.premium-adjust{border-radius:14px!important;box-shadow:0 5px 16px rgba(22,69,50,.035)!important}
    #time details.premium-adjust>summary{min-height:36px!important;padding:7px 11px!important;font-size:.72rem!important}
    #time details.premium-adjust .controls{display:grid!important;grid-template-columns:minmax(110px,.72fr) minmax(150px,1fr) minmax(170px,1.2fr) auto auto!important;align-items:end!important;gap:7px!important;padding:8px 10px 9px!important;background:linear-gradient(180deg,#fbfdfc,#fff)!important}
    #time details.premium-adjust .field{min-width:0!important;gap:2px!important}
    #time details.premium-adjust .field label{font-size:.62rem!important;line-height:1.15;color:#7b8d86!important;text-transform:uppercase;letter-spacing:.025em;font-weight:750!important}
    #time details.premium-adjust input,
    #time details.premium-adjust select{width:100%!important;min-width:0!important;min-height:34px!important;padding:6px 8px!important;border-radius:9px!important;font-size:.76rem!important;font-weight:650;background:#fff!important}
    #time details.premium-adjust .field:first-child input{border-color:#b9d5c9!important;background:#f4faf7!important;color:#145f44!important;font-weight:850!important}
    #time details.premium-adjust .btn{min-height:34px!important;padding:6px 10px!important;border-radius:9px!important;font-size:.73rem!important;font-weight:820!important;white-space:nowrap}
    #time details.premium-adjust .btn.secondary{background:transparent!important;color:#70827b!important;border:0!important;box-shadow:none!important;padding-left:5px!important;padding-right:5px!important;font-size:.67rem!important}

    #time .venue-badge{min-width:18px;justify-content:center;font-size:.55rem!important;padding:1px 4px!important;letter-spacing:0!important}
    #time .mando-legend{display:flex;justify-content:flex-end;gap:10px;margin:-3px 2px 6px;color:#74877f;font-size:.66rem;font-weight:700}
    #time .mando-legend span{display:inline-flex;align-items:center;gap:3px}

    #time .bench{border-radius:13px!important}
    #time .bench .mini{display:grid!important;grid-template-columns:auto minmax(0,1fr) auto auto;grid-template-rows:auto;align-items:center;column-gap:7px;min-height:40px!important;padding:5px 30px 5px 9px!important}
    #time .bench .mini .pill{grid-column:1;font-size:.55rem!important;padding:2px 5px!important;white-space:nowrap}
    #time .bench .mini b{grid-column:2;margin:0!important;font-size:.78rem!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #time .bench .mini .fixture-tag{grid-column:3;font-size:.63rem!important;white-space:nowrap}
    #time .bench .mini .bench-venue{grid-column:4;margin:0!important;font-size:.72rem!important;line-height:1}
    #time .bench .mini small.muted{grid-column:2 / 5;margin-top:1px;font-size:.58rem!important;line-height:1.05!important;color:#83928c}
    #time .bench .mini:after{right:9px!important;font-size:1rem!important}

    #time .alternatives{gap:13px!important}
    #time .alternatives .altgroup{position:relative;padding:0!important;border:1px solid #e0eae5!important;border-radius:15px!important;background:#fff!important;box-shadow:0 8px 22px rgba(22,69,50,.045)!important;overflow:hidden}
    #time .alternatives .altgroup:before{display:none!important}
    #time .altgroup h3{display:flex;align-items:center;justify-content:space-between;padding:9px 11px 7px!important;margin:0!important;font-size:.72rem!important;text-transform:uppercase;letter-spacing:.035em;color:#70847c!important;background:#fbfdfc;border-bottom:1px solid #edf2ef;font-weight:820!important}
    #time .altplayer{padding:8px 11px!important;margin:0!important;position:relative!important;border-top:1px solid #edf2ef!important;background:#fff!important;grid-template-columns:minmax(0,1fr) auto!important;gap:2px 10px!important}
    #time .altplayer:first-of-type{border-top:0!important}
    #time .altplayer.first-choice{padding:11px 11px 10px 14px!important;background:linear-gradient(105deg,#f1f8f4 0%,#fff 72%)!important;box-shadow:inset 3px 0 0 #2b8a63!important}
    #time .altplayer.first-choice:before{content:'RECOMENDAÇÃO DO MODELO';display:block;grid-column:1/3;margin-bottom:3px;font-size:.52rem;letter-spacing:.055em;font-weight:900;color:#44806a}
    #time .altplayer b{font-size:.82rem!important;line-height:1.18!important;font-weight:800!important}
    #time .altplayer.first-choice b{font-size:.91rem!important;color:#203c32!important}
    #time .altplayer .first-alt{display:inline-flex;margin-left:5px;padding:2px 5px;border-radius:999px;background:#e1f0e9;color:#176b4b;font-size:.5rem;font-weight:900;vertical-align:1px;white-space:nowrap}
    #time .altplayer small{font-size:.64rem!important;line-height:1.35!important;color:#778a82!important}
    #time .altplayer small .good,#time .altplayer small .warn,#time .altplayer small .bad{font-size:.57rem!important;padding:2px 5px!important}
    #time .altpts{align-self:center!important;font-size:.9rem!important;min-width:60px!important;padding:4px 7px!important;border-radius:9px!important;background:#f5f9f7!important;color:#176b4b!important;text-align:center!important}
    #time .first-choice .altpts{font-size:1.02rem!important;background:#e8f4ee!important;color:#0f6948!important}
    #time .altpts:after{display:block!important;content:'PROJEÇÃO'!important;font-size:.46rem!important;line-height:1.05!important;margin-top:2px!important;letter-spacing:.04em!important;color:#7d938a!important;font-weight:800!important}
    #time .alt-toggle{width:100%;text-align:left;border:0!important;border-top:1px dashed #dfe8e4!important;margin:0!important;padding:7px 11px 8px!important;background:#fbfdfc!important;color:#176b4b!important;font-size:.65rem!important;font-weight:820!important}
    #time .alt-venue{font-size:.62rem!important}

    .modalbox{width:min(620px,100%)!important;padding:14px 16px!important;max-height:92vh!important;border-radius:17px!important}
    .modalbox .close{width:32px!important;height:32px!important;font-size:.82rem!important}
    #modalContent>.pill{font-size:.64rem!important;padding:3px 7px!important}
    #modalContent>h2{font-size:1.35rem!important;margin:7px 42px 2px 0!important;line-height:1.1}
    #modalContent>.fixture-tag{font-size:.76rem!important;line-height:1.2}
    #modalContent>.muted{font-size:.72rem!important;line-height:1.2}
    #modalContent .modal-kpis{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:0!important;border:1px solid #e1ebe6;border-radius:12px;overflow:hidden;margin:8px 0 0!important;background:#fbfdfc}
    #modalContent .modal-kpis .card{border:0!important;border-radius:0!important;box-shadow:none!important;padding:7px 8px!important;min-width:0}
    #modalContent .modal-kpis .card:not(:last-child){border-right:1px solid #e1ebe6!important}
    #modalContent .modal-kpis .metric small{font-size:.55rem!important;line-height:1.05!important;text-transform:uppercase;letter-spacing:.02em;white-space:normal}
    #modalContent .modal-kpis .metric b{font-size:.98rem!important;line-height:1.08!important;margin-top:2px!important;white-space:nowrap}
    #modalContent .model-note{margin:6px 0 8px;padding:6px 8px;border-radius:9px;background:#f3f7f5;color:#6d7e77;font-size:.63rem;line-height:1.32;border:1px solid #e5ece8}
    #modalContent .model-note b{color:#315347}
    #modalContent .why-title{font-size:.88rem!important;margin:9px 0 1px!important;color:#183128}
    #modalContent .scouts-subtitle{font-size:.62rem;color:#7d8c86;margin-bottom:1px}
    #modalContent .scoutrow{padding:5px 0!important;font-size:.76rem!important;line-height:1.18}
    #modalContent .scoutrow small{font-size:.6rem!important;margin-top:1px!important;line-height:1.15}
    #modalContent .scoutrow>b{font-size:.75rem}
    #modalContent h3{font-size:.83rem!important;margin:10px 0 4px!important}
    #modalContent .modal-context-grid{gap:6px!important;margin-top:4px!important}
    #modalContent .modal-context-grid .card{padding:7px 8px!important;border-radius:10px!important;box-shadow:none!important}
    #modalContent .modal-context-grid .metric small{font-size:.55rem!important}
    #modalContent .modal-context-grid .metric b{font-size:.88rem!important;margin-top:1px!important}

    @media(max-width:700px){
      header .sub{display:none!important}
      header .top{padding-top:7px!important}
      header .nav{gap:1px!important;padding:4px 0 1px!important}
      header .nav button{min-height:29px!important;padding:4px 3px!important;border-radius:5px!important;font-size:.67rem!important;background:transparent!important;box-shadow:none!important}
      header .nav button.active{color:#176b4b!important;box-shadow:inset 0 -2px 0 #176b4b!important}
      #time details.premium-adjust .controls{grid-template-columns:minmax(0,.72fr) minmax(0,1fr)!important;padding:7px 8px 8px!important;gap:6px!important}
      #time details.premium-adjust .field:nth-of-type(3){grid-column:1/3!important}
      #time details.premium-adjust .btn{min-height:34px!important;font-size:.7rem!important}
      #time details.premium-adjust .btn.secondary{justify-self:start!important;min-height:28px!important;padding:3px 2px!important}
      #time details.premium-adjust input,#time details.premium-adjust select{font-size:.73rem!important;min-height:34px!important;padding:6px 7px!important}
      #time .bench .mini{min-height:38px!important;padding:4px 27px 4px 8px!important;column-gap:5px}
      #time .bench .mini .pill{font-size:.52rem!important}
      #time .bench .mini b{font-size:.73rem!important}
      #time .bench .mini .fixture-tag{font-size:.58rem!important}
      #time .bench .mini small.muted{font-size:.54rem!important}
      #time .alternatives{grid-template-columns:1fr!important;gap:10px!important}
      #time .altgroup h3{padding:8px 9px 6px!important;font-size:.68rem!important}
      #time .altplayer{padding:7px 9px!important}
      #time .altplayer.first-choice{padding:9px 9px 9px 12px!important}
      #time .altplayer.first-choice b{font-size:.87rem!important}
      #time .altpts{min-width:56px!important;font-size:.85rem!important}
      #time .first-choice .altpts{font-size:.96rem!important}
      .modal{padding:6px!important;align-items:center!important}
      .modalbox{padding:11px 12px!important;max-height:95vh!important;border-radius:14px!important}
      #modalContent>h2{font-size:1.18rem!important;margin-top:5px!important}
      #modalContent .modal-kpis .card{padding:6px 5px!important}
      #modalContent .modal-kpis .metric small{font-size:.5rem!important}
      #modalContent .modal-kpis .metric b{font-size:.88rem!important}
      #modalContent .model-note{font-size:.59rem;padding:5px 7px;margin:5px 0 6px}
      #modalContent .scoutrow{padding:4px 0!important;font-size:.72rem!important}
      #modalContent .scoutrow small{font-size:.57rem!important}
      #modalContent h3{margin:8px 0 3px!important}
    }
    @media(max-width:430px){
      #time details.premium-adjust .controls{grid-template-columns:minmax(0,.7fr) minmax(0,1fr)!important}
      #time .bench .mini{grid-template-columns:auto minmax(0,1fr) auto auto}
      #time .bench .mini .fixture-tag{max-width:72px;overflow:hidden;text-overflow:ellipsis}
      #modalContent .modal-kpis .metric b{font-size:.82rem!important}
    }
  `;

  function injectStyle() {
    let style = document.getElementById('time-final-polish');
    if (!style) {
      style = document.createElement('style');
      style.id = 'time-final-polish';
      document.head.appendChild(style);
    }
    if (style.textContent !== CSS) style.textContent = CSS;
  }

  function ensureLegend(section) {
    const pitch = section.querySelector('#pitch');
    if (!pitch || section.querySelector('.mando-legend')) return;
    const legend = document.createElement('div');
    legend.className = 'mando-legend';
    legend.setAttribute('aria-label', 'Legenda de mando de campo');
    legend.innerHTML = '<span>🏠 Casa</span><span>✈️ Fora</span>';
    pitch.parentNode.insertBefore(legend, pitch);
  }

  function iconsOnly(section) {
    section.querySelectorAll('.venue-badge').forEach(el => {
      const away = /FORA|✈/i.test(el.textContent || '');
      el.textContent = away ? '✈️' : '🏠';
      el.title = away ? 'Fora' : 'Casa';
      el.setAttribute('aria-label', away ? 'Joga fora de casa' : 'Joga em casa');
    });
    section.querySelectorAll('.bench-venue,.alt-venue').forEach(el => {
      const away = /Fora|FORA|✈/i.test(el.textContent || '');
      el.textContent = away ? '✈️' : '🏠';
      el.title = away ? 'Fora' : 'Casa';
      el.setAttribute('aria-label', away ? 'Fora' : 'Casa');
    });
  }

  function refineAlternatives(section) {
    section.querySelectorAll('#alternatives .altgroup').forEach(group => {
      const rows = Array.from(group.querySelectorAll('.altplayer'));
      rows.forEach((row, index) => {
        row.classList.toggle('first-choice', index === 0);
        const name = row.querySelector('b');
        if (index === 0 && name && !name.querySelector('.first-alt')) {
          const badge = document.createElement('span');
          badge.className = 'first-alt';
          badge.textContent = '1ª alternativa';
          name.appendChild(badge);
        }
      });
      const toggle = group.querySelector('.alt-toggle');
      if (toggle) {
        const expanded = group.dataset.altExpanded === '1';
        const hiddenCount = Math.max(0, rows.length - 2);
        toggle.textContent = expanded ? '− Recolher' : `+${hiddenCount} opção${hiddenCount === 1 ? '' : 'ões'}`;
      }
    });
  }

  function compactModal() {
    const content = document.getElementById('modalContent');
    if (!content || !content.children.length) return;
    const directGrids = Array.from(content.children).filter(el => el.classList && el.classList.contains('grid'));
    if (directGrids[0]) directGrids[0].classList.add('modal-kpis');
    if (directGrids[1]) directGrids[1].classList.add('modal-context-grid');

    if (directGrids[0] && !content.querySelector('.model-note')) {
      const note = document.createElement('div');
      note.className = 'model-note';
      note.innerHTML = '<b>Projeção final</b> combina scouts esperados com histórico, contexto da partida, minutos/titularidade e ajustes validados do modelo; por isso ela pode ser diferente da parcela bruta de scouts.';
      directGrids[0].insertAdjacentElement('afterend', note);
    }

    const playerName = (content.querySelector('h2')?.textContent || 'este jogador').trim();
    Array.from(content.querySelectorAll('h2,h3')).forEach(h => {
      const text = (h.textContent || '').trim();
      if (/Scouts que mais pesam|scouts.*projeção/i.test(text)) {
        h.textContent = `Por que o modelo recomenda ${playerName}`;
        h.classList.add('why-title');
        if (!h.nextElementSibling || !h.nextElementSibling.classList.contains('scouts-subtitle')) {
          const sub = document.createElement('div');
          sub.className = 'scouts-subtitle';
          sub.textContent = 'Principais scouts projetados';
          h.insertAdjacentElement('afterend', sub);
        }
      }
    });
  }

  function polish() {
    injectStyle();
    const section = document.getElementById('time');
    if (section) {
      ensureLegend(section);
      iconsOnly(section);
      refineAlternatives(section);
    }
    compactModal();
  }

  function boot() {
    polish();
    const root = document.body;
    if (!root || root.dataset.finalPolishObserved === '1') return;
    root.dataset.finalPolishObserved = '1';
    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        polish();
      });
    });
    observer.observe(root, { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
