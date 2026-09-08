(function () {
  'use strict';
  if (typeof document === 'undefined') return;

  const STYLE_ID = 'time-sugerido-final-fixes';
  const CSS = `
    /* Fechamento do Time Sugerido: alternativas uniformes e sempre visíveis. */
    #time #alternatives .altplayer,
    #time #alternatives .altplayer.first-choice{
      display:grid!important;
      padding:8px 11px!important;
      margin:0!important;
      background:#fff!important;
      box-shadow:none!important;
      grid-template-columns:minmax(0,1fr) auto!important;
      gap:2px 10px!important;
    }
    #time #alternatives .altplayer.first-choice:before{display:none!important;content:none!important}
    #time #alternatives .altplayer b,
    #time #alternatives .altplayer.first-choice b{
      font-size:.82rem!important;
      line-height:1.18!important;
      color:inherit!important;
      font-weight:800!important;
    }
    #time #alternatives .altpts,
    #time #alternatives .first-choice .altpts{
      align-self:center!important;
      min-width:60px!important;
      padding:4px 7px!important;
      border-radius:9px!important;
      background:#f5f9f7!important;
      color:#176b4b!important;
      font-size:.9rem!important;
      text-align:center!important;
    }
    #time #alternatives .alt-toggle{display:none!important}
    #time #alternatives .first-alt{
      display:inline-flex!important;
      margin-left:5px!important;
      padding:2px 5px!important;
      border-radius:999px!important;
      background:#e1f0e9!important;
      color:#176b4b!important;
      font-size:.5rem!important;
      font-weight:900!important;
      vertical-align:1px!important;
      white-space:nowrap!important;
    }
    @media(max-width:700px){
      #time #alternatives .altplayer,
      #time #alternatives .altplayer.first-choice{padding:7px 9px!important}
      #time #alternatives .altplayer b,
      #time #alternatives .altplayer.first-choice b{font-size:.82rem!important}
      #time #alternatives .altpts,
      #time #alternatives .first-choice .altpts{min-width:56px!important;font-size:.85rem!important}
    }
  `;

  let allPlayerOptions = [];
  let applying = false;
  let queued = false;

  function normalize(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .trim()
      .toLowerCase();
  }

  function injectStyle() {
    let style = document.getElementById(STYLE_ID);
    if (!style) {
      style = document.createElement('style');
      style.id = STYLE_ID;
      document.head.appendChild(style);
    }
    if (style.textContent !== CSS) style.textContent = CSS;
  }

  function optionData(option) {
    return {
      value: String(option.value || ''),
      text: String(option.textContent || '').trim()
    };
  }

  function rememberFullPlayerList(select) {
    const current = Array.from(select.options).map(optionData);
    if (current.length > allPlayerOptions.length) allPlayerOptions = current;
  }

  function currentSuggestedNames(section) {
    const names = new Set();
    section.querySelectorAll('#pitch .player-ball .name').forEach(el => {
      const name = normalize(el.textContent);
      if (name) names.add(name);
    });
    return names;
  }

  function limitExcludePlayer(section) {
    const select = section.querySelector('#excludePlayer');
    if (!select) return;

    rememberFullPlayerList(select);
    const names = currentSuggestedNames(section);
    if (!names.size || !allPlayerOptions.length) return;

    const desired = allPlayerOptions.filter((item, index) => {
      if (index === 0 || !item.value) return true;
      const optionName = normalize(item.text.split('·')[0]);
      return names.has(optionName);
    });

    const signature = desired.map(item => item.value + ':' + item.text).join('|');
    if (select.dataset.suggestedOnlySignature === signature) return;

    const previous = select.value;
    applying = true;
    select.replaceChildren(...desired.map(item => {
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.text;
      return option;
    }));
    if (desired.some(item => item.value === previous)) select.value = previous;
    else select.value = '';
    select.dataset.suggestedOnlySignature = signature;
    applying = false;
  }

  function showAllAlternatives(section) {
    section.querySelectorAll('#alternatives .altgroup').forEach(group => {
      const rows = Array.from(group.querySelectorAll('.altplayer'));
      rows.forEach((row, index) => {
        row.hidden = false;
        row.removeAttribute('aria-hidden');
        row.style.removeProperty('display');
        row.classList.toggle('first-choice', index === 0);

        const name = row.querySelector('b');
        if (index === 0 && name && !name.querySelector('.first-alt')) {
          const badge = document.createElement('span');
          badge.className = 'first-alt';
          badge.textContent = '1ª alternativa';
          name.appendChild(badge);
        }
      });
      group.dataset.altExpanded = '1';
      const toggle = group.querySelector('.alt-toggle');
      if (toggle) {
        toggle.hidden = true;
        toggle.setAttribute('aria-hidden', 'true');
        toggle.tabIndex = -1;
      }
    });
  }

  function apply() {
    if (applying) return;
    injectStyle();
    const section = document.getElementById('time');
    if (!section) return;
    limitExcludePlayer(section);
    showAllAlternatives(section);
  }

  function scheduleApply() {
    if (applying || queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      apply();
    });
  }

  function boot() {
    apply();
    const root = document.body;
    if (!root || root.dataset.timeSuggestedFinalObserved === '1') return;
    root.dataset.timeSuggestedFinalObserved = '1';
    new MutationObserver(scheduleApply).observe(root, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
