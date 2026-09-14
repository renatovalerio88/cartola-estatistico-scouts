(() => {
  function historicoGeral() {
    const box = document.querySelector('#historyAudit');
    if (!box || typeof normalizeHistory !== 'function') return;

    const times = normalizeHistory();
    const validos = times.filter(r => r.publico);
    const avaliados = validos.filter(r => r.status === 'AVALIADA');

    if (typeof drawHistory === 'function') drawHistory(avaliados);

    const linhas = validos.map(r => {
      const projetado = r.projecao != null ? fmt(r.projecao) : '—';
      const real = r.status === 'AVALIADA' ? fmt(r.pontuacao_real) : 'Aguardando';
      const diferenca = r.status === 'AVALIADA' && r.projecao != null
        ? fmt(Number(r.pontuacao_real) - Number(r.projecao))
        : '—';

      return `<tr><td><b>R${r.rodada}</b></td><td>${projetado}</td><td>${real}</td><td>${diferenca}</td></tr>`;
    }).join('');

    box.innerHTML = linhas
      ? `<div class="scroll history-list"><table><thead><tr><th>Rodada</th><th>Projetado</th><th>Real</th><th>Diferença</th></tr></thead><tbody>${linhas}</tbody></table></div>`
      : '<div class="notice">Ainda não existe rodada prospectiva válida para comparar Projetado × Real.</div>';
  }

  window.renderHistory = historicoGeral;

  const botaoHistorico = document.querySelector('#nav button[data-page="historico"]');
  if (botaoHistorico) {
    botaoHistorico.addEventListener('click', () => setTimeout(historicoGeral, 0));
  }

  if (document.querySelector('#historico.page.active')) {
    setTimeout(historicoGeral, 0);
  }
})();
